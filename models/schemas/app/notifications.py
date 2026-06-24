# models/schemas/app/notifications.py
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from prisma.enums import AuditEventType, AuditActorType, AuditEntityType


class NotificationActorOut(BaseModel):
    id: str
    name: Optional[str] = None
    picture: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseModel):
    id: str                              # UserNotification.id (used as cursor)
    auditLogId: str

    eventType: AuditEventType
    actorType: AuditActorType

    # Resolved at read time. None for SYSTEM events.
    actor: Optional[NotificationActorOut] = None

    entityType: Optional[AuditEntityType] = None
    entityId: Optional[str] = None
    parentEntityType: Optional[AuditEntityType] = None
    parentEntityId: Optional[str] = None

    # Frozen snapshot from the audit log row (event-specific shape)
    metadata: Optional[Any] = None

    isRead: bool
    readAt: Optional[datetime] = None
    createdAt: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    notifications: list[NotificationOut]
    nextCursor: Optional[str] = None
    hasMore: bool
    model_config = ConfigDict(from_attributes=True)


class UnreadCountResponse(BaseModel):
    count: int
    model_config = ConfigDict(from_attributes=True)


class MarkReadResponse(BaseModel):
    notificationId: str
    isRead: bool
    readAt: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class MarkAllReadResponse(BaseModel):
    updatedCount: int
    model_config = ConfigDict(from_attributes=True)
