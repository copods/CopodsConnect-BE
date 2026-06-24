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

    serialized = []
    for n in notifications:
        serialized.append(await _serialize_user_notification(n))

    return NotificationListResponse(
        notifications=serialized,
        nextCursor=next_cursor,
        hasMore=has_more,
    ).model_dump(mode="json")


async def get_unread_count(current_user, event_types: list | None = None) -> dict:
    where: dict = {"recipientId": current_user.id, "readAt": None}
    if event_types:
        where["auditLog"] = {"eventType": {"in": event_types}}
    count = await db.usernotification.count(where=where)
    return UnreadCountResponse(count=count).model_dump(mode="json")


async def mark_notification_read(current_user, notification_id: str) -> dict:
    notif = await db.usernotification.find_unique(where={"id": notification_id})
    if not notif or notif.recipientId != current_user.id:
        raise AppException(404, "Notification not found")
    if notif.readAt is not None:
        return MarkReadResponse(
            notificationId=notification_id,
            isRead=True,
            readAt=notif.readAt,
        ).model_dump(mode="json")
    now = datetime.now(timezone.utc)
    await db.usernotification.update(
        where={"id": notification_id},
        data={"readAt": now},
    )
    return MarkReadResponse(
        notificationId=notification_id,
        isRead=True,
        readAt=now,
    ).model_dump(mode="json")


async def mark_all_notifications_read(current_user, event_types: list | None = None) -> dict:
    where: dict = {"recipientId": current_user.id, "readAt": None}
    if event_types:
        where["auditLog"] = {"eventType": {"in": event_types}}
    now = datetime.now(timezone.utc)
    result = await db.usernotification.update_many(where=where, data={"readAt": now})
    return MarkAllReadResponse(updatedCount=result).model_dump(mode="json")
