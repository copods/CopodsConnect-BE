# services/user_service.py
import io
import re
import openpyxl
from datetime import datetime, timedelta, timezone
from db.client import db
from prisma.enums import Role
from utils.exceptions import AppException
from utils.email import send_invitation_email, send_admin_invitation_email
from constants import ALLOWED_EMAIL_DOMAIN


# ============================================================
# INVITE
# ============================================================

async def invite_users(emails: list) -> dict:
    """Invite users to the app. Creates MEMBER stub records."""
    return await _process_email_invites(emails, role=Role.MEMBER)


async def invite_admins(emails: list) -> dict:
    """Invite admins to the panel. Creates ADMIN stub records. SUPER_ADMIN only."""
    return await _process_email_invites(emails, role=Role.ADMIN)


async def _process_email_invites(emails: list, role: Role) -> dict:
    invited = []
    skipped = []

    for email in emails:
        # Domain check — only @copods.co emails allowed
        if not email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
            skipped.append({
                "email": email,
                "reason": f"Only @{ALLOWED_EMAIL_DOMAIN} emails can be invited"
            })
            continue

        existing_user = await db.user.find_unique(where={"email": email})

        if existing_user:
            skipped.append({"email": email, "reason": "User already exists"})
            continue

        await db.user.create(
            data={
                "email": email,
                "role": role
            }
        )

        # Send appropriate email based on role
        if role == Role.ADMIN:
            send_admin_invitation_email(email)
        else:
            send_invitation_email(email)

        invited.append({"email": email})

    return {
        "invited": invited,
        "skipped": skipped
    }


async def bulk_invite_users(file_bytes: bytes, filename: str, role: Role = Role.MEMBER) -> dict:
    """
    Bulk invite from Excel file.
    role param determines whether inviting users (MEMBER) or admins (ADMIN).
    """
    if not filename.lower().endswith(".xlsx") and not filename.lower().endswith(".xls"):
        raise AppException(400, "Invalid file format. Only .xlsx and .xls files are allowed")

    try:
        workbook = openpyxl.load_workbook(io.BytesIO(file_bytes))
    except Exception:
        raise AppException(400, "Invalid Excel file")

    sheet = workbook.active

    # Find email column (case insensitive)
    headers = [cell.value for cell in sheet[1]]
    email_col_index = None

    for i, header in enumerate(headers):
        if header and header.lower() == "email":
            email_col_index = i + 1
            break

    if email_col_index is None:
        raise AppException(400, "Email column not found in the Excel file")

    # Extract emails from rows
    raw_emails = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        value = row[email_col_index - 1]
        if value and str(value).strip():
            raw_emails.append(str(value).strip())

    if not raw_emails:
        raise AppException(400, "No valid emails found in the Excel file")

    # Validate email format
    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    valid_emails = []
    skipped = []

    for email in raw_emails:
        if email_regex.match(email):
            valid_emails.append(email)
        else:
            skipped.append({"email": email, "reason": "Invalid email format"})

    result = await _process_email_invites(valid_emails, role=role)

    all_skipped = skipped + result["skipped"]
    invited = result["invited"]

    return {
        "invited": invited,
        "skipped": all_skipped,
        "totalProcessed": len(raw_emails),
        "totalInvited": len(invited),
        "totalSkipped": len(all_skipped)
    }


async def resend_invite(emails: list) -> dict:
    """
    Resend invite emails to existing users/admins.
    No new DB entry created.
    Sends admin email template if role is ADMIN, user template otherwise.
    """
    sent = []
    skipped = []

    for email in emails:
        user = await db.user.find_unique(where={"email": email})

        if not user:
            skipped.append({"email": email, "reason": "User not found"})
            continue

        if user.role == Role.ADMIN:
            send_admin_invitation_email(email)
        else:
            send_invitation_email(email)

        sent.append({"email": email})

    return {
        "sent": sent,
        "skipped": skipped
    }


# ============================================================
# DELETE
# ============================================================

async def _check_delete_permission(caller, target_user):
    # Block self deletion
    if caller.id == target_user.id:
        raise AppException(400, "You cannot delete yourself")

    # Nobody can delete a SUPER_ADMIN
    if target_user.role == Role.SUPER_ADMIN:
        raise AppException(403, "Super Admins cannot be deleted")

    # ADMIN can only delete MEMBERs — only SUPER_ADMIN can delete ADMINs
    if caller.role == Role.ADMIN and target_user.role != Role.MEMBER:
        raise AppException(403, "Admins can only delete members")


async def delete_user(current_user, target_user_id: str) -> dict:
    target_user = await db.user.find_unique(where={"id": target_user_id})

    if not target_user:
        raise AppException(404, "User not found")

    await _check_delete_permission(current_user, target_user)

    await db.user.delete(where={"id": target_user_id})

    return {"deletedUserId": target_user_id}


