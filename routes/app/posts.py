#routes/app/posts.py
from db.client import db
from fastapi import APIRouter, Depends, Query
from typing import Optional
from db.client import db
from prisma.enums import Role, ContentStatus, FlagReason
from utils.exceptions import AppException
from middlewares.auth import require_admin
from datetime import datetime, timezone

from middlewares.auth import get_current_user, require_platform
from services.app import post_service, poll_service
from utils.ApiResponse import api_response
from constants import DEFAULT_PAGE_SIZE
from prisma.enums import PostType
from services.app import storage_service
from models.schemas.app.posts import (
    CreatePostRequest,
    UpdatePostRequest,
    CreateCommentRequest,
    UpdateCommentRequest,
    LikePostRequest,
    MediaUploadUrlRequest,
    MediaUploadUrlResponse,
    CastVoteRequest,
    ExtendPollRequest,
)


posts_router = APIRouter(
    prefix="/app/posts",
    tags=["App Posts"],
    dependencies=[Depends(require_platform("app"))],
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
    cursor: Optional[str] = Query(default=None),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, alias="pageSize"),
    post_type: Optional[PostType] = Query(default=None, alias="type"),
    author_id: Optional[str] = Query(default=None, alias="authorId"),
    current_user=Depends(get_current_user),
):
    result = await post_service.get_feed(current_user, cursor, page_size, post_type, author_id)
    return api_response(200, result, "Feed fetched successfully")

@posts_router.post("/media/upload-url")
async def create_media_upload_url(
    body: MediaUploadUrlRequest,
    current_user=Depends(get_current_user),
):
    result = await storage_service.create_post_media_upload_url(
        current_user.id,
        body.contentType,
    )
    return api_response(200, result, "Upload URL created")

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

@posts_router.delete("/{post_id}/admin")
async def admin_delete_post(
    post_id: str, 
    current_user=Depends(require_admin)
):
    post = await db.post.find_unique(where={"id": post_id}, include={"author": True})
    
    if not post:
        raise AppException(404, "Post not found")
    # Hierarchy rule: Admins cannot delete posts made by other admins/super_admins
    if post.author and post.author.role in [Role.ADMIN, Role.SUPER_ADMIN] and current_user.role != Role.SUPER_ADMIN:
        raise AppException(403, "You cannot delete posts authored by another Admin.")
    now = datetime.now(timezone.utc)
    
    # Soft delete the post AND set status to REMOVED
    await db.post.update(
        where={"id": post_id},
        data={"deletedAt": now, "status": ContentStatus.REMOVED, "flagReason": FlagReason.NORMAL}
    )
    
    return api_response(200, None, "Post removed by admin")

# ── Likes ─────────────────────────────────────────────────────

@posts_router.post("/{post_id}/like")
async def like_post(
    post_id: str,
    body:LikePostRequest = LikePostRequest(),
    current_user=Depends(get_current_user),
):
    result = await post_service.like_post(current_user, post_id,body)
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

# ── Polls ─────────────────────────────────────────────────────

@posts_router.post("/{post_id}/vote")
async def cast_vote(
    post_id: str,
    body: CastVoteRequest,
    current_user=Depends(get_current_user),
):
    result = await poll_service.cast_vote(current_user, post_id, body.optionId)
    return api_response(200, result, "Vote recorded")


@posts_router.patch("/{post_id}/close")
async def close_poll(
    post_id: str,
    current_user=Depends(get_current_user),
):
    result = await poll_service.close_poll(current_user, post_id)
    return api_response(200, result, "Poll closed")


@posts_router.patch("/{post_id}/reopen")
async def reopen_poll(
    post_id: str,
    current_user=Depends(get_current_user),
):
    result = await poll_service.reopen_poll(current_user, post_id)
    return api_response(200, result, "Poll reopened")


@posts_router.patch("/{post_id}/extend")
async def extend_poll(
    post_id: str,
    body: ExtendPollRequest,
    current_user=Depends(get_current_user),
):
    result = await poll_service.extend_poll(current_user, post_id, body.newClosesAt)
    return api_response(200, result, "Poll deadline extended")
