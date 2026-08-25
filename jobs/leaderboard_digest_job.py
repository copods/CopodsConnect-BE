# jobs/leaderboard_digest_job.py
"""
Monthly job that:
  1. Identifies the most-appreciated person for the PREVIOUS calendar month
     (by raw appreciation-received count — same basis as the Appreciation tab).
  2. Creates a system-generated congratulatory post tagging that person.
     The post is created with status=PUBLISHED directly (bypasses moderation),
     identical to how birthday/anniversary posts work in daily_celebration_job.py.
  3. Sends a LEADERBOARD_DIGEST notification to all active app users
     (updated to period="monthly").

Schedule: 1st of every month at 09:00 IST — configured in main.py.

AUDIT LOGGING NOTE:
  We reuse SYSTEM_ANNIVERSARY_POST_CREATED as the audit event type because
  adding a new AuditEventType enum value would require a schema change, which
  is out-of-scope for this pass.  A metadata field ("systemPostKind") clearly
  labels the row.  A dedicated enum should be added in a future schema-change
  pass for a precise audit trail.

FRONTEND CONTRACT (LEADERBOARD_DIGEST notification):
  { period: "monthly", monthOf: "YYYY-MM" }
  Use monthOf to display "Check out June 2026's leaderboard!" or similar.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from db.client import db
from services.app import notification_service
from services.audit_service import write_audit_log
from prisma.enums import AuditActorType, AuditEntityType, AuditEventType

logger = logging.getLogger(__name__)


async def send_most_appreciated_monthly() -> None:
    """
    Main entry point for the monthly most-appreciated job.
    Wrapped in try/except so a DB hiccup never kills the scheduler.
    """
    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))

        # ── Determine previous calendar month ────────────────────────────────
        if now.month == 1:
            prev_month = 12
            prev_year = now.year - 1
        else:
            prev_month = now.month - 1
            prev_year = now.year

        # e.g. "2026-06"
        month_label = f"{prev_year}-{prev_month:02d}"

        # first second of previous month (UTC)
        from datetime import timezone
        month_start = datetime(prev_year, prev_month, 1, tzinfo=timezone.utc).isoformat()
        if prev_month == 12:
            month_end = datetime(prev_year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
        else:
            month_end = datetime(prev_year, prev_month + 1, 1, tzinfo=timezone.utc).isoformat()

        # ── Find the most-appreciated person last month ───────────────────────
        winner_rows = await db.query_raw(f"""
            SELECT u.id, u.name, COUNT(*) AS received_count
            FROM users u
            JOIN appreciation_recipients ar ON u.id = ar."user_id"
            JOIN appreciations a ON ar."appreciation_id" = a.id
            WHERE u."deleted_at" IS NULL
              AND a."deleted_at" IS NULL
              AND a."created_at" >= '{month_start}'
              AND a."created_at" <  '{month_end}'
            GROUP BY u.id, u.name
            ORDER BY received_count DESC
            LIMIT 1;
        """)

        if not winner_rows:
            logger.info(
                "most_appreciated_monthly_job: no appreciations found for %s, skipping post",
                month_label,
            )
        else:
            winner = winner_rows[0]
            winner_id = winner["id"]
            winner_name = winner["name"] or "a team member"
            received_count = int(winner["received_count"])

            # ── Find winner's most-received appreciation type last month ──────
            type_rows = await db.query_raw(f"""
                SELECT t.name AS type_name, COUNT(*) AS type_count
                FROM appreciations a
                JOIN appreciation_recipients ar ON a.id = ar."appreciation_id"
                JOIN appreciation_types t ON a."appreciation_type_id" = t.id
                WHERE ar."user_id" = '{winner_id}'
                  AND a."deleted_at" IS NULL
                  AND a."created_at" >= '{month_start}'
                  AND a."created_at" <  '{month_end}'
                GROUP BY t.name
                ORDER BY type_count DESC
                LIMIT 1;
            """)

            type_name = type_rows[0]["type_name"] if type_rows else "Appreciation"

            # ── Create the system post (PUBLISHED — bypasses moderation) ─────
            caption = (
                f"🏆 Most Appreciated Person of the Month — @[{winner_id}]!\n\n"
                f"This past month, {winner_name} was recognised {received_count} time"
                f"{'s' if received_count != 1 else ''} by their teammates, "
                f"most often as '{type_name}'. "
                f"Thank you for making our team a better place! 🙌"
            )

            post = await db.post.create(
                data={
                    "type": "SYSTEM_ANNIVERSARY",    # reusing existing PostType; no schema change
                    "caption": caption,
                    "status": "PUBLISHED",
                    "tags": {
                        "create": [{"taggedUserId": winner_id}]
                    },
                }
            )

            # Audit log — reuse SYSTEM_ANNIVERSARY_POST_CREATED.
            # metadata.systemPostKind labels this as the monthly most-appreciated post.
            # TODO: add SYSTEM_MOST_APPRECIATED_POST_CREATED enum in a future schema pass.
            await write_audit_log(
                event_type=AuditEventType.SYSTEM_ANNIVERSARY_POST_CREATED,
                actor_type=AuditActorType.SYSTEM,
                entity_type=AuditEntityType.POST,
                entity_id=post.id,
                metadata={
                    "systemPostKind": "MONTHLY_MOST_APPRECIATED",
                    "monthOf": month_label,
                    "winnerId": winner_id,
                    "winnerName": winner_name,
                    "appreciationTypeName": type_name,
                    "totalReceived": received_count,
                },
            )

            logger.info(
                "most_appreciated_monthly_job: created post %s for winner %s (%s appreciations) in %s",
                post.id,
                winner_name,
                received_count,
                month_label,
            )

        # ── Send LEADERBOARD_DIGEST notification to all active users ─────────
        active_users = await db.user.find_many(
            where={
                "deletedAt": None,
                "isBanned": False,
                "hasLoggedInApp": True,
            }
        )

        if not active_users:
            logger.info("most_appreciated_monthly_job: no active users found, skipping digest")
            return

        for user in active_users:
            await notification_service.notify_leaderboard_digest(
                recipient_id=user.id,
                period="monthly",
                week_of=month_label,   # field name kept for API compat; value is now month label
            )

        logger.info(
            "most_appreciated_monthly_job: sent digest to %d users for month %s",
            len(active_users),
            month_label,
        )

    except Exception as e:
        logger.error("most_appreciated_monthly_job failed: %s", e)