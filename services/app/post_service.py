import asyncio
import math
from datetime import datetime, timezone

from db.client import db
from prisma.enums import PostType, ContentStatus, FlagReason
from utils.exceptions import AppException
from constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from models.schemas.app.posts import (
    PostOut,
    PostDetailOut,
    MediaOut,
    TagOut,
    AuthorOut,
    CommentOut,
)

POST_INCLUDE = {
    "author": True,
    "media": {"order_by": {"order": "asc"}},
    "tags": {"include": {"taggedUser": True}},
    "likes": True,
    "comments": {
        "where": {"deletedAt": None, "parentId": None, "status": {"not": ContentStatus.REMOVED}},
        "include": {
            "author": True,
            "replies": {
                "where": {"deletedAt": None, "status": {"not": ContentStatus.REMOVED}},
                "include": {"author": True},
                "order_by": {"createdAt": "asc"},
            },
        },
        "order_by": {"createdAt": "asc"},
    },
}

FEED_INCLUDE = {
    "author": True,
    "media": {"order_by": {"order": "asc"}},
    "tags": {"include": {"taggedUser": True}},
    "likes": True,
    "_count": {"select": {"comments": True}},
}


# ── Serializers ───────────────────────────────────────────────

def _serialize_author(user) -> AuthorOut | None:
    if not user:
        return None
    return AuthorOut(
        id=user.id,
        name=user.name,
        picture=user.picture,
        designation=user.designation,
    )


def _serialize_tag(tag) -> TagOut:
    user = getattr(tag, "taggedUser", None)
    return TagOut(
        id=tag.id,
        taggedUserId=tag.taggedUserId,
        taggedUserName=user.name if user else None,
        taggedUserPicture=user.picture if user else None,
    )


def _serialize_comment(comment) -> CommentOut:
    replies = getattr(comment, "replies", []) or []
    return CommentOut(
        id=comment.id,
        body=comment.body,
        authorId=comment.authorId,
        parentId=comment.parentId,
        status=str(comment.status),
        createdAt=comment.createdAt,
        updatedAt=comment.updatedAt,
        author=_serialize_author(getattr(comment, "author", None)),
        replies=[_serialize_comment(r) for r in replies],
    )


def _serialize_post(post, current_user_id: str, include_comments: bool = False) -> dict:
    likes = getattr(post, "likes", []) or []
    comments_rel = getattr(post, "comments", []) or []
    media = getattr(post, "media", []) or []
    tags = getattr(post, "tags", []) or []

    count_obj = getattr(post, "_count", None)
    comment_count = count_obj.get("comments", 0) if isinstance(count_obj, dict) else len(comments_rel)

    data = PostDetailOut if include_comments else PostOut
    payload = {
        "id": post.id,
        "type": str(post.type),
        "caption": post.caption,
        "status": str(post.status),
        "sourceUrl": post.sourceUrl,
        "createdAt": post.createdAt,
        "updatedAt": post.updatedAt,
        "authorId": post.authorId,
        "author": _serialize_author(getattr(post, "author", None)),
        "media": [MediaOut.model_validate(m) for m in media],
        "tags": [_serialize_tag(t) for t in tags],
        "likeCount": len(likes),
        "commentCount": comment_count,
        "isLikedByMe": any(like.userId == current_user_id for like in likes),
    }
    if include_comments:
        payload["comments"] = [_serialize_comment(c) for c in comments_rel]

    return data(**payload).model_dump()


# ── CRUD: Posts ───────────────────────────────────────────────

async def create_post(current_user, body) -> dict:
    valid_types = {e.value for e in PostType}
    if body.type not in valid_types:
        raise AppException(400, f"Invalid post type. Must be one of: {', '.join(sorted(valid_types))}")

    post = await db.post.create(
        data={
            "authorId": current_user.id,
            "caption": body.caption,
            "type": PostType[body.type],
            "status": ContentStatus.PUBLISHED,
            "media": {
                "create": [
                    {"url": m.url, "order": m.order, "altText": m.altText}
                    for m in body.media
                ]
            } if body.media else None,
            "tags": {
                "create": [
                    {"taggedUserId": uid}
                    for uid in body.taggedUserIds
                ]
            } if body.taggedUserIds else None,
        },
        include=POST_INCLUDE,
    )
    return _serialize_post(post, current_user.id, include_comments=True)


