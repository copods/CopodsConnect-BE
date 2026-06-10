# jobs/daily_celebration_job.py
"""
Background job that creates system posts for birthdays and work anniversaries.
Runs every day at 12:00 AM IST — scheduled via cron trigger in main.py.
"""
import logging
from datetime import datetime
from db.client import db
from zoneinfo import ZoneInfo
from services.app import notification_service

logger = logging.getLogger(__name__)


async def create_daily_celebration_posts() -> None:
    """
    Finds users with birthdays or work anniversaries today and creates system posts.
    Runs silently — exceptions are caught so a DB hiccup never kills the scheduler.
    """
    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        current_month = now.month
        current_day = now.day
        current_year = now.year

        # ── Birthdays ──────────────────────────────────────────────────────────
        birthday_users = await db.query_raw(
            """
            SELECT id, name FROM users
            WHERE EXTRACT(MONTH FROM birthdate) = $1
              AND EXTRACT(DAY FROM birthdate) = $2
              AND deleted_at IS NULL
              AND is_banned = false
            """,
            current_month,
            current_day,
        )

        for user in birthday_users:
            user_id = user["id"]
            name = user["name"] or "a team member"

            # Create the system post first — notifications reference its id
            post = await db.post.create(
                data={
                    "type": "SYSTEM_BIRTHDATE",
                    "caption": f"🎉 Happy Birthday, @{name}! Wishing you a fantastic day ahead! 🎂",
                    "status": "PUBLISHED",
                    "tags": {
                        "create": [{"taggedUserId": user_id}]
                    },
                }
            )

            # Personal wish to the birthday person
            await notification_service.notify_birthday_celebration(
                birthday_user_id=user_id,
                person_name=name,
                post_id=post.id,
            )

            # Broadcast to all other active app users so they can wish/appreciate
            peer_users = await db.user.find_many(
                where={
                    "deletedAt": None,
                    "isBanned": False,
                    "hasLoggedInApp": True,
                    "id": {"not": user_id},
                }
            )
            for peer in peer_users:
                await notification_service.notify_peer_birthday(
                    recipient_id=peer.id,
                    person_name=name,
                    post_id=post.id,
                )

        # ── Work Anniversaries ─────────────────────────────────────────────────
        anniversary_users = await db.query_raw(
            """
            SELECT id, name, EXTRACT(YEAR FROM date_of_joining)::int AS join_year
            FROM users
            WHERE EXTRACT(MONTH FROM date_of_joining) = $1
              AND EXTRACT(DAY FROM date_of_joining) = $2
              AND EXTRACT(YEAR FROM date_of_joining) < $3
              AND deleted_at IS NULL
              AND is_banned = false
            """,
            current_month,
            current_day,
            current_year,
        )

        for user in anniversary_users:
            user_id = user["id"]
            name = user["name"] or "a team member"
            join_year = user.get("join_year")
            years = int(current_year - join_year) if join_year else 1

            # Create the system post first — notifications reference its id
            post = await db.post.create(
                data={
                    "type": "SYSTEM_ANNIVERSARY",
                    "caption": (
                        f"🎊 Happy {years} Year Work Anniversary, @{name}! "
                        f"Thanks for being an amazing part of the journey! 🚀"
                    ),
                    "status": "PUBLISHED",
                    "tags": {
                        "create": [{"taggedUserId": user_id}]
                    },
                }
            )

            # Personal wish to the anniversary person
            await notification_service.notify_anniversary_celebration(
                anniversary_user_id=user_id,
                person_name=name,
                post_id=post.id,
                years_at_company=years,
            )

            # Broadcast to all other active app users
            peer_users = await db.user.find_many(
                where={
                    "deletedAt": None,
                    "isBanned": False,
                    "hasLoggedInApp": True,
                    "id": {"not": user_id},
                }
            )
            for peer in peer_users:
                await notification_service.notify_peer_anniversary(
                    recipient_id=peer.id,
                    person_name=name,
                    post_id=post.id,
                    years_at_company=years,
                )

    except Exception as e:
        logger.error("daily_celebration_job failed: %s", e)
