# services/app/notification_service.py
"""
Read-side notification service.
All write operations (creating notifications) now happen inside
services/notification_engine.py, called from services/audit_service.py.

This file handles only:
  - get_notifications()   → paginated notification feed
  - get_unread_count()    → badge count
  - mark_notification_read()
  - mark_all_notifications_read()
"""
from datetime import datetime, timezone
from constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from db.client import db
from utils.exceptions import AppException
from models.schemas.app.notifications import (
    NotificationOut,
    NotificationActorOut,
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
    MarkAllReadResponse,
)

# Event types whose UserNotification rows get grouped at read time into
# a single "X and N others ..." entry, keyed on (eventType, target entity, recipient).
AGGREGATED_EVENT_TYPES = ("POST_LIKED", "COMMENT_CREATED", "POLL_VOTE_CAST")


# ── Serializer ────────────────────────────────────────────────

async def _serialize_user_notification(un) -> dict:
    """
    un = UserNotification row with `auditLog` relation pre-fetched.
    Resolves actor info from the audit log's actorId at read time.
    """
    al = un.auditLog
    meta = al.metadata or {}

    actor = None
    if al.actorId:
        user = await db.user.find_unique(where={"id": al.actorId})
        if user:
            actor = NotificationActorOut(
                id=user.id,
                name=user.name,
                picture=user.picture,
            )
        else:
            # User was hard-deleted — render as anonymous
            actor = NotificationActorOut(id=al.actorId, name=None, picture=None)

    return NotificationOut(
        id=un.id,
        auditLogId=al.id,
        eventType=al.eventType,
        actorType=al.actorType,
        actor=actor,
        entityType=al.entityType,
        entityId=al.entityId,
        parentEntityType=al.parentEntityType,
        parentEntityId=al.parentEntityId,
        metadata=meta,
        isRead=un.readAt is not None,
        readAt=un.readAt,
        createdAt=un.createdAt,
    ).model_dump(mode="json")


# ── Read endpoints ────────────────────────────────────────────

async def get_notifications(
    current_user,
    cursor: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    event_types: list | None = None,
) -> dict:
    page_size = min(page_size, MAX_PAGE_SIZE)

    where: dict = {"recipientId": current_user.id}
    if event_types:
        where["auditLog"] = {"eventType": {"in": event_types}}

    notifications = await db.usernotification.find_many(
        where=where,
        take=page_size + 1,
        skip=1 if cursor else 0,
        cursor={"id": cursor} if cursor else None,
        order={"createdAt": "desc"},
        include={"auditLog": True},
    )

    has_more = len(notifications) > page_size
    if has_more:
        notifications = notifications[:page_size]

    next_cursor = notifications[-1].id if has_more else None

    serialized_list = []
    for n in notifications:
        serialized_list.append(await _serialize_user_notification(n))

        # Aggregation Logic
    grouped_notifications= []
    seen={}

    for sn in serialized_list:
        event_type = sn["eventType"]

        # only aggregate LIKED and COMMENT_CREATED
        if event_type in AGGREGATED_EVENT_TYPES:
            # Grouping key : eventType + target entity ID + recipientId
            entity_key= sn.get("parentEntityId") or sn.get("entityId")
            key = (event_type, entity_key, current_user.id)

            if key in seen : 
                base_sn = seen[key]
                base_sn["aggregatedCount"]+=1

                # If this older notification is unread , ensure the base group shows as unread 

                if not sn["isRead"] and base_sn["isRead"]:
                    base_sn["isRead"]=False
                    base_sn["readAt"]=None
                continue
            
            sn["aggregatedCount"] = 1  # NEW: keep consistent for POLL_VOTE_CAST
            seen[key]=sn
            
        grouped_notifications.append(sn)

    return NotificationListResponse(
        notifications=grouped_notifications,
        nextCursor=next_cursor,
        hasMore=has_more,
    ).model_dump(mode="json")


async def get_unread_count(current_user, event_types: list | None = None) -> dict:
    """
    Returns the number of *visible, grouped* unread notifications — matching
    exactly what the app shows in the notification drawer.

    Raw DB row count is NOT used because aggregated event types (POST_LIKED,
    COMMENT_CREATED, POLL_VOTE_CAST) collapse multiple rows into a single
    grouped item. Counting raw rows would over-report the badge (e.g. 10 likes
    on one post = 10 raw rows but only 1 grouped item shown).
    """
    where: dict = {"recipientId": current_user.id, "readAt": None}
    if event_types:
        where["auditLog"] = {"eventType": {"in": event_types}}

    # Fetch all unread rows (capped at a reasonable limit to keep this fast)
    unread_rows = await db.usernotification.find_many(
        where=where,
        take=500,
        order={"createdAt": "desc"},
        include={"auditLog": True},
    )

    # Apply the same grouping as get_notifications so the count matches the list
    seen: set = set()
    grouped_count = 0

    for un in unread_rows:
        al = un.auditLog
        et = al.eventType

        if et in AGGREGATED_EVENT_TYPES:
            # Group key: (eventType, target entity, recipient) — same as list view
            entity_key = al.parentEntityId or al.entityId
            key = (et, entity_key, current_user.id)
            if key in seen:
                continue  # Already counted this group
            seen.add(key)

        grouped_count += 1

    return UnreadCountResponse(count=grouped_count).model_dump(mode="json")


async def mark_notification_read(current_user, notification_id: str) -> dict:
    # We must include auditLog to check what type it is
    notif = await db.usernotification.find_unique(where={"id": notification_id}, include={"auditLog": True})
    if not notif or notif.recipientId != current_user.id:
        raise AppException(404, "Notification not found")
        
    now = datetime.now(timezone.utc)
    al = notif.auditLog

    # If this is an aggregated event type, mark ALL related unread notifications as read!
    if al.eventType in AGGREGATED_EVENT_TYPES:
        where_clause = {
            "recipientId": current_user.id,
            "readAt": None,
            "auditLog": {
                "eventType": al.eventType,
            }
        }
        
        if al.parentEntityId:
            where_clause["auditLog"]["parentEntityId"] = al.parentEntityId
        else:
            where_clause["auditLog"]["entityId"] = al.entityId

        await db.usernotification.update_many(
            where=where_clause,
            data={"readAt": now},
        )
    else:
        # Standard single read for non-aggregated notifications
        if notif.readAt is None:
            await db.usernotification.update(
                where={"id": notification_id},
                data={"readAt": now},
            )

    return MarkReadResponse(
        notificationId=notification_id,
        isRead=True,
        readAt=now,
    ).model_dump(mode="json")