async def get_feed(
    current_user,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    post_type: str | None = None,
    author_id: str | None = None,
) -> dict:
    page_size = min(page_size, MAX_PAGE_SIZE)
    skip = (page - 1) * page_size

    where: dict = {
        "deletedAt": None,
        "status": {"in": [ContentStatus.PUBLISHED, ContentStatus.PENDING_SCAN]},
    }
    if post_type:
        where["type"] = PostType[post_type]
    if author_id:
        where["authorId"] = author_id

    total, posts = await asyncio.gather(
        db.post.count(where=where),
        db.post.find_many(
            where=where,
            skip=skip,
            take=page_size,
            order={"createdAt": "desc"},
            include=FEED_INCLUDE,
        ),
    )

    total_pages = math.ceil(total / page_size) if total else 0

    return {
        "posts": [_serialize_post(p, current_user.id) for p in posts],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


async def get_post(current_user, post_id: str) -> dict:
    post = await db.post.find_unique(
        where={"id": post_id},
        include=POST_INCLUDE,
    )
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.status == ContentStatus.REMOVED:
        raise AppException(404, "Post not found")
    return _serialize_post(post, current_user.id, include_comments=True)


async def update_post(current_user, post_id: str, body) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.authorId != current_user.id:
        raise AppException(403, "You can only edit your own posts")

    updated = await db.post.update(
        where={"id": post_id},
        data={"caption": body.caption},
        include=POST_INCLUDE,
    )
    return _serialize_post(updated, current_user.id, include_comments=True)


async def delete_post(current_user, post_id: str) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.authorId != current_user.id:
        raise AppException(403, "You can only delete your own posts")

    now = datetime.now(timezone.utc)
    await db.post.update(
        where={"id": post_id},
        data={
            "deletedAt": now,
            "status": ContentStatus.REMOVED,
            "flagReason": FlagReason.NORMAL,
        },
    )
    return {"deletedPostId": post_id}


# ── Likes ─────────────────────────────────────────────────────

async def like_post(current_user, post_id: str) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")

    existing = await db.like.find_first(
        where={"postId": post_id, "userId": current_user.id}
    )
    if existing:
        raise AppException(400, "You have already liked this post")

    await db.like.create(data={"postId": post_id, "userId": current_user.id})
    count = await db.like.count(where={"postId": post_id})
    return {"postId": post_id, "liked": True, "likeCount": count}


async def unlike_post(current_user, post_id: str) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")

    existing = await db.like.find_first(
        where={"postId": post_id, "userId": current_user.id}
    )
    if not existing:
        raise AppException(400, "You have not liked this post")

    await db.like.delete(where={"id": existing.id})
    count = await db.like.count(where={"postId": post_id})
    return {"postId": post_id, "liked": False, "likeCount": count}


# ── Comments ──────────────────────────────────────────────────

async def create_comment(current_user, post_id: str, body) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")

    if body.parentId:
        parent = await db.comment.find_unique(where={"id": body.parentId})
        if not parent or parent.postId != post_id or parent.deletedAt is not None:
            raise AppException(404, "Parent comment not found")
        if parent.parentId is not None:
            raise AppException(400, "Replies can only be one level deep")

    comment = await db.comment.create(
        data={
            "postId": post_id,
            "authorId": current_user.id,
            "body": body.body,
            "parentId": body.parentId,
            "status": ContentStatus.PUBLISHED,
        },
        include={"author": True, "replies": {"include": {"author": True}}},
    )
    return _serialize_comment(comment).model_dump()


async def update_comment(current_user, comment_id: str, body) -> dict:
    comment = await db.comment.find_unique(where={"id": comment_id})
    if not comment or comment.deletedAt is not None:
        raise AppException(404, "Comment not found")
    if comment.authorId != current_user.id:
        raise AppException(403, "You can only edit your own comments")

    updated = await db.comment.update(
        where={"id": comment_id},
        data={"body": body.body},
        include={"author": True, "replies": {"include": {"author": True}}},
    )
    return _serialize_comment(updated).model_dump()


async def delete_comment(current_user, comment_id: str) -> dict:
    comment = await db.comment.find_unique(where={"id": comment_id})
    if not comment or comment.deletedAt is not None:
        raise AppException(404, "Comment not found")
    if comment.authorId != current_user.id:
        raise AppException(403, "You can only delete your own comments")

    now = datetime.now(timezone.utc)
    await db.comment.update(
        where={"id": comment_id},
        data={
            "deletedAt": now,
            "status": ContentStatus.REMOVED,
            "flagReason": FlagReason.NORMAL,
        },
    )
    return {"deletedCommentId": comment_id}
