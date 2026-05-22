# jobs/purge_soft_deleted_job.py
"""
Hard-delete users that have been soft-deleted for 30+ days.
Requires no foreign-key rows pointing at the user (e.g. empty workspace tables).
"""
from datetime import datetime, timedelta, timezone
from db.client import db


async def purge_soft_deleted_users() -> None:
    """
    Permanently removes users where deletedAt is set and older than 30 days.
    Runs silently — exceptions are caught so a DB hiccup never kills the scheduler.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        await db.user.delete_many(
            where={
                "deletedAt": {"lt": cutoff}
            }
        )
    except Exception:
        pass
