from db.client import db
from fastapi.encoders import jsonable_encoder

async def get_overview_stats():
    adoption_res = await db.query_raw("""
        SELECT 
            COUNT(CASE WHEN "has_logged_in_app" = true THEN 1 END) as active_users,
            COUNT(*) as total_users
        FROM users 
        WHERE "deleted_at" IS NULL AND "role" = 'MEMBER';
    """)
    adoption = adoption_res[0] if adoption_res else {"active_users": 0, "total_users": 0}

    false_pos_res = await db.query_raw("""
        SELECT 
            COUNT(CASE WHEN "resolved_action" IN ('RESTORED', 'WHITELISTED') THEN 1 END) as false_positives,
            COUNT(*) as total_resolved
        FROM admin_alerts 
        WHERE "resolved_action" IS NOT NULL;
    """)
    false_pos = false_pos_res[0] if false_pos_res else {"false_positives": 0, "total_resolved": 0}

    ratio_res = await db.query_raw("""
        SELECT 
            (SELECT COUNT(*) FROM comments WHERE "deleted_at" IS NULL AND "status" = 'PUBLISHED') as total_comments,
            (SELECT COUNT(*) FROM posts WHERE "deleted_at" IS NULL AND "status" = 'PUBLISHED') as total_posts;
    """)
    ratio = ratio_res[0] if ratio_res else {"total_comments": 0, "total_posts": 0}

    velocity_res = await db.query_raw("""
        SELECT
            COUNT(CASE WHEN "created_at" >= NOW() - INTERVAL '30 days' THEN 1 END) as this_month,
            COUNT(CASE WHEN "created_at" >= NOW() - INTERVAL '60 days' AND "created_at" < NOW() - INTERVAL '30 days' THEN 1 END) as last_month
        FROM appreciations WHERE "deleted_at" IS NULL;
    """)
    velocity = velocity_res[0] if velocity_res else {"this_month": 0, "last_month": 0}

    return {
        "adoption": adoption,
        "falsePositives": false_pos,
        "contentRatio": ratio,
        "appreciationVelocity": velocity
    }

async def get_engagement_leaderboards():
    most_engaging = await db.query_raw("""
        SELECT 
            p.id, p.caption, u.name as author_name, u.picture as author_picture,
            (SELECT COUNT(*) FROM likes WHERE "post_id" = p.id) +
            (SELECT COUNT(*) FROM comments WHERE "post_id" = p.id AND "deleted_at" IS NULL) as engagement
        FROM posts p
        JOIN users u ON p."author_id" = u.id
        WHERE p."deleted_at" IS NULL AND p."status" = 'PUBLISHED'
        ORDER BY engagement DESC
        LIMIT 5;
    """)

    most_liked_person = await db.query_raw("""
        SELECT 
            u.id, u.name, u.picture,
            COUNT(l.id) as total_likes,
            COUNT(DISTINCT p.id) as total_posts,
            CAST(COUNT(l.id) AS FLOAT) / NULLIF(COUNT(DISTINCT p.id), 0) as average_likes
        FROM users u
        JOIN posts p ON u.id = p."author_id"
        LEFT JOIN likes l ON p.id = l."post_id"
        WHERE u."deleted_at" IS NULL AND p."deleted_at" IS NULL AND p."status" = 'PUBLISHED'
        GROUP BY u.id
        HAVING COUNT(DISTINCT p.id) > 0
        ORDER BY average_likes DESC
        LIMIT 5;
    """)

    conversation_starters = await db.query_raw("""
        SELECT 
            u.id, u.name, u.picture,
            COUNT(c.id) as total_comments_received
        FROM users u
        JOIN posts p ON u.id = p."author_id"
        JOIN comments c ON p.id = c."post_id"
        WHERE u."deleted_at" IS NULL AND p."deleted_at" IS NULL AND c."deleted_at" IS NULL
        GROUP BY u.id
        ORDER BY total_comments_received DESC
        LIMIT 5;
    """)

    silent_observers = await db.query_raw("""
        SELECT u.id, u.name, u.picture
        FROM users u
        WHERE u."deleted_at" IS NULL AND u."has_logged_in_app" = true
        AND NOT EXISTS (SELECT 1 FROM posts WHERE "author_id" = u.id)
        AND NOT EXISTS (SELECT 1 FROM comments WHERE "author_id" = u.id)
        AND NOT EXISTS (SELECT 1 FROM appreciations WHERE "sender_id" = u.id)
        AND EXISTS (SELECT 1 FROM likes WHERE "user_id" = u.id)
        LIMIT 5;
    """)

    return {
        "mostEngagingPosts": most_engaging,
        "mostLikedPerson": most_liked_person,
        "conversationStarters": conversation_starters,
        "silentObservers": silent_observers
    }

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
        "ultimateDuos": ultimate_duos,
        "mediaHeavy": media_heavy,
        "novelists": novelists,
        "quickUpdaters": quick_updaters
    }

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
        "mostFlagged": most_flagged,
        "cleanestActive": cleanest_active,
        "topTriggerWords": top_trigger_words
    }

