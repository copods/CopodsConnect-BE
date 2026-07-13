# services/audit_service.py
"""
The single entry point for writing to the audit log.
All services call write_audit_log(...) after completing an action.
This module is never called from routes directly.

After writing the audit log row, it immediately calls the notification
engine to fan-out UserNotification rows to relevant recipients.
"""
from datetime import datetime, timezone
from prisma import Json
from db.client import db
from prisma.enums import AuditActorType, AuditEntityType, AuditEventType


async def write_audit_log(
    *,
    event_type: AuditEventType,
    actor_type: AuditActorType,
    entity_type: AuditEntityType,
    entity_id: str,
    actor_id: str | None = None,
    parent_entity_type: AuditEntityType | None = None,
    parent_entity_id: str | None = None,
    metadata: dict | None = None,
) -> "AuditLog":
    """
    Writes one row to audit_logs and then fans out UserNotification rows.
    Returns the created AuditLog row.

    actor_id is None when:
      - actor_type is SYSTEM (background job or automated action)
      - actor_type is USER/ADMIN but the user was later hard-deleted
        (in that case pass actor_type=SYSTEM or actor_type=USER with actor_id=None
         depending on which case you are in)

    metadata: a dict that gets frozen as JSON. Shape is event-type-specific.
    """
    data = {
        "eventType": event_type,
        "actorType": actor_type,
        "entityType": entity_type,
        "entityId": entity_id,
    }
    
    if actor_id is not None:
        data["actorId"] = actor_id
    if parent_entity_type is not None:
        data["parentEntityType"] = parent_entity_type
    if parent_entity_id is not None:
        data["parentEntityId"] = parent_entity_id
    if metadata is not None:
        data["metadata"] = Json(metadata)

    row = await db.auditlog.create(data=data)


    # Fan-out notification rows for relevant event types
    from services import notification_engine
    await notification_engine.dispatch(row)

    return row
