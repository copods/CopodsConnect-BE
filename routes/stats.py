from fastapi import APIRouter, Depends, Query
from middlewares.auth import require_admin
from services import stats_service
from utils.ApiResponse import api_response

stats_router = APIRouter(
    prefix="/stats",
    tags=["Stats"],
    dependencies=[Depends(require_admin)],
)

# ── Overview ──────────────────────────────────────────────────────────────────

@stats_router.get("/overview")
async def get_overview():
    data = await stats_service.get_overview_stats()
    return api_response(200, data, "Overview stats fetched successfully")

# ── Participation leaderboard (Section 3C) ────────────────────────────────────

@stats_router.get("/leaderboards/participation")
async def get_participation_leaderboard(period: str = Query(default="monthly", pattern="^(monthly|all_time)$")):
    data = await stats_service.get_participation_leaderboard(period)
    return api_response(200, data, "Participation leaderboard fetched")

# ── Section 9 — admin-triggered recognition post ──────────────────────────────

@stats_router.get("/leaderboards/participation/preview-post")
async def preview_participation_post(period: str = Query(default="monthly", pattern="^(monthly|all_time)$")):
    """Returns the draft post content without writing anything to the DB."""
    data = await stats_service.get_participation_post_preview(period)
    if data is None:
        return api_response(200, None, "No activity this month — no post to preview")
    return api_response(200, data, "Preview ready")

@stats_router.post("/leaderboards/participation/create-post")
async def create_participation_post(
    period: str = Query(default="monthly", pattern="^(monthly|all_time)$"),
    admin=Depends(require_admin)
):
    """Creates the system recognition post. Only fires on explicit admin confirmation."""
    data = await stats_service.create_participation_recognition_post(admin_id=admin.id, period=period)
    if data is None:
        return api_response(200, None, "No activity this month — nothing posted")
    return api_response(200, data, "Recognition post created successfully")

# ── Engagement leaderboards (Section 4) ───────────────────────────────────────

@stats_router.get("/leaderboards/engagement")
async def get_engagement_leaderboards(period: str = Query(default="monthly", pattern="^(monthly|all_time)$")):
    data = await stats_service.get_engagement_leaderboards(period)
    return api_response(200, data, "Engagement leaderboards fetched")

# ── Culture leaderboards (unchanged) ─────────────────────────────────────────

@stats_router.get("/leaderboards/culture")
async def get_culture_leaderboards():
    data = await stats_service.get_culture_leaderboards()
    return api_response(200, data, "Culture leaderboards fetched")

# ── Moderation leaderboards — kept so no existing callers 404 ─────────────────

@stats_router.get("/leaderboards/moderation")
async def get_moderation_leaderboards():
    data = await stats_service.get_moderation_leaderboards()
    return api_response(200, data, "Moderation leaderboards fetched")

# ── Activity heatmap — kept so no existing callers 404 ───────────────────────

@stats_router.get("/activity-heatmap")
async def get_activity_heatmap(type: str = Query(default="all")):
    data = await stats_service.get_activity_heatmap(type)
    return api_response(200, data, "Activity heatmap fetched")

# ── Cross-role connections ────────────────────────────────────────────────────

@stats_router.get("/cross-role")
async def get_cross_role():
    data = await stats_service.get_cross_role_connections()
    return api_response(200, data, "Cross-role connections fetched")

# ── Appreciation leaderboards (Section 6) ────────────────────────────────────

@stats_router.get("/leaderboards/appreciations")
async def get_appreciation_leaderboards(period: str = Query(default="monthly", pattern="^(monthly|all_time)$")):
    data = await stats_service.get_appreciation_leaderboards(period)
    return api_response(200, data, "Appreciation leaderboards fetched")

# ── User-specific stats (unchanged) ──────────────────────────────────────────

@stats_router.get("/user/{user_id}")
async def get_user_stats(user_id: str):
    data = await stats_service.get_user_stats(user_id)
    return api_response(200, data, "User stats fetched")

@stats_router.get("/user/{user_id}/posts")
async def get_user_posts(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1),
    type: str | None = Query(default=None),
):
    data = await stats_service.get_user_posts(user_id, page, page_size, type)
    return api_response(200, data, "User posts fetched")