async def get_activity_heatmap():
    heatmap = await db.query_raw("""
        SELECT 
            EXTRACT(DOW FROM act.created_at) as day_of_week,
            EXTRACT(HOUR FROM act.created_at) as hour_of_day,
            COUNT(*) as activity_count
        FROM (
            SELECT "created_at" FROM posts WHERE "deleted_at" IS NULL
            UNION ALL
            SELECT "created_at" FROM comments WHERE "deleted_at" IS NULL
            UNION ALL
            SELECT "created_at" FROM likes
            UNION ALL
            SELECT "created_at" FROM appreciations WHERE "deleted_at" IS NULL
        ) act
        GROUP BY day_of_week, hour_of_day
        ORDER BY day_of_week, hour_of_day;
    """)
    return heatmap

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

async def get_user_stats(user_id: str):
    # What type of appreciation they receive the most
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

    # What type of appreciation they send the most
    fav_type_sent_res = await db.query_raw(f"""
        SELECT t.name, t.emoji_path, COUNT(*) as count
        FROM appreciations a
        JOIN appreciation_types t ON a."appreciation_type_id" = t.id
        WHERE a."sender_id" = '{user_id}' AND a."deleted_at" IS NULL
        GROUP BY t.id, t.name, t.emoji_path
        ORDER BY count DESC
        LIMIT 1;
    """)

    # The person who has most appreciated them (Their biggest fan)
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

    # The person they have most appreciated
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

    # Total numbers of appreciations received/sent, posts, comments, likes
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
        "favoriteTypeReceived": fav_type_received_res[0] if fav_type_received_res else None,
        "favoriteTypeSent": fav_type_sent_res[0] if fav_type_sent_res else None,
        "biggestFan": biggest_fan_res[0] if biggest_fan_res else None,
        "mostAppreciatedPerson": most_appreciated_res[0] if most_appreciated_res else None,
        "counts": counts_res[0] if counts_res else {}
    }


async def get_user_posts(user_id :str , page: int, page_size: int):
    posts = await db.post.find_many(
        where={"authorId": user_id, "deletedAt":None},
        include={
            "tags":{
                "include":{"taggedUser":True}
            },
            "likes":True,
            "comments":{
                "where":{"deletedAt":None},
                "include" :{"author":True},
                "orderBy":{"createdAt":"asc"}
            },
        },
        order={"createdAt":"desc"},
        skip=(page -1)* page_size,
        take=page_size,
    )

    total = await db.post.count(
        where={
            "authorId":user_id,
            "deletedAt":None
        }  
    )

    result = []
    for p in posts:
        post_dict = p.model_dump()
        post_dict["likeCount"] = len(p.likes) if p.likes else 0
        post_dict["commentCount"]= len(p.comments) if p.comments else 0 
        result.append(post_dict)
    
    return {"posts":jsonable_encoder(result), "total":total}

async def get_appreciation_leaderboards():
    most_appreciated_persons = await db.query_raw("""
        SELECT u.id, u.name, u.picture, COUNT(*) as total_received
        FROM users u
        JOIN appreciation_recipients ar ON u.id = ar."user_id"
        JOIN appreciations a ON ar."appreciation_id" = a.id
        WHERE u."deleted_at" IS NULL AND a."deleted_at" IS NULL
        GROUP BY u.id
        ORDER BY total_received DESC
        LIMIT 5;
    """)

    top_appreciators = await db.query_raw("""
        SELECT u.id, u.name, u.picture, COUNT(*) as total_sent
        FROM users u
        JOIN appreciations a ON u.id = a."sender_id"
        WHERE u."deleted_at" IS NULL AND a."deleted_at" IS NULL
        GROUP BY u.id
        ORDER BY total_sent DESC
        LIMIT 5;
    """)

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
        "topAppreciators": top_appreciators,
        "mostUsedTypes": most_used_types
    }
