# services/app/appreciation_service.py
from datetime import datetime, timezone

from db.client import db
from utils.exceptions import AppException
from constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, BASE_URL
from services.audit_service import write_audit_log
from prisma.enums import AuditActorType, AuditEntityType, AuditEventType
from models.schemas.app.appreciations import (
    AppreciationOut,
    AppreciationListResponse,
    AppreciationTypeMinimalOut,
    AppreciationSenderOut,
    RecipientOut,
    MarkSeenResponse,
    DeleteAppreciationResponse,
)


APPRECIATION_INCLUDE = {
    "sender": True,
    "appreciationType": True,
    "recipients": {
        "include": {"user": True}
    },
}


# ── Serializers ───────────────────────────────────────────────

def _serialize_recipient(r) -> RecipientOut:
    user = getattr(r, "user", None)
    return RecipientOut(
        id=r.id,
        userId=r.userId,
        userName=user.name if user else None,
        userPicture=user.picture if user else None,
        seenAt=r.seenAt,
    )


def _build_emoji_url(emoji_path: str) -> str:
    return f"{BASE_URL}/{emoji_path}"


def _serialize_appreciation_type(t) -> AppreciationTypeMinimalOut:
    return AppreciationTypeMinimalOut(
        id=t.id,
        name=t.name,
        emojiUrl=_build_emoji_url(t.emojiPath),
        badgeUrl=_build_emoji_url(t.badgePath) if t.badgePath else None,
        description=t.description,
        displayOrder=t.displayOrder,
    )


def _serialize_appreciation(a) -> dict:
    sender = getattr(a, "sender", None)
    appreciation_type = getattr(a, "appreciationType", None)
    recipients = getattr(a, "recipients", []) or []

    return AppreciationOut(
        id=a.id,
        senderId=a.senderId,
        sender=AppreciationSenderOut(
            id=sender.id,
            name=sender.name,
            picture=sender.picture,
            designation=sender.designation,
        ) if sender else None,
        appreciationTypeId=a.appreciationTypeId,
        appreciationType=_serialize_appreciation_type(appreciation_type)
        if appreciation_type
        else None,
        message=a.message,
        createdAt=a.createdAt,
        updatedAt=a.updatedAt,
        recipients=[_serialize_recipient(r) for r in recipients],
    ).model_dump(mode="json")


# ── Validation helper ─────────────────────────────────────────

async def _validate_recipients(recipient_ids: list[str], sender_id: str):
    if not recipient_ids:
        raise AppException(400, "At least one recipient is required")

    if sender_id in recipient_ids:
        raise AppException(400, "You cannot appreciate yourself")

    if len(recipient_ids) != len(set(recipient_ids)):
        raise AppException(400, "Duplicate recipient IDs are not allowed")

    users = await db.user.find_many(
        where={"id": {"in": recipient_ids}, "deletedAt": None}
    )
    if len(users) != len(recipient_ids):
        raise AppException(400, "One or more recipients not found")


# ── Appreciation types (picker) ───────────────────────────────

async def get_active_types() -> list[dict]:
    types = await db.appreciationtype.find_many(
        where={"isActive": True},
        order={"displayOrder": "asc"},
    )
    return [
        _serialize_appreciation_type(t).model_dump(mode="json")
        for t in types
    ]


# ── CRUD ──────────────────────────────────────────────────────

async def create_appreciation(current_user, body) -> dict:
    appreciation_type = await db.appreciationtype.find_unique(
        where={"id": body.appreciationTypeId}
    )
    if not appreciation_type or not appreciation_type.isActive:
        raise AppException(404, "Appreciation type not found or inactive")

    await _validate_recipients(body.recipientIds, current_user.id)

    appreciation = await db.appreciation.create(
        data={
            "senderId": current_user.id,
            "appreciationTypeId": body.appreciationTypeId,
            "message": body.message,
            "recipients": {
                "create": [{"userId": uid} for uid in body.recipientIds]
            },
        },
        include=APPRECIATION_INCLUDE,
    )

    await write_audit_log(
        event_type=AuditEventType.APPRECIATION_SENT,
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.APPRECIATION,
        entity_id=appreciation.id,
        metadata={
            "recipientIds": body.recipientIds,
            "appreciationTypeName": appreciation_type.name,
            "emojiPath": appreciation_type.emojiPath,
            "message": body.message,
        },
    )

    return _serialize_appreciation(appreciation)


