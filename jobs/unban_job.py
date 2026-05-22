# jobs/unban_job.py
"""
Background job that clears expired bans every 15 minutes.
Runs server-side so bans expire even if the banned user never makes a request.
"""
from datetime import datetime, timezone
from db.client import db


async def clear_expired_bans() -> None:
    """
    Finds all users where isBanned=True and bannedUntil is in the past,
    and clears their ban fields.
    Runs silently — exceptions are caught so a DB hiccup never kills the scheduler.
    """
    try:
        now = datetime.now(timezone.utc)
        await db.user.update_many(
            where={
                "isBanned": True,
                "bannedUntil": {"lt": now}
            },
            data={
                "isBanned": False,
                "bannedUntil": None
            }
        )
    except Exception:
        pass
