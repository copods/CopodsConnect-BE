# jobs/purge_soft_deleted_job.py
"""
Hard-delete users that have been soft-deleted for 30+ days.
Requires no foreign-key rows pointing at the user (e.g. empty workspace tables).
"""
from datetime import datetime, timedelta, timezone
from db.client import db
from services.audit_service import write_audit_log
from prisma.enums import AuditActorType, AuditEntityType, AuditEventType


async def purge_soft_deleted_users() -> None:
    """
    Permanently removes users where deletedAt is set and older than 30 days.
    Writes a USER_PURGED_BY_JOB audit log per deleted user.
    Runs silently — exceptions are caught so a DB hiccup never kills the scheduler.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        users_to_purge = await db.user.find_many(
            where={"deletedAt": {"lt": cutoff}}
        )
        for user in users_to_purge:
            await db.user.delete(where={"id": user.id})
            await write_audit_log(
                event_type=AuditEventType.USER_PURGED_BY_JOB,
                actor_type=AuditActorType.SYSTEM,
                entity_type=AuditEntityType.USER,
                entity_id=user.id,
                metadata={"email": user.email},
            )
    except Exception as e:
        print(f"❌ Error purging users: {e}")
