# routes/appreciation_types.py
from fastapi import APIRouter, Depends, UploadFile, File

from middlewares.auth import require_admin
from services import appreciation_type_service
from models.schemas.appreciation_types import (
    AppreciationTypeCreate,
    AppreciationTypeUpdate,
    AppreciationTypeReorderBody,
)
from utils.ApiResponse import api_response

appreciation_types_router = APIRouter(
    prefix="/appreciation-types",
    tags=["Appreciation Types"],
    dependencies=[Depends(require_admin)],
)


@appreciation_types_router.get("")
async def get_all_types():
    result = await appreciation_type_service.get_all_types()
    return api_response(200, result, "Appreciation types fetched successfully")


@appreciation_types_router.post("")
async def create_type(data: AppreciationTypeCreate):
    result = await appreciation_type_service.create_type(data)
    return api_response(201, result, "Appreciation type created successfully")


# NOTE: /reorder MUST be before /{type_id} — otherwise FastAPI
# treats the literal string "reorder" as a type_id value.
@appreciation_types_router.put("/reorder")
async def reorder_types(body: AppreciationTypeReorderBody):
    result = await appreciation_type_service.reorder_types(body)
    return api_response(200, result, "Appreciation types reordered successfully")


@appreciation_types_router.patch("/{type_id}/toggle")
async def toggle_type(type_id: str):
    result = await appreciation_type_service.toggle_type(type_id)
    return api_response(200, result, "Appreciation type toggled successfully")


@appreciation_types_router.patch("/{type_id}")
async def update_type(type_id: str, data: AppreciationTypeUpdate):
    result = await appreciation_type_service.update_type(type_id, data)
    return api_response(200, result, "Appreciation type updated successfully")


@appreciation_types_router.post("/{type_id}/svg")
async def upload_svg(type_id: str, file: UploadFile = File(...)):
    file_bytes = await file.read()
    result = await appreciation_type_service.upload_svg(type_id, file_bytes, file.filename or "")
    return api_response(200, result, "SVG uploaded successfully")

@appreciation_types_router.delete("/{type_id}")
async def delete_type(type_id: str):
    result = await appreciation_type_service.delete_type(type_id)
    return api_response(200, result, "Appreciation type deleted successfully")
