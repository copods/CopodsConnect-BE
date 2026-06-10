# services/app/notification_service.py
#
# NOTIFICATION SERVICE — Architecture Notes
#
# This service is the single source of truth for all notification logic.
# It is called by other services (post_service, appreciation_service) and
# by background jobs (daily_celebration_job, leaderboard_digest_job).
# It must never be called from routes directly for writes — only reads go
# through routes → service. Writes are always side-effects of other actions.
#
# IN-APP DELIVERY:
#   Notifications are stored as DB rows. The frontend is responsible for
#   polling GET /notifications/unread-count on app open and at a regular
#   interval (recommended: every 30-60 seconds while foregrounded) to keep
#   the badge count fresh. When the user taps the bell, the frontend calls
#   GET /notifications to fetch and display the full list.
#
# PUSH DELIVERY (TODO — not yet implemented):
#   When push is added, each _create_notification() call will be accompanied
#   by a _send_push_notification() call at write time (event-driven, not
#   scheduled). This requires a pushToken field on the User model and
#   integration with Expo Push API or FCM. A stub is left below.
#
# AGGREGATION:
#   POST_LIKE and POST_COMMENT are aggregated at write time (upsert pattern).
#   All other types always create a new row.
#   Aggregation resets when the recipient reads the notification — the next
#   event after a read creates a fresh row so it bubbles to the top of the list.
#
# UNLIKE ROLLBACK:
#   When a user unlikes a post, their ID is removed from the actorIds array
#   of the existing unread POST_LIKE notification (if one exists).
#   If actorIds becomes empty after removal, the row is deleted entirely.
#   If the notification was already read, nothing happens.

from datetime import datetime, timezone
from constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from db.client import db
from prisma.enums import NotificationType
from utils.exceptions import AppException
from models.schemas.app.notifications import (
    NotificationOut,
    NotificationActorOut,
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
    MarkAllReadResponse,
)

# Notification types that use write-time aggregation (upsert into existing unread row)
AGGREGATED_TYPES = {NotificationType.POST_LIKE, NotificationType.POST_COMMENT}


# ── Push stub (TODO) ──────────────────────────────────────────

async def _send_push_notification(recipient_id: str, title: str, body: str, data: dict) -> None:
    # TODO: implement push notification delivery via Expo Push API or FCM.
    # Steps when implementing:
    #   1. Add pushToken: String? field to User model in schema.prisma
    #   2. Add PUT /api/v1/app/users/me/push-token endpoint to store the token on login
    #   3. Fetch recipient.pushToken here
    #   4. If pushToken is None, return early (user has not granted permission)
    #   5. Call Expo Push API: POST https://exp.host/--/api/v2/push/send
    #      with { to: pushToken, title, body, data }
    #   6. Handle delivery errors / invalid tokens gracefully
    pass


# ── Serializer ────────────────────────────────────────────────

async def _serialize_notification(notif) -> dict:
    # Resolve actorIds to User objects at read time.
    # If a user was deleted their DB record may be gone — we handle that
    # gracefully by checking which IDs were actually found.
    actors = []
    if notif.actorIds:
        users = await db.user.find_many(
            where={"id": {"in": notif.actorIds}},
        )
        # Build a lookup so we preserve insertion order from actorIds
        user_map = {u.id: u for u in users}
        for actor_id in notif.actorIds:
            user = user_map.get(actor_id)
            actors.append(
                NotificationActorOut(
                    id=actor_id,
                    name=user.name if user else None,
                    picture=user.picture if user else None,
                )
            )

    return NotificationOut(
        id=notif.id,
        type=notif.type,
        actors=actors,
        actorCount=len(notif.actorIds),
        entityType=notif.entityType,
        entityId=notif.entityId,
        metadata=notif.metadata,
        isRead=notif.isRead,
        readAt=notif.readAt,
        createdAt=notif.createdAt,
        updatedAt=notif.updatedAt,
    ).model_dump(mode="json")


# ── Internal write helpers ────────────────────────────────────
# These are called by other services, never by routes directly.

