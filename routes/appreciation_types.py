# routes/appreciation_types.py
from fastapi import APIRouter, Depends

from middlewares.auth import require_admin
from services import appreciation_type_service
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


@appreciation_types_router.patch("/{type_id}/toggle")
async def toggle_type(type_id: str):
    result = await appreciation_type_service.toggle_type(type_id)
    return api_response(200, result, "Appreciation type toggled successfully")