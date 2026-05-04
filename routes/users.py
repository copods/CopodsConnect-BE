from fastapi import APIRouter, Depends, UploadFile, File
from middlewares.auth import require_platform_admin
from services import user_service
from utils.ApiResponse import api_response
from models.schemas.users import InviteUsersRequest, ResendInviteRequest, DeleteUserRequest

users_router = APIRouter(prefix="/users", tags=["Users"])

@users_router.post("/invite")
async def invite_users(
    body:InviteUsersRequest,
    current_user = Depends(require_platform_admin)
):
    result = await user_service.invite_users(body.emails)
    return api_response(200, result, "Users invited successfully")

@users_router.post("/invite/bulk")
async def bulk_invite_users(
    file: UploadFile = File(...),
    current_user=Depends(require_platform_admin)
):
    file_bytes = await file.read()
    result = await user_service.bulk_invite_users(file_bytes, file.filename)
    return api_response(200, result, "Bulk invitations processed successfully")

@users_router.post("/invite/resend")
async def resend_invite(
    body:ResendInviteRequest,
    current_user = Depends(require_platform_admin)
):
    result = await user_service.resend_invite(body.emails)
    return api_response(200, result, "Invitations resent successfully")

@users_router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user = Depends(require_platform_admin)
):
    result = await user_service.delete_user(current_user, user_id)
    return api_response(200, result, "User deleted successfully")

@users_router.delete("")
async def bulk_delete_users(
    body:DeleteUserRequest,
    current_user=Depends(require_platform_admin)
): 
    result = await user_service.bulk_delete_users(current_user, body.userIds)
    return api_response(200, result, "Users deleted successfully")