async def _create_notification(
    *,
    recipient_id: str,
    type: NotificationType,
    actor_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """
    Creates a single non-aggregated notification row.
    Used for all individual notification types.
    actor_id is None for system notifications (celebrations, moderation, digest).
    """
    await db.notification.create(
        data={
            "recipientId": recipient_id,
            "type": type,
            "actorIds": [actor_id] if actor_id else [],
            "entityType": entity_type,
            "entityId": entity_id,
            "metadata": metadata,
        }
    )
    # TODO: call _send_push_notification() here when push is implemented


async def _upsert_aggregated_notification(
    *,
    recipient_id: str,
    type: NotificationType,
    actor_id: str,
    entity_type: str,
    entity_id: str,
    metadata: dict | None = None,
) -> None:
    """
    Upsert logic for aggregated notification types (POST_LIKE, POST_COMMENT).

    Finds an existing unread notification for this (recipient, type, entity).
    - Found and actor not already in list → append actor_id, update updatedAt
    - Found and actor already in list → no-op (idempotent)
    - Not found (never existed or was already read) → create a fresh row

    Reset on read: once isRead=True the old row is ignored and a new one
    is created, which naturally bubbles to the top of the list by createdAt.
    """
    existing = await db.notification.find_first(
        where={
            "recipientId": recipient_id,
            "type": type,
            "entityId": entity_id,
            "isRead": False,
        }
    )

    if existing:
        # Idempotency guard — don't add the same actor twice
        if actor_id in existing.actorIds:
            return
        new_actor_ids = existing.actorIds + [actor_id]
        await db.notification.update(
            where={"id": existing.id},
            data={
                "actorIds": new_actor_ids,
            },
        )
    else:
        await db.notification.create(
            data={
                "recipientId": recipient_id,
                "type": type,
                "actorIds": [actor_id],
                "entityType": entity_type,
                "entityId": entity_id,
                "metadata": metadata,
            }
        )
    # TODO: call _send_push_notification() here when push is implemented


# ── Public write functions (called by other services) ─────────

async def notify_post_liked(
    *,
    liker_id: str,
    post_id: str,
    post_author_id: str,
    post_caption: str | None,
) -> None:
    """Called by like_post() in post_service. Skipped if liker is the post author."""
    if liker_id == post_author_id:
        return
    await _upsert_aggregated_notification(
        recipient_id=post_author_id,
        type=NotificationType.POST_LIKE,
        actor_id=liker_id,
        entity_type="post",
        entity_id=post_id,
        metadata={"postCaption": post_caption[:80] if post_caption else None},
    )


async def notify_post_unliked(
    *,
    unliker_id: str,
    post_id: str,
    post_author_id: str,
) -> None:
    """
    Called by unlike_post() in post_service.
    Removes the unliker from the unread POST_LIKE notification if one exists.
    If actorIds becomes empty after removal, the row is deleted.
    If the notification was already read, nothing happens.
    """
    if unliker_id == post_author_id:
        return

    existing = await db.notification.find_first(
        where={
            "recipientId": post_author_id,
            "type": NotificationType.POST_LIKE,
            "entityId": post_id,
            "isRead": False,
        }
    )
    if not existing:
        return

    new_actor_ids = [aid for aid in existing.actorIds if aid != unliker_id]

    if not new_actor_ids:
        await db.notification.delete(where={"id": existing.id})
    else:
        await db.notification.update(
            where={"id": existing.id},
            data={"actorIds": new_actor_ids},
        )


async def notify_post_commented(
    *,
    commenter_id: str,
    post_id: str,
    post_author_id: str,
    post_caption: str | None,
) -> None:
    """
    Called by create_comment() for top-level comments only.
    Skipped if commenter is the post author.
    """
    if commenter_id == post_author_id:
        return
    await _upsert_aggregated_notification(
        recipient_id=post_author_id,
        type=NotificationType.POST_COMMENT,
        actor_id=commenter_id,
        entity_type="post",
        entity_id=post_id,
        metadata={"postCaption": post_caption[:80] if post_caption else None},
    )


async def notify_comment_replied(
    *,
    replier_id: str,
    parent_comment_id: str,
    parent_comment_author_id: str,
    post_id: str,
    comment_snippet: str,
) -> None:
    """
    Called by create_comment() when parentId is set.
    Skipped if replier is the parent comment author.
    """
    if replier_id == parent_comment_author_id:
        return
    await _create_notification(
        recipient_id=parent_comment_author_id,
        type=NotificationType.COMMENT_REPLY,
        actor_id=replier_id,
        entity_type="comment",
        entity_id=parent_comment_id,
        metadata={
            "commentSnippet": comment_snippet[:80],
            "postId": post_id,
        },
    )


async def notify_post_tagged(
    *,
    tagger_id: str,
    tagged_user_id: str,
    post_id: str,
    post_caption: str | None,
) -> None:
    """
    Called by _scan_post() in post_service when post becomes PUBLISHED.
    Only fires for USER_POST type — system posts handle their own notifications.
    Skipped if tagger is the tagged user (shouldn't happen but guard anyway).
    """
    if tagger_id == tagged_user_id:
        return
    await _create_notification(
        recipient_id=tagged_user_id,
        type=NotificationType.POST_TAG,
        actor_id=tagger_id,
        entity_type="post",
        entity_id=post_id,
        metadata={"postCaption": post_caption[:80] if post_caption else None},
    )


async def notify_comment_tagged(
    *,
    tagger_id: str,
    tagged_user_id: str,
    comment_id: str,
    post_id: str,
    comment_snippet: str,
) -> None:
    """
    Called by create_comment() for each tagged user in the comment.
    Skipped if tagger is the tagged user.
    """
    if tagger_id == tagged_user_id:
        return
    await _create_notification(
        recipient_id=tagged_user_id,
        type=NotificationType.COMMENT_TAG,
        actor_id=tagger_id,
        entity_type="comment",
        entity_id=comment_id,
        metadata={
            "commentSnippet": comment_snippet[:80],
            "postId": post_id,
        },
    )


async def notify_appreciation_received(
    *,
    sender_id: str,
    recipient_id: str,
    appreciation_id: str,
    appreciation_type_name: str,
    emoji_path: str,
    message: str | None,
) -> None:
    """Called by create_appreciation() for each recipient."""
    if sender_id == recipient_id:
        return
    await _create_notification(
        recipient_id=recipient_id,
        type=NotificationType.APPRECIATION_RECEIVED,
        actor_id=sender_id,
        entity_type="appreciation",
        entity_id=appreciation_id,
        metadata={
            "appreciationTypeName": appreciation_type_name,
            "emojiPath": emoji_path,
            "message": message,
        },
    )


async def notify_post_removed_by_moderation(
    *,
    post_id: str,
    post_author_id: str,
    flag_reason: str,
) -> None:
    """Called by _scan_post() when post status becomes REMOVED."""
    await _create_notification(
        recipient_id=post_author_id,
        type=NotificationType.POST_REMOVED_BY_MODERATION,
        actor_id=None,
        entity_type="post",
        entity_id=post_id,
        metadata={"reason": flag_reason},
    )


async def notify_birthday_celebration(
    *,
    birthday_user_id: str,
    person_name: str,
    post_id: str,
) -> None:
    """
    Called by daily_celebration_job after SYSTEM_BIRTHDATE post is created.
    Sends a personal wish to the birthday person.
    """
    await _create_notification(
        recipient_id=birthday_user_id,
        type=NotificationType.BIRTHDAY_CELEBRATION,
        actor_id=None,
        entity_type="post",
        entity_id=post_id,
        metadata={"personName": person_name},
    )


async def notify_anniversary_celebration(
    *,
    anniversary_user_id: str,
    person_name: str,
    post_id: str,
    years_at_company: int,
) -> None:
    """
    Called by daily_celebration_job after SYSTEM_ANNIVERSARY post is created.
    Sends a personal wish to the anniversary person.
    """
    await _create_notification(
        recipient_id=anniversary_user_id,
        type=NotificationType.ANNIVERSARY_CELEBRATION,
        actor_id=None,
        entity_type="post",
        entity_id=post_id,
        metadata={"personName": person_name, "yearsAtCompany": years_at_company},
    )


async def notify_peer_birthday(
    *,
    recipient_id: str,
    person_name: str,
    post_id: str,
) -> None:
    """
    Called by daily_celebration_job for each active user other than the birthday person.
    Fan-out is handled by the job, not here — this creates one row per call.
    """
    await _create_notification(
        recipient_id=recipient_id,
        type=NotificationType.PEER_BIRTHDAY,
        actor_id=None,
        entity_type="post",
        entity_id=post_id,
        metadata={"personName": person_name},
    )


async def notify_peer_anniversary(
    *,
    recipient_id: str,
    person_name: str,
    post_id: str,
    years_at_company: int,
) -> None:
    """
    Called by daily_celebration_job for each active user other than the anniversary person.
    Fan-out is handled by the job, not here — this creates one row per call.
    """
    await _create_notification(
        recipient_id=recipient_id,
        type=NotificationType.PEER_ANNIVERSARY,
        actor_id=None,
        entity_type="post",
        entity_id=post_id,
        metadata={"personName": person_name, "yearsAtCompany": years_at_company},
    )


async def notify_leaderboard_digest(
    *,
    recipient_id: str,
    period: str,
    week_of: str,
) -> None:
    """
    Called by leaderboard_digest_job for each active user.
    Fan-out is handled by the job. period: "weekly" | "monthly".
    """
    await _create_notification(
        recipient_id=recipient_id,
        type=NotificationType.LEADERBOARD_DIGEST,
        actor_id=None,
        entity_type=None,
        entity_id=None,
        metadata={"period": period, "weekOf": week_of},
    )


# ── Read endpoints (called by routes) ────────────────────────

async def get_notifications(
    current_user,
    cursor: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    types: list[NotificationType] | None = None,
) -> dict:
    """
    Cursor-paginated list of notifications for the current user.
    Sorted by createdAt desc (newest first).
    Optionally filtered by a list of NotificationType values.

    FRONTEND CONTRACT:
    - Call on app open and whenever the user taps the bell icon.
    - Pass ?types= to filter per page surface:
        Feed page:         POST_LIKE,POST_COMMENT,POST_TAG,COMMENT_REPLY,
                           COMMENT_TAG,BIRTHDAY_CELEBRATION,ANNIVERSARY_CELEBRATION,
                           PEER_BIRTHDAY,PEER_ANNIVERSARY,POST_REMOVED_BY_MODERATION
        Appreciation page: APPRECIATION_RECEIVED
    - After fetching, call PATCH /notifications/read-all (with same ?types= filter)
      to mark the fetched surface as read.
    """
    page_size = min(page_size, MAX_PAGE_SIZE)

    where: dict = {"recipientId": current_user.id}
    if types:
        where["type"] = {"in": types}

    notifications = await db.notification.find_many(
        where=where,
        take=page_size + 1,
        skip=1 if cursor else 0,
        cursor={"id": cursor} if cursor else None,
        order={"createdAt": "desc"},
    )

    has_more = len(notifications) > page_size
    if has_more:
        notifications = notifications[:page_size]

    next_cursor = notifications[-1].id if has_more else None

    serialized = []
    for n in notifications:
        serialized.append(await _serialize_notification(n))

    return NotificationListResponse(
        notifications=serialized,
        nextCursor=next_cursor,
        hasMore=has_more,
    ).model_dump(mode="json")


async def get_unread_count(
    current_user,
    types: list[NotificationType] | None = None,
) -> dict:
    """
    Returns the count of unread notifications for the current user.
    Optionally filtered by type list for per-surface badge counts.

    FRONTEND CONTRACT:
    - Call on app open (foreground resume).
    - Poll every 30-60 seconds while app is foregrounded.
    - Pass ?types= to get per-surface badge counts:
        Feed page badge:         types=POST_LIKE,POST_COMMENT,...  (all feed types)
        Appreciation page badge: types=APPRECIATION_RECEIVED
    """
    where: dict = {"recipientId": current_user.id, "isRead": False}
    if types:
        where["type"] = {"in": types}

    count = await db.notification.count(where=where)
    return UnreadCountResponse(count=count).model_dump(mode="json")


async def mark_notification_read(current_user, notification_id: str) -> dict:
    """Marks a single notification as read. 404 if not found or not owned by user."""
    notification = await db.notification.find_unique(where={"id": notification_id})
    if not notification or notification.recipientId != current_user.id:
        raise AppException(404, "Notification not found")

    if notification.isRead:
        return MarkReadResponse(
            notificationId=notification_id,
            isRead=True,
            readAt=notification.readAt,
        ).model_dump(mode="json")

    now = datetime.now(timezone.utc)
    await db.notification.update(
        where={"id": notification_id},
        data={"isRead": True, "readAt": now},
    )
    return MarkReadResponse(
        notificationId=notification_id,
        isRead=True,
        readAt=now,
    ).model_dump(mode="json")


async def mark_all_notifications_read(
    current_user,
    types: list[NotificationType] | None = None,
) -> dict:
    """
    Marks all unread notifications as read for the current user.
    Optionally scoped to specific types (for per-surface mark-all-read).

    FRONTEND CONTRACT:
    - Call after fetching the notification list for a surface, passing the
      same ?types= filter used for GET /notifications, so only that surface's
      notifications are marked read and the other surface's badge is unaffected.
    """
    where: dict = {"recipientId": current_user.id, "isRead": False}
    if types:
        where["type"] = {"in": types}

    now = datetime.now(timezone.utc)
    result = await db.notification.update_many(
        where=where,
        data={"isRead": True, "readAt": now},
    )
    return MarkAllReadResponse(updatedCount=result.count).model_dump(mode="json")