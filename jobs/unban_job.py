# jobs/unban_job.py
"""
Background job that clears expired bans every 15 minutes.
Runs server-side so bans expire even if the banned user never makes a request.
"""
from datetime import datetime, timezone
from db.client import db
from services.audit_service import write_audit_log
from prisma.enums import AuditActorType, AuditEntityType, AuditEventType


async def clear_expired_bans() -> None:
    """
    Finds all users where isBanned=True and bannedUntil is in the past,
    clears their ban fields, and writes a USER_BAN_EXPIRED audit log per user.
    Runs silently — exceptions are caught so a DB hiccup never kills the scheduler.
    """
    try:
        now = datetime.now(timezone.utc)
        expired_banned_users = await db.user.find_many(
            where={"isBanned": True, "bannedUntil": {"lt": now}}
        )
        for user in expired_banned_users:
            await db.user.update(
                where={"id": user.id},
                data={"isBanned": False, "bannedUntil": None, "banReason": None},
            )
            await write_audit_log(
                event_type=AuditEventType.USER_BAN_EXPIRED,
                actor_type=AuditActorType.SYSTEM,
                entity_type=AuditEntityType.USER,
                entity_id=user.id,
                metadata={"previousBanReason": user.banReason},
            )
    except Exception:
        pass
