# routes/polls.py
"""
Panel-side poll moderation.
Reuses poll_service.close_poll/reopen_poll directly — _assert_can_manage_poll
already allows ADMIN/SUPER_ADMIN regardless of who created the poll, so no
separate admin-specific service function is needed.

NOTE: Panel-side poll *creation* is intentionally out of scope for now —
see comment in CreatePostRequest / create_post() flow. The app-only
require_platform("app") dependency on posts_router already enforces this;
when panel-side poll creation is added later, it'll need its own request
DTO and route here rather than reusing CreatePostRequest as-is, since the
panel would be creating on behalf of "the org" rather than a single user.
"""
from fastapi import APIRouter, Depends, Query
from db.client import db
from prisma.enums import PostType 
from middlewares.auth import require_admin, require_platform
from services.app import poll_service
from utils.ApiResponse import api_response

panel_polls_router = APIRouter(
    prefix="/posts",
    tags=["Panel — Polls"],
    dependencies=[Depends(require_platform("panel"))],
)


@panel_polls_router.patch("/{post_id}/close")
async def admin_close_poll(
    post_id: str,
    current_user=Depends(require_admin),
):
    result = await poll_service.close_poll(current_user, post_id)
    return api_response(200, result, "Poll closed by admin")


@panel_polls_router.patch("/{post_id}/reopen")
async def admin_reopen_poll(
    post_id: str,
    current_user=Depends(require_admin),
):
    result = await poll_service.reopen_poll(current_user, post_id)
    return api_response(200, result, "Poll reopened by admin")

@panel_polls_router.get("")
async def get_all_polls_for_panel(
    page: int = Query(default=1, ge=1), 
    page_size: int = Query(default=25, ge=1),
    current_user = Depends(require_admin),
):
    posts = await db.post.find_many(
        where={
            "type":PostType.POLL , 
            "deletedAt":None
        },
        include={
            "author":True,
            "poll": {
                "include" : {"options":True}
            }
        },
        order={"createdAt":"desc"},
        skip=(page -1) * page_size,
        take=page_size
    )

    total = await db.post.count(
        where={"type": PostType.POLL , "deletedAt":None}
    )

    data ={
        "posts": [p.model_dump(mode="json") for p in posts],
        "total": total,
        "page" : page,
        "pageSize": page_size
    }

    return api_response(200, data, "All polls fetched for panenl")