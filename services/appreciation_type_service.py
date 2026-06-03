from db.client import db
from utils.exceptions import AppException
from models.schemas.appreciation_types import (
    AppreciationTypeOut,
    CreateAppreciationTypeRequest,
    UpdateAppreciationTypeRequest,
)


# ── Serializer ────────────────────────────────────────────────

def _serialize_type(t) -> dict:
    return AppreciationTypeOut(
        id=t.id,
        name=t.name,
        emoji=t.emoji,
        animationUrl=t.animationUrl,
        description=t.description,
        isActive=t.isActive,
        displayOrder=t.displayOrder,
        createdAt=t.createdAt,
        updatedAt=t.updatedAt,
    ).model_dump(mode="json")


# ── CRUD ──────────────────────────────────────────────────────

async def get_all_types() -> list[dict]:
    types = await db.appreciationtype.find_many(
        order={"displayOrder": "asc"}
    )
    return [_serialize_type(t) for t in types]


async def create_type(body: CreateAppreciationTypeRequest) -> dict:
    t = await db.appreciationtype.create(
        data={
            "name": body.name,
            "emoji": body.emoji,
            "animationUrl": body.animationUrl,
            "description": body.description,
            "displayOrder": body.displayOrder,
        }
    )
    return _serialize_type(t)


async def update_type(type_id: str, body: UpdateAppreciationTypeRequest) -> dict:
    existing = await db.appreciationtype.find_unique(where={"id": type_id})
    if not existing:
        raise AppException(404, "Appreciation type not found")

    updates = body.model_dump(exclude_unset=True)
    update_data = {k: v for k, v in updates.items() if v is not None}

    updated = await db.appreciationtype.update(
        where={"id": type_id},
        data=update_data,
    )
    return _serialize_type(updated)


async def delete_type(type_id: str) -> dict:
    existing = await db.appreciationtype.find_unique(where={"id": type_id})
    if not existing:
        raise AppException(404, "Appreciation type not found")

    # If this type has been used in any appreciation, only deactivate it —
    # hard deleting would break the FK on existing appreciation records.
    # If it has never been used, it is safe to hard delete.
    usage_count = await db.appreciation.count(
        where={"appreciationTypeId": type_id}
    )

    if usage_count > 0:
        await db.appreciationtype.update(
            where={"id": type_id},
            data={"isActive": False},
        )
    else:
        await db.appreciationtype.delete(where={"id": type_id})

    return {"deactivatedTypeId": type_id}