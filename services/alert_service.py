# services/alert_service.py
from services.app import notification_service
import json
from datetime import datetime, timezone

from db.client import db
from prisma.enums import AlertAction, ContentStatus, Role
from utils.email import send_nsfw_alert_email


async def create_alert(
    post_id: str,
    author_id: str,
    flag_details: dict,
) -> None:
    """
    Creates an AdminAlert record and emails all admins.
    - Always creates as pending admin review (resolvedAction = None)
    """
    now = datetime.now(timezone.utc)

    await db.adminalert.create(
        data={
            "postId": post_id,
            "reportedUserId": author_id,
            "flagDetails": json.dumps(flag_details),
            "resolvedAction": None,
"resolvedAt": None,
        }
    )

    # Fetch all admins + the flagged user for the email
    admins = await db.user.find_many(
        where={
            "role": {"in": [Role.ADMIN, Role.SUPER_ADMIN]},
            "deletedAt": None,
            "isBanned": False,
        }
    )
    flagged_user = await db.user.find_unique(where={"id": author_id})
    if not flagged_user or not admins:
        return

    for admin in admins:
        await send_nsfw_alert_email(
            to_email=admin.email,
            flagged_user_name=flagged_user.name or "Unknown",
            flagged_user_email=flagged_user.email,
            post_id=post_id,
        )


async def resolve_alert(alert_id: str, action: AlertAction, resolved_by_id: str) -> None:
    """Resolves a FLAGGED alert with admin action — RESTORED or CONFIRMED_REMOVAL."""
    now = datetime.now(timezone.utc)

    alert = await db.adminalert.find_unique(where={"id": alert_id})
    if not alert:
        from utils.exceptions import AppException
        raise AppException(404, "Alert not found")
    if alert.resolvedAction is not None:
        from utils.exceptions import AppException
        raise AppException(400, "Alert is already resolved")

    new_post_status = (
        ContentStatus.PUBLISHED if action == AlertAction.RESTORED else ContentStatus.REMOVED
    )

    await db.adminalert.update(
        where={"id": alert_id},
        data={
            "resolvedAction": action,
            "resolvedAt": now,
            "resolvedById": resolved_by_id,
        },
    )
    updated_post = await db.post.update(
        where={"id": alert.postId},
        data={"status": new_post_status},
    )
    # Notify the author when admin removes their post
    if action == AlertAction.CONFIRMED_REMOVAL and updated_post:
        await notification_service.notify_post_removed_by_moderation(
            post_id=alert.postId,
            post_author_id=alert.reportedUserId,
            flag_reason=updated_post.flagReason.value if updated_post.flagReason else "UNKNOWN"
        )