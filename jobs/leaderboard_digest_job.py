# jobs/leaderboard_digest_job.py
"""
Scheduled job that sends a leaderboard digest notification to all active app users.
Runs every Monday at 09:00 IST — scheduled via cron trigger in main.py.

When the leaderboard feature is fully built, update the metadata here to include
the actual leaderboard period dates or a deep-link reference. For now it sends
a generic weekly prompt with the week's start date so the frontend can display
"Check this week's leaderboard" with a reference to the correct week.

FRONTEND CONTRACT:
  On receiving a LEADERBOARD_DIGEST notification, the frontend should deep-link
  the user to the leaderboard page. The metadata contains:
    { period: "weekly", weekOf: "YYYY-MM-DD" }  ← Monday's date for that week
  Use weekOf to display "Week of June 9, 2026" or similar context.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from db.client import db
from services.app import notification_service

logger = logging.getLogger(__name__)


async def send_leaderboard_digest() -> None:
    """
    Fetches all active app users and sends each one a LEADERBOARD_DIGEST
    notification. Wrapped in try/except so a DB hiccup never kills the scheduler.
    """
    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))

        # week_of is the Monday of the current week — used by frontend
        # to reference the correct leaderboard period
        days_since_monday = now.weekday()  # Monday = 0, Sunday = 6
        week_of = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_of = week_of.replace(day=now.day - days_since_monday)
        week_of_str = week_of.strftime("%Y-%m-%d")

        # Fetch all active users who have logged into the app
        active_users = await db.user.find_many(
            where={
                "deletedAt": None,
                "isBanned": False,
                "hasLoggedInApp": True,
            }
        )

        if not active_users:
            logger.info("leaderboard_digest_job: no active users found, skipping")
            return

        for user in active_users:
            await notification_service.notify_leaderboard_digest(
                recipient_id=user.id,
                period="weekly",
                week_of=week_of_str,
            )

        logger.info(
            "leaderboard_digest_job: sent digest to %d users for week %s",
            len(active_users),
            week_of_str,
        )

    except Exception as e:
        logger.error("leaderboard_digest_job failed: %s", e)