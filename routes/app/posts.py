from fastapi import APIRouter, Depends, Query

from middlewares.auth import get_current_user
from services.app import post_service
from utils.ApiResponse import api_response
from constants import DEFAULT_PAGE_SIZE
from models.schemas.app.posts import (
    CreatePostRequest,
    UpdatePostRequest,
    CreateCommentRequest,
    UpdateCommentRequest,
)

posts_router = APIRouter(
    prefix="/app/posts",
    tags=["App Posts"],
    dependencies=[Depends(get_current_user)],
)


# ── Posts CRUD ────────────────────────────────────────────────

@posts_router.post("")
async def create_post(
    body: CreatePostRequest,
    current_user=Depends(get_current_user),
):
    result = await post_service.create_post(current_user, body)
    return api_response(201, result, "Post created successfully")


@posts_router.get("")
async def get_feed(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, alias="pageSize"),
    post_type: str | None = Query(default=None, alias="type"),
    author_id: str | None = Query(default=None, alias="authorId"),
    current_user=Depends(get_current_user),
):
    result = await post_service.get_feed(current_user, page, page_size, post_type, author_id)
    return api_response(200, result, "Feed fetched successfully")


@posts_router.get("/{post_id}")
async def get_post(
    post_id: str,
    current_user=Depends(get_current_user),
):
    result = await post_service.get_post(current_user, post_id)
    return api_response(200, result, "Post fetched successfully")


@posts_router.patch("/{post_id}")
async def update_post(
    post_id: str,
    body: UpdatePostRequest,
    current_user=Depends(get_current_user),
):
    result = await post_service.update_post(current_user, post_id, body)
    return api_response(200, result, "Post updated successfully")


@posts_router.delete("/{post_id}")
async def delete_post(
    post_id: str,
    current_user=Depends(get_current_user),
):
    result = await post_service.delete_post(current_user, post_id)
    return api_response(200, result, "Post deleted successfully")


# ── Likes ─────────────────────────────────────────────────────

@posts_router.post("/{post_id}/like")
async def like_post(
    post_id: str,
    current_user=Depends(get_current_user),
):
    result = await post_service.like_post(current_user, post_id)
    return api_response(200, result, "Post liked")


@posts_router.delete("/{post_id}/like")
async def unlike_post(
    post_id: str,
    current_user=Depends(get_current_user),
):
    result = await post_service.unlike_post(current_user, post_id)
    return api_response(200, result, "Post unliked")


# ── Comments ──────────────────────────────────────────────────

@posts_router.post("/{post_id}/comments")
async def create_comment(
    post_id: str,
    body: CreateCommentRequest,
    current_user=Depends(get_current_user),
):
    result = await post_service.create_comment(current_user, post_id, body)
    return api_response(201, result, "Comment created successfully")


@posts_router.patch("/comments/{comment_id}")
async def update_comment(
    comment_id: str,
    body: UpdateCommentRequest,
    current_user=Depends(get_current_user),
):
    result = await post_service.update_comment(current_user, comment_id, body)
    return api_response(200, result, "Comment updated successfully")


@posts_router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    current_user=Depends(get_current_user),
):
    result = await post_service.delete_comment(current_user, comment_id)
    return api_response(200, result, "Comment deleted successfully")