async def get_sent_appreciations(
    current_user,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page_size = min(page_size, MAX_PAGE_SIZE)
    skip = (page - 1) * page_size
    where = {"senderId": current_user.id, "deletedAt": None}

    total = await db.appreciation.count(where=where)
    appreciations = await db.appreciation.find_many(
        where=where,
        order={"createdAt": "desc"},
        take=page_size,
        skip=skip,
        include=APPRECIATION_INCLUDE,
    )

    return AppreciationListResponse(
        appreciations=[_serialize_appreciation(a) for a in appreciations],
        total=total,
        page=page,
        pageSize=page_size,
    ).model_dump(mode="json")


async def get_received_appreciations(
    current_user,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page_size = min(page_size, MAX_PAGE_SIZE)
    skip = (page - 1) * page_size
    where = {
        "userId": current_user.id,
        "appreciation": {"deletedAt": None},
    }

    total = await db.appreciationrecipient.count(where=where)
    recipient_rows = await db.appreciationrecipient.find_many(
        where=where,
        order={"createdAt": "desc"},
        take=page_size,
        skip=skip,
        include={
            "appreciation": {
                "include": APPRECIATION_INCLUDE
            }
        },
    )

    return AppreciationListResponse(
        appreciations=[_serialize_appreciation(row.appreciation) for row in recipient_rows],
        total=total,
        page=page,
        pageSize=page_size,
    ).model_dump(mode="json")


async def update_appreciation(current_user, appreciation_id: str, body) -> dict:
    appreciation = await db.appreciation.find_unique(
        where={"id": appreciation_id},
        include={"recipients": True},
    )
    if not appreciation or appreciation.deletedAt is not None:
        raise AppException(404, "Appreciation not found")
    if appreciation.senderId != current_user.id:
        raise AppException(403, "You can only edit your own appreciations")

    update_data = {}
    if body.message is not None:
        update_data["message"] = body.message

    if body.recipientIds is not None:
        await _validate_recipients(body.recipientIds, current_user.id)

        existing_ids = {r.userId for r in appreciation.recipients}
        new_ids = set(body.recipientIds)
        to_remove = existing_ids - new_ids
        to_add = new_ids - existing_ids

        if to_remove:
            await db.appreciationrecipient.delete_many(
                where={
                    "appreciationId": appreciation_id,
                    "userId": {"in": list(to_remove)},
                }
            )
        for uid in to_add:
            await db.appreciationrecipient.create(
                data={"appreciationId": appreciation_id, "userId": uid}
            )

    if update_data:
        updated = await db.appreciation.update(
            where={"id": appreciation_id},
            data=update_data,
            include=APPRECIATION_INCLUDE,
        )
    else:
        updated = await db.appreciation.find_unique(
            where={"id": appreciation_id},
            include=APPRECIATION_INCLUDE,
        )

    return _serialize_appreciation(updated)


async def delete_appreciation(current_user, appreciation_id: str) -> dict:
    appreciation = await db.appreciation.find_unique(where={"id": appreciation_id})
    if not appreciation or appreciation.deletedAt is not None:
        raise AppException(404, "Appreciation not found")
    if appreciation.senderId != current_user.id:
        raise AppException(403, "You can only delete your own appreciations")

    now = datetime.now(timezone.utc)
    await db.appreciation.update(
        where={"id": appreciation_id},
        data={"deletedAt": now},
    )
    return DeleteAppreciationResponse(
        deletedAppreciationId=appreciation_id
    ).model_dump(mode="json")


async def mark_seen(current_user, appreciation_id: str) -> dict:
    appreciation = await db.appreciation.find_unique(where={"id": appreciation_id})
    if not appreciation or appreciation.deletedAt is not None:
        raise AppException(404, "Appreciation not found")

    recipient = await db.appreciationrecipient.find_first(
        where={"appreciationId": appreciation_id, "userId": current_user.id}
    )
    if not recipient:
        raise AppException(403, "You are not a recipient of this appreciation")

    if recipient.seenAt is not None:
        return MarkSeenResponse(
            appreciationId=appreciation_id,
            seenAt=recipient.seenAt,
        ).model_dump(mode="json")

    now = datetime.now(timezone.utc)
    await db.appreciationrecipient.update(
        where={"id": recipient.id},
        data={"seenAt": now},
    )
    return MarkSeenResponse(
        appreciationId=appreciation_id,
        seenAt=now,
    ).model_dump(mode="json")