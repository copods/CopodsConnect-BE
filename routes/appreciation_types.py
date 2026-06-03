from fastapi import APIRouter, Depends

from middlewares.auth import require_admin
from services import appreciation_type_service
from utils.ApiResponse import api_response
from models.schemas.appreciation_types import (
    CreateAppreciationTypeRequest,
    UpdateAppreciationTypeRequest,
)

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
async def create_type(body: CreateAppreciationTypeRequest):
    result = await appreciation_type_service.create_type(body)
    return api_response(201, result, "Appreciation type created successfully")


@appreciation_types_router.patch("/{type_id}")
async def update_type(type_id: str, body: UpdateAppreciationTypeRequest):
    result = await appreciation_type_service.update_type(type_id, body)
    return api_response(200, result, "Appreciation type updated successfully")


@appreciation_types_router.delete("/{type_id}")
async def delete_type(type_id: str):
    result = await appreciation_type_service.delete_type(type_id)
    return api_response(200, result, "Appreciation type deactivated successfully")