async def bulk_delete_users(current_user, user_ids: list) -> dict:
    deleted = []
    skipped = []

    for user_id in user_ids:
        target_user = await db.user.find_unique(where={"id": user_id})

        if not target_user:
            skipped.append({"userId": user_id, "reason": "User not found"})
            continue

        try:
            await _check_delete_permission(current_user, target_user)
        except AppException as e:
            skipped.append({"userId": user_id, "reason": e.message})
            continue

        await db.user.delete(where={"id": user_id})
        deleted.append({"userId": user_id})

    return {"deleted": deleted, "skipped": skipped}


# ============================================================
# BAN
# ============================================================

def _check_ban_permission(caller, target_user):
    """Shared permission check for ban, edit ban, unban."""
    if caller.id == target_user.id:
        raise AppException(400, "You cannot perform this action on yourself")

    if target_user.role == Role.SUPER_ADMIN:
        raise AppException(403, "Super Admins cannot be banned")

    # ADMIN cannot perform any ban operation on another ADMIN
    if caller.role == Role.ADMIN and target_user.role == Role.ADMIN:
        raise AppException(403, "Admins cannot ban other admins")


async def ban_user(current_user, target_user_id: str, duration_hours: int) -> dict:
    if current_user.id == target_user_id:
        raise AppException(400, "You cannot ban yourself")

    target_user = await db.user.find_unique(where={"id": target_user_id})

    if not target_user:
        raise AppException(404, "User not found")

    _check_ban_permission(current_user, target_user)

    if duration_hours <= 0:
        raise AppException(400, "Ban duration must be greater than 0 hours")

    banned_until = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

    updated_user = await db.user.update(
        where={"id": target_user_id},
        data={
            "isBanned": True,
            "bannedUntil": banned_until
        }
    )

    return {
        "userId": updated_user.id,
        "isBanned": updated_user.isBanned,
        "bannedUntil": updated_user.bannedUntil.isoformat()
    }


async def edit_ban(current_user, target_user_id: str, duration_hours: int) -> dict:
    if current_user.id == target_user_id:
        raise AppException(400, "You cannot edit your own ban")

    target_user = await db.user.find_unique(where={"id": target_user_id})

    if not target_user:
        raise AppException(404, "User not found")

    _check_ban_permission(current_user, target_user)

    if not target_user.isBanned:
        raise AppException(400, "This user is not currently banned")

    if duration_hours <= 0:
        raise AppException(400, "Ban duration must be greater than 0 hours")

    banned_until = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

    updated_user = await db.user.update(
        where={"id": target_user_id},
        data={"bannedUntil": banned_until}
    )

    return {
        "userId": updated_user.id,
        "isBanned": updated_user.isBanned,
        "bannedUntil": updated_user.bannedUntil.isoformat()
    }


async def unban_user(current_user, target_user_id: str) -> dict:
    if current_user.id == target_user_id:
        raise AppException(400, "You cannot unban yourself")

    target_user = await db.user.find_unique(where={"id": target_user_id})

    if not target_user:
        raise AppException(404, "User not found")

    _check_ban_permission(current_user, target_user)

    if not target_user.isBanned:
        raise AppException(400, "This user is not currently banned")

    await db.user.update(
        where={"id": target_user_id},
        data={
            "isBanned": False,
            "bannedUntil": None
        }
    )

    return {"userId": target_user_id, "isBanned": False}


# ============================================================
# ROLE CHANGE
# ============================================================

async def change_role(current_user, target_user_id: str, new_role: str) -> dict:
    """
    Change an admin's role to MEMBER or a member's role to ADMIN.
    SUPER_ADMIN only. Cannot change SUPER_ADMIN role.
    Accepted values for new_role: 'MEMBER', 'ADMIN'
    """
    if current_user.id == target_user_id:
        raise AppException(400, "You cannot change your own role")

    if new_role not in ("MEMBER", "ADMIN"):
        raise AppException(400, "Role must be either 'MEMBER' or 'ADMIN'")

    target_user = await db.user.find_unique(where={"id": target_user_id})

    if not target_user:
        raise AppException(404, "User not found")

    if target_user.role == Role.SUPER_ADMIN:
        raise AppException(403, "Super Admin role cannot be changed")

    if str(target_user.role) == new_role:
        raise AppException(400, f"User already has the role {new_role}")

    updated_user = await db.user.update(
        where={"id": target_user_id},
        data={"role": Role[new_role]}
    )

    return {
        "userId": updated_user.id,
        "role": str(updated_user.role)
    }


# ============================================================
# GET ALL USERS
# ============================================================

async def get_all_users(search: str = None) -> list:
    if search:
        users = await db.user.find_many(
            where={
                "OR": [
                    {"email": {"contains": search, "mode": "insensitive"}},
                    {"name": {"contains": search, "mode": "insensitive"}}
                ]
            },
            order={"createdAt": "desc"}
        )
    else:
        users = await db.user.find_many(order={"createdAt": "desc"})

    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "picture": u.picture,
            "role": str(u.role),
            "isBanned": u.isBanned,
            "bannedUntil": u.bannedUntil.isoformat() if u.bannedUntil else None,
            "hasLoggedInApp": u.hasLoggedInApp,
            "hasLoggedInPanel": u.hasLoggedInPanel,
            "createdAt": u.createdAt.isoformat()
        }
        for u in users
    ]