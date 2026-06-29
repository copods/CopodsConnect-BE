from fastapi import APIRouter, Depends, Query
from middlewares.auth import require_admin
from services import stats_service
from utils.ApiResponse import api_response

stats_router = APIRouter(
    prefix="/stats",
    tags=["Stats"],
    dependencies=[Depends(require_admin)],
)

@stats_router.get("/overview")
async def get_overview():
    data = await stats_service.get_overview_stats()
    return api_response(200, data, "Overview stats fetched successfully")

@stats_router.get("/leaderboards/engagement")
async def get_engagement_leaderboards():
    data = await stats_service.get_engagement_leaderboards()
    return api_response(200, data, "Engagement leaderboards fetched")

@stats_router.get("/leaderboards/culture")
async def get_culture_leaderboards():
    data = await stats_service.get_culture_leaderboards()
    return api_response(200, data, "Culture leaderboards fetched")

@stats_router.get("/leaderboards/moderation")
async def get_moderation_leaderboards():
    data = await stats_service.get_moderation_leaderboards()
    return api_response(200, data, "Moderation leaderboards fetched")

@stats_router.get("/activity-heatmap")
async def get_activity_heatmap():
    data = await stats_service.get_activity_heatmap()
    return api_response(200, data, "Activity heatmap fetched")

@stats_router.get("/cross-role")
async def get_cross_role():
    data = await stats_service.get_cross_role_connections()
    return api_response(200, data, "Cross-role connections fetched")

@stats_router.get("/user/{user_id}")
async def get_user_stats(user_id: str):
    data = await stats_service.get_user_stats(user_id)
    return api_response(200, data, "User stats fetched")

@stats_router.get("/user/{user_id}/posts")
async def get_user_posts(user_id: str, page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1)):
    data = await stats_service.get_user_posts(user_id, page, page_size)
    return api_response(200, data, "User posts fetched")

@stats_router.get("/leaderboards/appreciations")
async def get_appreciation_leaderboards():
    data = await stats_service.get_appreciation_leaderboards()
    return api_response(200, data, "Appreciation leaderboards fetched")
