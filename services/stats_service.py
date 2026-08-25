from db.client import db
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi.encoders import jsonable_encoder
from constants import (
    PARTICIPATION_WEIGHT_POST,
    PARTICIPATION_WEIGHT_APPRECIATION_SENT,
    PARTICIPATION_WEIGHT_COMMENT,
    PARTICIPATION_WEIGHT_POLL_VOTE,
    PARTICIPATION_WEIGHT_LIKE_GIVEN,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _calendar_month_bounds():
    """Returns (month_start ISO string, month_end ISO string) for the
    current calendar month in UTC.  All 'this month' queries use these bounds
    so we stay on calendar months rather than rolling 30-day windows.
    """
    now = datetime.now(ZoneInfo("UTC"))
    # first second of this month
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # first second of next month
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.isoformat(), end.isoformat()


# ---------------------------------------------------------------------------
# overview
# ---------------------------------------------------------------------------

async def get_overview_stats():
    """
    Returns 6 current-month KPI cards + last-6-months trend data.
    No rolling-30-day windows; all filters use calendar-month bounds.
    """
    month_start, month_end = _calendar_month_bounds()

    kpi_res = await db.query_raw(f"""
        SELECT
            (SELECT COUNT(*) FROM posts
             WHERE "deleted_at" IS NULL
               AND "created_at" >= '{month_start}'
               AND "created_at" <  '{month_end}') AS posts_created,

            (SELECT COUNT(*) FROM comments
             WHERE "deleted_at" IS NULL
               AND "created_at" >= '{month_start}'
               AND "created_at" <  '{month_end}') AS comments_created,

            (SELECT COUNT(*) FROM appreciations
             WHERE "deleted_at" IS NULL
               AND "created_at" <  '{month_end}') AS appreciations_sent,

            -- moderation_actions = flags raised this month + posts removed by admin this month
            --   + comments removed by admin this month
            (
              (SELECT COUNT(*) FROM admin_alerts
               WHERE "created_at" >= '{month_start}'
                 AND "created_at" <  '{month_end}')
              +
              (SELECT COUNT(*) FROM audit_logs
               WHERE "event_type" IN ('POST_REMOVED_BY_ADMIN', 'COMMENT_REMOVED_BY_ADMIN')
                 AND "created_at" >= '{month_start}'
                 AND "created_at" <  '{month_end}')
            ) AS moderation_actions
    """)
    kpis = kpi_res[0] if kpi_res else {}

    # Monthly trend — last 6 complete calendar months
    trend_res = await db.query_raw("""
        SELECT
            TO_CHAR(DATE_TRUNC('month', period_month), 'YYYY-MM') AS month,
            COALESCE(p.posts, 0)          AS posts,
            COALESCE(c.comments, 0)       AS comments,
            COALESCE(a.appreciations, 0)  AS appreciations
        FROM (
            -- generate the last 6 complete months (not including current)
            SELECT generate_series(
                DATE_TRUNC('month', NOW()) - INTERVAL '6 months',
                DATE_TRUNC('month', NOW()) - INTERVAL '1 month',
                '1 month'
            ) AS period_month
        ) months
        LEFT JOIN (
            SELECT DATE_TRUNC('month', "created_at") AS m, COUNT(*) AS posts
            FROM posts WHERE "deleted_at" IS NULL
            GROUP BY m
        ) p ON p.m = months.period_month
        LEFT JOIN (
            SELECT DATE_TRUNC('month', "created_at") AS m, COUNT(*) AS comments
            FROM comments WHERE "deleted_at" IS NULL
            GROUP BY m
        ) c ON c.m = months.period_month
        LEFT JOIN (
            SELECT DATE_TRUNC('month', "created_at") AS m, COUNT(*) AS appreciations
            FROM appreciations WHERE "deleted_at" IS NULL
            GROUP BY m
        ) a ON a.m = months.period_month
        ORDER BY period_month ASC;
    """)

    # Trim leading zero-activity months so the chart fills from left to right
    first_active_idx = 0
    for i, m in enumerate(trend_res):
        if m["posts"] > 0 or m["comments"] > 0 or m["appreciations"] > 0:
            first_active_idx = i
            break
    else:
        # If absolutely zero activity over 6 months, just show the last month on the left
        first_active_idx = 5

    active_trend = trend_res[first_active_idx:]
    
    # Pad the right side so we always return 6 data points. 
    # This prevents the bars from stretching dynamically and forces them to align left.
    while len(active_trend) < 6:
        active_trend.append({"month": "", "posts": 0, "comments": 0, "appreciations": 0})

    return {
        "kpis": kpis,
        "monthlyTrend": active_trend,
    }


# ---------------------------------------------------------------------------
# participation leaderboard
# ---------------------------------------------------------------------------

async def get_participation_leaderboard(period: str = "monthly"):
    """
    Computes the weighted participation score for each user on-the-fly.
    period: 'monthly' (current calendar month) | 'all_time'
    Weights are pulled from constants.py — not stored in DB.
    Score is never persisted; computed purely at request time.
    """
    month_start, month_end = _calendar_month_bounds()

    if period == "monthly":
        date_filter = f"AND \"created_at\" >= '{month_start}' AND \"created_at\" < '{month_end}'"
        appr_filter = f"AND a.\"created_at\" >= '{month_start}' AND a.\"created_at\" < '{month_end}'"
        like_filter = f"AND l.\"created_at\" >= '{month_start}' AND l.\"created_at\" < '{month_end}'"
    else:
        date_filter = ""
        appr_filter = ""
        like_filter = ""

    rows = await db.query_raw(f"""
        SELECT
            u.id,
            u.name,
            u.picture,
            COALESCE(p.posts_created, 0)        AS posts_created,
            COALESCE(c.comments_created, 0)     AS comments_created,
            COALESCE(a.appreciations_sent, 0)   AS appreciations_sent,
            COALESCE(pv.poll_votes_cast, 0)     AS poll_votes_cast,
            COALESCE(l.likes_given, 0)          AS likes_given
        FROM users u
        LEFT JOIN (
            SELECT "author_id", COUNT(*) AS posts_created
            FROM posts WHERE "deleted_at" IS NULL {date_filter}
            GROUP BY "author_id"
        ) p ON p."author_id" = u.id
        LEFT JOIN (
            SELECT "author_id", COUNT(*) AS comments_created
            FROM comments WHERE "deleted_at" IS NULL {date_filter}
            GROUP BY "author_id"
        ) c ON c."author_id" = u.id
        LEFT JOIN (
            SELECT a."sender_id", COUNT(*) AS appreciations_sent
            FROM appreciations a
            WHERE a."deleted_at" IS NULL {appr_filter}
            GROUP BY a."sender_id"
        ) a ON a."sender_id" = u.id
        LEFT JOIN (
            SELECT "user_id", COUNT(*) AS poll_votes_cast
            FROM poll_votes WHERE 1=1 {date_filter}
            GROUP BY "user_id"
        ) pv ON pv."user_id" = u.id
        LEFT JOIN (
            SELECT l."user_id", COUNT(*) AS likes_given
            FROM likes l WHERE 1=1 {like_filter}
            GROUP BY l."user_id"
        ) l ON l."user_id" = u.id
        WHERE u."deleted_at" IS NULL
        ORDER BY u.name;
    """)

    # Compute score in-memory — never stored
    scored = []
    for r in rows:
        posts        = int(r.get("posts_created", 0) or 0)
        comments     = int(r.get("comments_created", 0) or 0)
        appr_sent    = int(r.get("appreciations_sent", 0) or 0)
        poll_votes   = int(r.get("poll_votes_cast", 0) or 0)
        likes_given  = int(r.get("likes_given", 0) or 0)

        score = (
            posts       * PARTICIPATION_WEIGHT_POST
            + appr_sent * PARTICIPATION_WEIGHT_APPRECIATION_SENT
            + comments  * PARTICIPATION_WEIGHT_COMMENT
            + poll_votes * PARTICIPATION_WEIGHT_POLL_VOTE
            + likes_given * PARTICIPATION_WEIGHT_LIKE_GIVEN
        )

        # Only include users who have at least some activity
        if score == 0:
            continue

        scored.append({
            **r,
            "posts_created":      posts,
            "comments_created":   comments,
            "appreciations_sent": appr_sent,
            "poll_votes_cast":    poll_votes,
            "likes_given":        likes_given,
            "score":              round(score, 1),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:10]


# ---------------------------------------------------------------------------
# Section 9 helpers — admin-triggered "Most Participating Person" post
# ---------------------------------------------------------------------------

async def get_participation_post_preview(period: str = "monthly"):
    """
    Returns the #1 user on the participation leaderboard for the specified period
    and a draft post caption (no score in the text).
    Nothing is written to DB here.
    """
    leaders = await get_participation_leaderboard(period=period)
    if not leaders:
        return None

    winner = leaders[0]
    time_label = "this month" if period == "monthly" else "of all time"
    caption = (
        f"🏅 Shoutout to @[{winner['id']}] for being our most active member {time_label}! "
        f"Their consistent contributions — whether posting, commenting, or sharing appreciation — "
        f"keep our community thriving. Keep it up! 🙌"
    )
    return {
        "userId":  winner["id"],
        "name":    winner["name"],
        "picture": winner["picture"],
        "caption": caption,
    }


async def create_participation_recognition_post(admin_id: str, period: str = "monthly"):
    """
    Creates a system-style recognition post for the specified period's top
    participation scorer.  The post is created with status=PUBLISHED directly
    (same pattern as birthday/anniversary posts in daily_celebration_job.py)
    so it bypasses the normal user-post moderation flow.

    Audit logging note: we log this with the generic POST_CREATED event type
    (reusing the closest existing event) rather than adding a new enum value.
    A TODO is left here for a dedicated enum in a future schema-change pass.
    """
    preview = await get_participation_post_preview(period)
    if not preview:
        return None

    # Create post directly with PUBLISHED status — bypasses moderation,
    # exactly as birthday/anniversary system posts do.
    post = await db.post.create(
        data={
            "type":    "SYSTEM_ANNIVERSARY",   # reusing existing PostType; no schema change
            "caption": preview["caption"],
            "status":  "PUBLISHED",
            "tags": {
                "create": [{"taggedUserId": preview["userId"]}]
            },
        }
    )

    # Audit log — reuse POST_CREATED (closest existing event type).
    # TODO: add SYSTEM_PARTICIPATION_POST_CREATED to AuditEventType in a
    # future schema-change pass for a precise audit trail.
    from services.audit_service import write_audit_log
    from prisma.enums import AuditActorType, AuditEntityType, AuditEventType
    await write_audit_log(
        event_type=AuditEventType.POST_CREATED,
        actor_type=AuditActorType.ADMIN,
        actor_id=admin_id,
        entity_type=AuditEntityType.POST,
        entity_id=post.id,
        metadata={
            "systemPostKind": "PARTICIPATION_RECOGNITION",
            "recognizedUserId": preview["userId"],
            "recognizedUserName": preview["name"],
        },
    )

    return {"postId": post.id, "caption": preview["caption"]}


# ---------------------------------------------------------------------------
# engagement leaderboards
# ---------------------------------------------------------------------------

async def get_engagement_leaderboards(period: str = "monthly"):
    month_start, month_end = _calendar_month_bounds()

    if period == "monthly":
        like_date   = f"AND l.\"created_at\" >= '{month_start}' AND l.\"created_at\" < '{month_end}'"
        comment_date = f"AND c.\"created_at\" >= '{month_start}' AND c.\"created_at\" < '{month_end}'"
    else:
        like_date   = ""
        comment_date = ""

    # Most Liked Person — total likes received on their posts, raw count
    most_liked_person = await db.query_raw(f"""
        SELECT
            u.id, u.name, u.picture,
            COUNT(l.id) AS total_likes
        FROM users u
        JOIN posts p   ON u.id = p."author_id"
        JOIN likes l   ON p.id = l."post_id"
        WHERE u."deleted_at" IS NULL
          AND p."deleted_at" IS NULL
          AND p."status" = 'PUBLISHED'
          {like_date}
        GROUP BY u.id
        ORDER BY total_likes DESC
        LIMIT 5;
    """)

    # Most Comments Made — comments authored by the user
    most_comments_made = await db.query_raw(f"""
        SELECT
            u.id, u.name, u.picture,
            COUNT(c.id) AS total_comments
        FROM users u
        JOIN comments c ON u.id = c."author_id"
        WHERE u."deleted_at" IS NULL
          AND c."deleted_at" IS NULL
          {comment_date}
        GROUP BY u.id
        ORDER BY total_comments DESC
        LIMIT 5;
    """)

    # Silent Observers (Lurkers) — monthly definition:
    # has_logged_in_app = true AND zero posts this month AND zero appreciations sent this month
    silent_observers = await db.query_raw(f"""
        SELECT u.id, u.name, u.picture
        FROM users u
        WHERE u."deleted_at" IS NULL
          AND u."has_logged_in_app" = true
          AND NOT EXISTS (
              SELECT 1 FROM posts
              WHERE "author_id" = u.id
                AND "created_at" >= '{month_start}'
                AND "created_at" <  '{month_end}'
          )
          AND NOT EXISTS (
              SELECT 1 FROM appreciations
              WHERE "sender_id" = u.id
                AND "created_at" >= '{month_start}'
                AND "created_at" <  '{month_end}'
                AND "deleted_at" IS NULL
          )
        LIMIT 5;
    """)

    return {
        "mostLikedPerson":   most_liked_person,
        "mostCommentsMade":  most_comments_made,
        "silentObservers":   silent_observers,
    }


# ---------------------------------------------------------------------------
# culture leaderboards (unchanged)
# ---------------------------------------------------------------------------

async def get_culture_leaderboards():
    ultimate_duos_raw = await db.query_raw("""
        SELECT 
            LEAST(a."sender_id", ar."user_id") as u1_id,
            GREATEST(a."sender_id", ar."user_id") as u2_id,
            COUNT(*) as interactions
        FROM appreciations a
        JOIN appreciation_recipients ar ON a.id = ar."appreciation_id"
        WHERE a."deleted_at" IS NULL
        GROUP BY u1_id, u2_id
        ORDER BY interactions DESC
        LIMIT 5;
    """)

    ultimate_duos = []
    for duo in ultimate_duos_raw:
        u1 = await db.user.find_unique(where={"id": duo["u1_id"]})
        u2 = await db.user.find_unique(where={"id": duo["u2_id"]})
        if u1 and u2:
            ultimate_duos.append({
                "u1": {"id": u1.id, "name": u1.name, "picture": u1.picture},
                "u2": {"id": u2.id, "name": u2.name, "picture": u2.picture},
                "interactions": duo["interactions"]
            })

    media_heavy = await db.query_raw("""
        SELECT 
            u.id, u.name, u.picture,
            COUNT(m.id) as media_count
        FROM users u
        JOIN posts p ON u.id = p."author_id"
        JOIN post_media m ON p.id = m."post_id"
        WHERE u."deleted_at" IS NULL AND p."deleted_at" IS NULL
        GROUP BY u.id
        ORDER BY media_count DESC
        LIMIT 5;
    """)

    novelists = await db.query_raw("""
        SELECT 
            u.id, u.name, u.picture,
            AVG(LENGTH(COALESCE(p.caption, ''))) as avg_length
        FROM users u
        JOIN posts p ON u.id = p."author_id"
        WHERE u."deleted_at" IS NULL AND p."deleted_at" IS NULL AND p."status" = 'PUBLISHED'
        GROUP BY u.id
        HAVING COUNT(p.id) > 1
        ORDER BY avg_length DESC
        LIMIT 5;
    """)

    quick_updaters = await db.query_raw("""
        SELECT 
            u.id, u.name, u.picture,
            AVG(LENGTH(COALESCE(p.caption, ''))) as avg_length
        FROM users u
        JOIN posts p ON u.id = p."author_id"
        WHERE u."deleted_at" IS NULL AND p."deleted_at" IS NULL AND p."status" = 'PUBLISHED'
        GROUP BY u.id
        HAVING COUNT(p.id) > 1
        ORDER BY avg_length ASC
        LIMIT 5;
    """)

    return {
        "ultimateDuos":  ultimate_duos,
        "mediaHeavy":    media_heavy,
        "novelists":     novelists,
        "quickUpdaters": quick_updaters,
    }


# ---------------------------------------------------------------------------
# moderation leaderboards — kept so existing route doesn't 404
# ---------------------------------------------------------------------------

async def get_moderation_leaderboards():
    most_flagged = await db.query_raw("""
        SELECT 
            u.id, u.name, u.picture,
            COUNT(a.id) as flag_count
        FROM users u
        JOIN admin_alerts a ON u.id = a."reported_user_id"
        WHERE u."deleted_at" IS NULL
        GROUP BY u.id
        ORDER BY flag_count DESC
        LIMIT 5;
    """)

    cleanest_active = await db.query_raw("""
        WITH Activity AS (
            SELECT 
                u.id, u.name, u.picture,
                (SELECT COUNT(*) FROM posts WHERE "author_id" = u.id AND "deleted_at" IS NULL) +
                (SELECT COUNT(*) FROM comments WHERE "author_id" = u.id AND "deleted_at" IS NULL) +
                (SELECT COUNT(*) FROM appreciations WHERE "sender_id" = u.id AND "deleted_at" IS NULL) as total_activity
            FROM users u
            WHERE u."deleted_at" IS NULL
        )
        SELECT * FROM Activity
        WHERE total_activity > 0 
        AND NOT EXISTS (SELECT 1 FROM admin_alerts WHERE "reported_user_id" = id)
        ORDER BY total_activity DESC
        LIMIT 5;
    """)

    top_trigger_words = await db.query_raw("""
        SELECT 
            "flagged_phrase", COUNT(*) as occurrences
        FROM admin_alerts
        WHERE "flagged_phrase" IS NOT NULL
        GROUP BY "flagged_phrase"
        ORDER BY occurrences DESC
        LIMIT 10;
    """)

    return {
        "mostFlagged":     most_flagged,
        "cleanestActive":  cleanest_active,
        "topTriggerWords": top_trigger_words,
    }


# ---------------------------------------------------------------------------
# activity heatmap — kept so existing route doesn't 404
# ---------------------------------------------------------------------------

async def get_activity_heatmap(activity_type: str = "all"):
    if activity_type == "active_users":
        source_query = """SELECT "created_at" FROM audit_logs WHERE "event_type" ='USER_LOGIN_APP' """
    elif activity_type == "content":
        source_query = """
        SELECT "created_at" FROM posts WHERE "deleted_at" is NULL 
        UNION ALL 
        SELECT "created_at" FROM comments WHERE "deleted_at" is NULL 
        UNION ALL
        SELECT "created_at" FROM likes
        """
    elif activity_type == "ai_detection":
        source_query = """SELECT "created_at" FROM "admin_alerts" """
    elif activity_type == "appreciation":
        source_query = """SELECT "created_at" FROM appreciations WHERE "deleted_at" is NULL"""
    else:
        source_query = """
        SELECT "created_at" FROM posts WHERE "deleted_at" is NULL
        UNION ALL
        SELECT "created_at" FROM comments WHERE "deleted_at" IS NULL
        UNION ALL
        SELECT "created_at" FROM likes
        UNION ALL
        SELECT "created_at" FROM appreciations WHERE "deleted_at" IS NULL
        UNION ALL
        SELECT "created_at" FROM audit_logs WHERE "event_type" = 'USER_LOGIN_APP'
        UNION ALL
        SELECT "created_at" FROM admin_alerts
        """

    heatmap = await db.query_raw(f"""
    SELECT 
        EXTRACT(DOW FROM act.created_at) as day_of_week,
        EXTRACT(HOUR FROM act.created_at) as hour_of_day, 
        COUNT(*) as activity_count
    FROM (
        {source_query}
    ) act
    GROUP BY day_of_week , hour_of_day
    ORDER BY day_of_week , hour_of_day;
    """)

    return heatmap


# ---------------------------------------------------------------------------
# cross-role connections (unchanged)
# ---------------------------------------------------------------------------

async def get_cross_role_connections():
    connections = await db.query_raw("""
        SELECT 
            u1."designation" as sender_role,
            u2."designation" as receiver_role,
            COUNT(*) as count
        FROM appreciations a
        JOIN users u1 ON a."sender_id" = u1.id
        JOIN appreciation_recipients ar ON a.id = ar."appreciation_id"
        JOIN users u2 ON ar."user_id" = u2.id
        WHERE u1."designation" IS NOT NULL AND u2."designation" IS NOT NULL
        AND a."deleted_at" IS NULL
        GROUP BY sender_role, receiver_role
        ORDER BY count DESC
        LIMIT 100;
    """)
    return connections


# ---------------------------------------------------------------------------
# appreciation leaderboards
# ---------------------------------------------------------------------------

async def get_appreciation_leaderboards(period: str = "monthly"):
    month_start, month_end = _calendar_month_bounds()

    if period == "monthly":
        appr_date = f"AND a.\"created_at\" >= '{month_start}' AND a.\"created_at\" < '{month_end}'"
    else:
        appr_date = ""

    most_appreciated_persons = await db.query_raw(f"""
        SELECT u.id, u.name, u.picture, COUNT(*) as total_received
        FROM users u
        JOIN appreciation_recipients ar ON u.id = ar."user_id"
        JOIN appreciations a ON ar."appreciation_id" = a.id
        WHERE u."deleted_at" IS NULL AND a."deleted_at" IS NULL
          {appr_date}
        GROUP BY u.id
        ORDER BY total_received DESC
        LIMIT 5;
    """)

    top_appreciators = await db.query_raw(f"""
        SELECT u.id, u.name, u.picture, COUNT(*) as total_sent
        FROM users u
        JOIN appreciations a ON u.id = a."sender_id"
        WHERE u."deleted_at" IS NULL AND a."deleted_at" IS NULL
          {appr_date}
        GROUP BY u.id
        ORDER BY total_sent DESC
        LIMIT 5;
    """)

    # Most Used Types — no period filter (all-time, per spec: no changes needed)
    most_used_types = await db.query_raw("""
        SELECT t.id, t.name, t.emoji_path, COUNT(*) as total_uses
        FROM appreciation_types t
        JOIN appreciations a ON t.id = a."appreciation_type_id"
        WHERE a."deleted_at" IS NULL
        GROUP BY t.id
        ORDER BY total_uses DESC
        LIMIT 5;
    """)

    return {
        "mostAppreciatedPersons": most_appreciated_persons,
        "topAppreciators":        top_appreciators,
        "mostUsedTypes":          most_used_types,
    }


# ---------------------------------------------------------------------------
# user-specific stats (unchanged)
# ---------------------------------------------------------------------------

async def get_user_stats(user_id: str):
    fav_type_received_res = await db.query_raw(f"""
        SELECT t.name, t.emoji_path, COUNT(*) as count
        FROM appreciations a
        JOIN appreciation_recipients ar ON a.id = ar."appreciation_id"
        JOIN appreciation_types t ON a."appreciation_type_id" = t.id
        WHERE ar."user_id" = '{user_id}' AND a."deleted_at" IS NULL
        GROUP BY t.id, t.name, t.emoji_path
        ORDER BY count DESC
        LIMIT 1;
    """)

    fav_type_sent_res = await db.query_raw(f"""
        SELECT t.name, t.emoji_path, COUNT(*) as count
        FROM appreciations a
        JOIN appreciation_types t ON a."appreciation_type_id" = t.id
        WHERE a."sender_id" = '{user_id}' AND a."deleted_at" IS NULL
        GROUP BY t.id, t.name, t.emoji_path
        ORDER BY count DESC
        LIMIT 1;
    """)

    biggest_fan_res = await db.query_raw(f"""
        SELECT u.id, u.name, u.picture, COUNT(*) as count
        FROM appreciations a
        JOIN users u ON a."sender_id" = u.id
        JOIN appreciation_recipients ar ON a.id = ar."appreciation_id"
        WHERE ar."user_id" = '{user_id}' AND a."deleted_at" IS NULL
        GROUP BY u.id, u.name, u.picture
        ORDER BY count DESC
        LIMIT 1;
    """)

    most_appreciated_res = await db.query_raw(f"""
        SELECT u.id, u.name, u.picture, COUNT(*) as count
        FROM appreciations a
        JOIN appreciation_recipients ar ON a.id = ar."appreciation_id"
        JOIN users u ON ar."user_id" = u.id
        WHERE a."sender_id" = '{user_id}' AND a."deleted_at" IS NULL
        GROUP BY u.id, u.name, u.picture
        ORDER BY count DESC
        LIMIT 1;
    """)

    counts_res = await db.query_raw(f"""
        SELECT 
            (SELECT COUNT(*) FROM appreciation_recipients ar JOIN appreciations a ON a.id = ar."appreciation_id" WHERE ar."user_id" = '{user_id}' AND a."deleted_at" IS NULL) as appreciations_received,
            (SELECT COUNT(*) FROM appreciations WHERE "sender_id" = '{user_id}' AND "deleted_at" IS NULL) as appreciations_sent,
            (SELECT COUNT(*) FROM likes WHERE "user_id" = '{user_id}') as total_likes,
            (SELECT COUNT(*) FROM comments WHERE "author_id" = '{user_id}' AND "deleted_at" IS NULL) as total_comments,
            (SELECT COUNT(*) FROM posts WHERE "author_id" = '{user_id}' AND "deleted_at" IS NULL) as total_posts,
            (SELECT COUNT(*) FROM likes l JOIN posts p ON l."post_id" = p.id WHERE p."author_id" = '{user_id}') as likes_received
    """)

    return {
        "favoriteTypeReceived":  fav_type_received_res[0] if fav_type_received_res else None,
        "favoriteTypeSent":      fav_type_sent_res[0] if fav_type_sent_res else None,
        "biggestFan":            biggest_fan_res[0] if biggest_fan_res else None,
        "mostAppreciatedPerson": most_appreciated_res[0] if most_appreciated_res else None,
        "counts":                counts_res[0] if counts_res else {},
    }


# ---------------------------------------------------------------------------
# user posts (unchanged)
# ---------------------------------------------------------------------------

async def get_user_posts(user_id: str, page: int, page_size: int, post_type: str | None = None):
    where_clause = {"authorId": user_id, "deletedAt": None}
    if post_type:
        where_clause["type"] = post_type

    posts = await db.post.find_many(
        where=where_clause,
        include={
            "tags":    {"include": {"taggedUser": True}},
            "likes":   True,
            "comments": {
                "where":    {"deletedAt": None},
                "include":  {
                    "author": True,
                    "tags":   {"include": {"taggedUser": True}},
                },
                "orderBy":  {"createdAt": "asc"},
            },
            "media": True,
            "poll":  {
                "include": {
                    "options": {"orderBy": {"order": "asc"}}
                }
            },
        },
        order={"createdAt": "desc"},
        skip=(page - 1) * page_size,
        take=page_size,
    )

    total = await db.post.count(where=where_clause)

    result = []
    for p in posts:
        post_dict = p.model_dump()
        post_dict["likeCount"]    = len(p.likes)    if p.likes    else 0
        post_dict["commentCount"] = len(p.comments) if p.comments else 0
        result.append(post_dict)

    return {"posts": jsonable_encoder(result), "total": total}
