from fastapi import APIRouter, Depends, Query

from middlewares.auth import get_current_user, require_platform
from services.app import appreciation_service
from utils.ApiResponse import api_response
from constants import DEFAULT_PAGE_SIZE
from models.schemas.app.appreciations import (
    CreateAppreciationRequest,
    UpdateAppreciationRequest,
)

# Separate router for the types picker — different prefix
appreciation_types_app_router = APIRouter(
    prefix="/app/appreciation-types",
    tags=["App Appreciation Types"],
    dependencies=[Depends(require_platform("app"))],
)

appreciations_router = APIRouter(
    prefix="/app/appreciations",
    tags=["App Appreciations"], 
    dependencies=[Depends(require_platform("app"))],
)


# ── Appreciation types (picker) ───────────────────────────────

@appreciation_types_app_router.get("")
async def get_active_types():
    result = await appreciation_service.get_active_types()
    return api_response(200, result, "Appreciation types fetched successfully")


# ── Appreciations ─────────────────────────────────────────────

@appreciations_router.post("")
async def create_appreciation(
    body: CreateAppreciationRequest,
    current_user=Depends(get_current_user),
):
    result = await appreciation_service.create_appreciation(current_user, body)
    return api_response(201, result, "Appreciation sent successfully")


@appreciations_router.get("")
async def get_sent_appreciations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, alias="pageSize"),
    current_user=Depends(get_current_user),
):
    result = await appreciation_service.get_sent_appreciations(current_user, page, page_size)
    return api_response(200, result, "Sent appreciations fetched successfully")


# NOTE: /received must be declared before /{appreciation_id} to avoid path conflict
@appreciations_router.get("/received")
async def get_received_appreciations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, alias="pageSize"),
    current_user=Depends(get_current_user),
):
    result = await appreciation_service.get_received_appreciations(current_user, page, page_size)
    return api_response(200, result, "Received appreciations fetched successfully")


# NOTE: /{appreciation_id}/seen must be declared before /{appreciation_id}
@appreciations_router.patch("/{appreciation_id}/seen")
async def mark_seen(
    appreciation_id: str,
    current_user=Depends(get_current_user),
):
    result = await appreciation_service.mark_seen(current_user, appreciation_id)
    return api_response(200, result, "Appreciation marked as seen")


@appreciations_router.patch("/{appreciation_id}")
async def update_appreciation(
    appreciation_id: str,
    body: UpdateAppreciationRequest,
    current_user=Depends(get_current_user),
):
    result = await appreciation_service.update_appreciation(current_user, appreciation_id, body)
    return api_response(200, result, "Appreciation updated successfully")


@appreciations_router.delete("/{appreciation_id}")
async def delete_appreciation(
    appreciation_id: str,
    current_user=Depends(get_current_user),
):
    result = await appreciation_service.delete_appreciation(current_user, appreciation_id)
    return api_response(200, result, "Appreciation deleted successfully")