# services/appreciation_type_service.py
from db.client import db
from utils.exceptions import AppException
from models.schemas.appreciation_types import AppreciationTypeOut


# ── Serializer ────────────────────────────────────────────────

def _serialize_type(t) -> AppreciationTypeOut:
    return AppreciationTypeOut(
        id=t.id,
        name=t.name,
        emojiPath=t.emojiPath,
        badgePath=t.badgePath,
        description=t.description,
        isActive=t.isActive,
        displayOrder=t.displayOrder,
        createdAt=t.createdAt,
        updatedAt=t.updatedAt,
    )


# ── Service functions ─────────────────────────────────────────

async def get_all_types() -> list[AppreciationTypeOut]:
    types = await db.appreciationtype.find_many(
        order={"displayOrder": "asc"}
    )
    return [_serialize_type(t) for t in types]


async def toggle_type(type_id: str) -> dict:
    existing = await db.appreciationtype.find_unique(where={"id": type_id})
    if not existing:
        raise AppException(404, "Appreciation type not found")

    updated = await db.appreciationtype.update(
        where={"id": type_id},
        data={"isActive": not existing.isActive},
    )
    return _serialize_type(updated).model_dump(mode="json")