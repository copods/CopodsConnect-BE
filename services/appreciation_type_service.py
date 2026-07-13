# services/appreciation_type_service.py
from dataclasses import dataclass
from genericpath import exists
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

async def update_type(type_id: str , data:AppreciationTypeUpdate) -> dict:
    existing = await db.appreciationtype.find_unique(
        where={'id':type_id}
    )
    if not existing:
        raise AppException(404, "Appreciation Type not found")
    
    update_data={}
    if data.name is not None:
        #check if the new name is alread take by another tyoe 
        if data.name != existing.name:
            name_check= await db.appreciationtype.find_unique(
                where={'name':data.name}
            )
            if name_check:
                raise AppException(400, "Appreciation tyoe name already exists")
        
        update_data["name"] = data.name
    
    if data.description is not None:
        update_data["description"] = data.description
    
    if data.displayOrder is not None:
        update_data["displayOrder"] = data.displayOrder
    
    updated = await db.appreciationtype.update(
        where={
            "id":type_id
        },
        data=update_data
    )
    return _serialize_type(updated).model_dump(mode="json")

async def upload_svg(type_id: str, file_bytes: bytes, filename: str) -> dict:
    existing = await db.appreciationtype.find_unique(where={"id": type_id})
    if not existing:
        raise AppException(404, "Appreciation type not found")
        
    # BACKEND VALIDATION: Strictly enforce SVG for icons
    if not filename.lower().endswith('.svg'):
        raise AppException(400, "Only .svg files are allowed for icons")
        
    os.makedirs(SVG_DIR, exist_ok=True)
    
    # NEW PATTERN: Convert "Team Player" to "team_player.svg"
    slug_name = existing.name.lower().replace(" ", "_")
    safe_filename = f"{slug_name}.svg"
    file_path = os.path.join(SVG_DIR, safe_filename)
    
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    rel_path = f"assets/appreciation-emojis/{safe_filename}"
    
    updated = await db.appreciationtype.update(
        where={"id": type_id},
        data={"emojiPath": rel_path},
    )
    return _serialize_type(updated).model_dump(mode="json")


async def upload_badge(type_id: str, file_bytes: bytes, filename: str) -> dict:
    existing = await db.appreciationtype.find_unique(where={"id": type_id})
    if not existing:
        raise AppException(404, "Appreciation type not found")
        
    # BACKEND VALIDATION: Strictly enforce PNG for badges
    if not filename.lower().endswith('.png'):
        raise AppException(400, "Only .png files are allowed for badges")
        
    BADGE_DIR = os.path.join("public", "assets", "appreciation-badges")
    os.makedirs(BADGE_DIR, exist_ok=True)
    
    # NEW PATTERN: Convert "Team Player" to "team_player.png"
    slug_name = existing.name.lower().replace(" ", "_")
    safe_filename = f"{slug_name}.png"
    file_path = os.path.join(BADGE_DIR, safe_filename)
    
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    rel_path = f"assets/appreciation-badges/{safe_filename}"
    
    updated = await db.appreciationtype.update(
        where={"id": type_id},
        data={"badgePath": rel_path},
    )
    return _serialize_type(updated).model_dump(mode="json")

async def reorder_types(body:AppreciationTypeReorderBody)-> list[dict]:
    #update the display order for all items in the array one by one 

    for item in body.items:
        await db.appreciationtype.update(
            where={
                "id":item.id
            },
            data={
                "displayOrder":item.displayOrder + 1
            }
        )
    #Fetch the fresh updated list 
    types = await get_all_types()
    return [t.model_dump(mode="json") for t in types]

async def delete_type(type_id:str)->dict:
    existing = await db.appreciationtype.find_unique(
        where={
            "id":type_id
        }
    )

    if not existing:
        raise AppException(404, "Appreciation type not found")

    #stop the admin from deleting an appreciation type if user have already sent it to each other!
    usage = await db.appreciation.find_first(
        where={
            "appreciationTypeId":type_id
        }
    )
    if usage: 
        raise AppException(400,"Cannot delete type because ir is already used in appreciations.")
    
    await db.appreciationtype.delete(
        where={
            "id":type_id
        }
    )

    return {"deleteId":type_id}
