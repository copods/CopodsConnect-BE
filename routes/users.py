# routes/users.py
from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Query
from fastapi.responses import Response
from fastapi.encoders import jsonable_encoder

from middlewares.auth import require_admin, require_super_admin, require_platform
from services import user_service
from utils.ApiResponse import api_response
from utils.email import send_invitation_email, send_admin_invitation_email
from prisma.enums import Role
from constants import DEFAULT_PAGE_SIZE
from models.schemas.users import (
    InviteUsersRequest,
    InviteAdminsRequest,
    ResendInviteRequest,
    DeleteUserRequest,
    BanUserRequest,
    EditBanRequest,
    ChangeRoleRequest,
    EditUserRequest,
)

users_router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(require_platform("panel"))],
)


def _enqueue_invite_emails(
    background_tasks: BackgroundTasks,
    emails: list[str],
    role: Role,
) -> None:
    send_fn = (
        send_admin_invitation_email
        if role == Role.ADMIN
        else send_invitation_email
    )
    for email in emails:
        background_tasks.add_task(send_fn, email)


# ============================================================
# GET ALL USERS
# ============================================================

@users_router.get("")
async def get_all_users(
    search: str = Query(default=None),
    status: str = Query(default=None),
    status_surface: str = Query(default="app"),
    role: str = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1),
    current_user=Depends(require_admin),
):
    result = await user_service.get_all_users(
        search, status, status_surface, role, page, page_size,
    )
    return api_response(200, result, "Users fetched successfully")


# ============================================================
# INVITE USERS (admin + super_admin)
# ============================================================

@users_router.get("/{user_id}")
async def get_user_by_id(user_id: str, admin: dict = Depends(require_admin)):
    user = await user_service.get_user(user_id)
    return api_response(200, jsonable_encoder(user), "User fetched")

@users_router.post("/invite")
async def invite_users(
    background_tasks: BackgroundTasks,
    body: InviteUsersRequest,
    current_user=Depends(require_admin),
):
    result = await user_service.invite_users(body.people)
    _enqueue_invite_emails(background_tasks, result.pop("emailsToSend", []), Role.MEMBER)
    return api_response(202, result, "Invite sent. Email is being delivered in the background.")


@users_router.get("/invite/bulk/template")
async def download_bulk_invite_template(current_user=Depends(require_admin)):
    content = user_service.build_bulk_invite_template_workbook_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="bulk-invite-template.xlsx"',
        },
    )


@users_router.post("/invite/bulk")
async def bulk_invite_users(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
):
    file_bytes = await file.read()
    result = await user_service.bulk_invite_users(file_bytes, file.filename, role=Role.MEMBER)
    _enqueue_invite_emails(background_tasks, result.pop("emailsToSend", []), Role.MEMBER)
    return api_response(
        202,
        result,
        "Bulk invite processed. Emails are being delivered in the background.",
    )


@users_router.post("/invite/resend")
async def resend_invite(
    body: ResendInviteRequest,
    current_user=Depends(require_admin)
):
    result = await user_service.resend_invite(body.emails)
    return api_response(200, result, "Invitations resent successfully")


# ============================================================
# INVITE ADMINS (super_admin only)
# ============================================================

@users_router.post("/admins/invite")
async def invite_admins(
    background_tasks: BackgroundTasks,
    body: InviteAdminsRequest,
    current_user=Depends(require_super_admin),
):
    result = await user_service.invite_admins(body.people)
    _enqueue_invite_emails(background_tasks, result.pop("emailsToSend", []), Role.ADMIN)
    return api_response(202, result, "Invite sent. Email is being delivered in the background.")


@users_router.post("/admins/invite/bulk")
async def bulk_invite_admins(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user=Depends(require_super_admin),
):
    file_bytes = await file.read()
    result = await user_service.bulk_invite_users(file_bytes, file.filename, role=Role.ADMIN)
    _enqueue_invite_emails(background_tasks, result.pop("emailsToSend", []), Role.ADMIN)
    return api_response(
        202,
        result,
        "Bulk invite processed. Emails are being delivered in the background.",
    )


@users_router.post("/admins/invite/resend")
async def resend_admin_invite(
    body: ResendInviteRequest,
    current_user=Depends(require_super_admin)
):
    result = await user_service.resend_invite(body.emails)
    return api_response(200, result, "Admin invitations resent successfully")


@users_router.get("/admins/invite/bulk/template")
async def download_bulk_invite_admin_template(current_user=Depends(require_super_admin)):
    content = user_service.build_bulk_invite_template_workbook_bytes()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="bulk-invite-admins-template.xlsx"',
        },
    )


# ============================================================
# DELETE
# ============================================================

@users_router.get("/deleted")
async def get_deleted_users(
    current_user=Depends(require_admin)
):
    result = await user_service.get_deleted_users()
    return api_response(200, result, "Deleted users fetched successfully")


@users_router.post("/{user_id}/restore")
async def restore_user(
    user_id: str,
    current_user=Depends(require_admin)
):
    result = await user_service.restore_user(current_user, user_id)
    return api_response(200, result, "User restored successfully")


@users_router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user=Depends(require_admin)
):
    result = await user_service.delete_user(current_user, user_id)
    return api_response(200, result, "User deleted successfully")


@users_router.delete("")
async def bulk_delete_users(
    body: DeleteUserRequest,
    current_user=Depends(require_admin)
):
    result = await user_service.bulk_delete_users(current_user, body.userIds)
    return api_response(200, result, "Users deleted successfully")


# ============================================================
# BAN
# ============================================================

@users_router.post("/{user_id}/ban")
async def ban_user(
    user_id: str,
    body: BanUserRequest,
    current_user=Depends(require_admin)
):
    result = await user_service.ban_user(current_user, user_id, body.durationHours, body.reason)
    return api_response(200, result, "User banned successfully")


@users_router.patch("/{user_id}/ban")
async def edit_ban(
    user_id: str,
    body: EditBanRequest,
    current_user=Depends(require_admin)
):
    payload = body.model_dump(exclude_unset=True)
    ban_updates = {"reason": payload["reason"]} if "reason" in payload else None
    result = await user_service.edit_ban(current_user, user_id, body.durationHours, ban_updates)
    return api_response(200, result, "Ban updated successfully")


@users_router.delete("/{user_id}/ban")
async def unban_user(
    user_id: str,
    current_user=Depends(require_admin)
):
    result = await user_service.unban_user(current_user, user_id)
    return api_response(200, result, "User unbanned successfully")


# ============================================================
# ROLE CHANGE (super_admin only)
# ============================================================

@users_router.patch("/{user_id}/role")
async def change_role(
    user_id: str,
    body: ChangeRoleRequest,
    current_user=Depends(require_super_admin)
):
    result = await user_service.change_role(current_user, user_id, body.role)
    return api_response(200, result, "User role updated successfully")


# ============================================================
# EDIT USER
# ============================================================

# NOTE: This route must always be declared AFTER /{user_id}/role and /{user_id}/ban to avoid path conflicts

@users_router.patch("/{user_id}")
async def edit_user(
    user_id: str,
    body: EditUserRequest,
    current_user=Depends(require_admin)
):
    updates = body.model_dump(exclude_unset=True)
    result = await user_service.edit_user(current_user, user_id, updates)
    return api_response(200, result, "User updated successfully")

@users_router.get("/{user_id}")
async def get_user_by_id(user_id: str, admin: dict = Depends(require_admin)):
    user = await user_service.get_user(user_id)
    return api_response(200, user, "User fetched")
