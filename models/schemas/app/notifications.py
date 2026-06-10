# models/schemas/app/notifications.py

from typing import Optional, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from prisma.enums import NotificationType


# ── Actor shape ───────────────────────────────────────────────
# Resolved at read time from actorIds array.
# name and picture can be None if the user was deleted.

class NotificationActorOut(BaseModel):
    id: str
    name: Optional[str] = None
    picture: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── Single notification OUT ───────────────────────────────────

class NotificationOut(BaseModel):
    id: str
    type: NotificationType

    # Resolved actor objects — empty list for system notifications.
    # For aggregated types: all actors in insertion order (newest last).
    # Frontend should take the last 2 for display ("Karan, Jay and N others").
    actors: list[NotificationActorOut]

    # Total actor count — may differ from len(actors) in future if we cap
    # the stored IDs, but for now always equals len(actors).
    actorCount: int

    # Where to navigate when the user taps this notification.
    # entityType: "post" | "comment" | "appreciation" | None
    # entityId:   cuid of that entity | None
    entityType: Optional[str] = None
    entityId: Optional[str] = None

    # Snapshot display data. Shape varies per NotificationType.
    # See schema.prisma comments for the exact shape per type.
    # Frontend should read this defensively (key may be absent if content deleted).
    metadata: Optional[Any] = None

    isRead: bool
    readAt: Optional[datetime] = None

    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Paginated list response ───────────────────────────────────

class NotificationListResponse(BaseModel):
    notifications: list[NotificationOut]
    nextCursor: Optional[str] = None
    hasMore: bool

    model_config = ConfigDict(from_attributes=True)


# ── Unread count response ─────────────────────────────────────

class UnreadCountResponse(BaseModel):
    count: int

    model_config = ConfigDict(from_attributes=True)


# ── Mark read response ────────────────────────────────────────

class MarkReadResponse(BaseModel):
    notificationId: str
    isRead: bool
    readAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── Mark all read response ────────────────────────────────────

class MarkAllReadResponse(BaseModel):
    updatedCount: int

    model_config = ConfigDict(from_attributes=True)