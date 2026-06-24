# services/appreciation_type_service.py
import asyncio
import os
from db.client import db
from utils.exceptions import AppException
from models.schemas.appreciation_types import (
    AppreciationTypeOut,
    AppreciationTypeCreate,
    AppreciationTypeUpdate,
    AppreciationTypeReorderBody,
)

SVG_DIR = os.path.join("public", "assets", "appreciation-emojis")


# ── Serializer ────────────────────────────────────────────────

def _serialize_type(t) -> dict:
    return AppreciationTypeOut(
        id=t.id,
        name=t.name,
        emojiPath=t.emojiPath,
        description=t.description,
        isActive=t.isActive,
        displayOrder=t.displayOrder,
        createdAt=t.createdAt,
        updatedAt=t.updatedAt,
    ).model_dump(mode="json")


# ── Unique name guard ──────────────────────────────────────────

def _is_unique_constraint_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "unique constraint" in msg or "unique_violation" in msg or "p2002" in msg


# ── Service functions ─────────────────────────────────────────

async def get_all_types() -> list[dict]:
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
    return _serialize_type(updated)


async def create_type(data: AppreciationTypeCreate) -> dict:
    try:
        created = await db.appreciationtype.create(
            data={
                "name": data.name.strip(),
                "description": data.description.strip() if data.description else None,
                "displayOrder": data.displayOrder if data.displayOrder is not None else 0,
                "emojiPath": "",
            }
        )
        return _serialize_type(created)
    except Exception as exc:
        if _is_unique_constraint_error(exc):
            raise AppException(409, "An appreciation type with this name already exists")
        raise


async def update_type(type_id: str, data: AppreciationTypeUpdate) -> dict:
    existing = await db.appreciationtype.find_unique(where={"id": type_id})
    if not existing:
        raise AppException(404, "Appreciation type not found")

    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name.strip()
    if data.description is not None:
        update_data["description"] = data.description.strip()
    if data.displayOrder is not None:
        update_data["displayOrder"] = data.displayOrder

    if not update_data:
        raise AppException(400, "No fields provided to update")

    try:
        updated = await db.appreciationtype.update(
            where={"id": type_id},
            data=update_data,
        )
        return _serialize_type(updated)
    except Exception as exc:
        if _is_unique_constraint_error(exc):
            raise AppException(409, "An appreciation type with this name already exists")
        raise


async def upload_svg(type_id: str, file_bytes: bytes, filename: str) -> dict:
    existing = await db.appreciationtype.find_unique(where={"id": type_id})
    if not existing:
        raise AppException(404, "Appreciation type not found")

    if not filename.lower().endswith(".svg"):
        raise AppException(400, "Only SVG files are allowed")

    snippet = file_bytes[:512].lower()
    if b"<svg" not in snippet:
        raise AppException(400, "File does not appear to be a valid SVG")

    os.makedirs(SVG_DIR, exist_ok=True)
    file_path = os.path.join(SVG_DIR, f"{type_id}.svg")
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    emoji_path = f"/assets/appreciation-emojis/{type_id}.svg"
    updated = await db.appreciationtype.update(
        where={"id": type_id},
        data={"emojiPath": emoji_path},
    )
    return _serialize_type(updated)


async def reorder_types(body: AppreciationTypeReorderBody) -> list[dict]:
    if not body.items:
        raise AppException(400, "No items provided for reordering")

    ids = [item.id for item in body.items]
    existing = await db.appreciationtype.find_many(where={"id": {"in": ids}})
    existing_ids = {t.id for t in existing}
    missing = [id_ for id_ in ids if id_ not in existing_ids]
    if missing:
        raise AppException(404, f"Appreciation types not found: {', '.join(missing)}")

    for item in body.items:
        await db.appreciationtype.update(
            where={"id": item.id},
            data={"displayOrder": item.displayOrder},
        )


    return await get_all_types()

async def delete_type(type_id: str) -> dict:
    existing = await db.appreciationtype.find_unique(where={"id": type_id})
    if not existing:
        raise AppException(404, "Appreciation type not found")

    # Block deletion if any appreciations have been sent using this type
    usage_count = await db.appreciation.count(
        where={"appreciationTypeId": type_id}
    )
    if usage_count > 0:
        raise AppException(
            409,
            f"Cannot delete — this type has been used in {usage_count} appreciation(s). Disable it instead."
        )

    await db.appreciationtype.delete(where={"id": type_id})
    return {"deletedId": type_id}