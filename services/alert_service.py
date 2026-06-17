# services/alert_service.py
from services.audit_service import write_audit_log
from prisma.enums import AuditActorType, AuditEntityType, AuditEventType
import json
from datetime import datetime, timezone

from db.client import db
from prisma.enums import AlertAction, ContentStatus, Role
from utils.email import send_nsfw_alert_email


async def create_alert(
    post_id: str,
    author_id: str,
    flag_details: dict,
    comment_id: str | None = None,
) -> None:
    """
    Creates an AdminAlert record and emails all admins.
    - Always creates as pending admin review (resolvedAction = None)
    """
    now = datetime.now(timezone.utc)

    alert = await db.adminalert.create(
        data={
            "postId": post_id,
            "commentId":comment_id,
            "reportedUserId": author_id,
            "flagDetails": json.dumps(flag_details),
            "resolvedAction": None,
            "resolvedAt": None,
        }
    )

    await write_audit_log(
        event_type=AuditEventType.ALERT_CREATED,
        actor_type=AuditActorType.SYSTEM,
        entity_type=AuditEntityType.ALERT,
        entity_id=alert.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post_id,
        metadata={
            "reportedUserId": author_id,
            "commentId": comment_id,
            "flagDetails": flag_details,
        },
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
    if alert.commentId:
        updated_content = await db.comment.update(
            where={"id": alert.commentId},
            data={"status": new_post_status},
        )
    else:
        updated_content = await db.post.update(
            where={"id": alert.postId},
            data={"status": new_post_status},
        )

    # Write audit log for the resolution — notification engine notifies author on CONFIRMED_REMOVAL
    await write_audit_log(
        event_type=AuditEventType.ALERT_RESOLVED,
        actor_type=AuditActorType.ADMIN,
        actor_id=resolved_by_id,
        entity_type=AuditEntityType.ALERT,
        entity_id=alert_id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=alert.postId,
        metadata={
            "resolvedAction": action.value,
            "reportedUserId": alert.reportedUserId,
            "postId": alert.postId,
            "commentId": alert.commentId,
            "flagReason": updated_content.flagReason if updated_content and updated_content.flagReason else None,
        },
    )