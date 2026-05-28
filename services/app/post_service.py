#services/app/post_service.py
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
    FeedResponse,
    LikeResponse,
    DeletePostResponse,
    DeleteCommentResponse,
)
from services.app import storage_service

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
    # "_count": {"select": {"comments": True}},
}

COMMENT_COUNT_WHERE = {
    "deletedAt": None,
    "status": {"not": ContentStatus.REMOVED},
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
        status=comment.status,
        createdAt=comment.createdAt,
        updatedAt=comment.updatedAt,
        author=_serialize_author(getattr(comment, "author", None)),
        replies=[_serialize_comment(r) for r in replies],
    )



def _serialize_post(
    post,
    current_user_id: str,
    include_comments: bool = False,
    comment_count: int | None = None,
) -> dict:
    likes = getattr(post, "likes", []) or []
    comments_rel = getattr(post, "comments", []) or []
    media = getattr(post, "media", []) or []
    tags = getattr(post, "tags", []) or []

    if comment_count is None:
        count_obj = getattr(post, "_count", None)
        comment_count = (
            getattr(count_obj, "comments", None) if count_obj else len(comments_rel)
        )
        if comment_count is None:
            comment_count = 0

    payload = {
        "id": post.id,
        "type": post.type,
        "caption": post.caption,
        "status": post.status,
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
        return PostDetailOut(**payload).model_dump(mode="json")

    return PostOut(**payload).model_dump(mode="json")


# ── CRUD: Posts ───────────────────────────────────────────────

async def create_post(current_user, body) -> dict:
    for m in body.media:
        storage_service.assert_allowed_post_media_url(m.url)

    create_data: dict = {
        "caption": body.caption,
        "type": body.type,
        "status": ContentStatus.PUBLISHED,
        "author": {"connect": {"id": current_user.id}},
    }

    if body.media:
        create_data["media"] = {
            "create": [
                {"url": m.url, "order": m.order, "altText": m.altText}
                for m in body.media
            ],
        }

    if body.taggedUserIds:
        create_data["tags"] = {
            "create": [{"taggedUserId": uid} for uid in body.taggedUserIds],
        }

    post = await db.post.create(
        data=create_data,
        include=FEED_INCLUDE,
    )

    return _serialize_post(post, current_user.id, include_comments=False)


async def get_feed(
    current_user,
    cursor: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    post_type: PostType | None = None,
    author_id: str | None = None,
) -> dict:
    page_size = min(page_size, MAX_PAGE_SIZE)

    where: dict = {
        "deletedAt": None,
        "status": ContentStatus.PUBLISHED,
    }

    if post_type:
        where["type"] = post_type
    if author_id:
        where["authorId"] = author_id

    posts = await db.post.find_many(
        where=where,
        take=page_size+1, 
        skip=1 if cursor else 0, 
        cursor={"id":cursor} if cursor else None, 
        order={"createdAt": "desc"},
        include=FEED_INCLUDE,
    )

    has_more = len(posts) > page_size
    if has_more:
        posts = posts[:page_size]
    
    next_cursor = posts[-1].id if has_more else None 
    post_ids = [p.id for p in posts]
    comment_counts = await _comment_counts_for_posts(post_ids)
    return FeedResponse(
        posts=[
            _serialize_post(
                p,
                current_user.id,
                comment_count=comment_counts.get(p.id, 0),
            )
            for p in posts
        ],
        nextCursor=next_cursor,
        hasMore=has_more,
    ).model_dump(mode="json")


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
    if post.status == ContentStatus.REMOVED:
        raise AppException(400, "Post is removed")
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
    if post.status == ContentStatus.REMOVED:
        raise AppException(400, "Post is removed")
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
    return DeletePostResponse(deletedPostId=post_id).model_dump(mode="json")


# ── Likes ─────────────────────────────────────────────────────

async def like_post(current_user, post_id: str) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.status == ContentStatus.REMOVED:
        raise AppException(400, "Post is removed")
    existing = await db.like.find_first(
        where={"postId": post_id, "userId": current_user.id}
    )
    if existing:
        raise AppException(400, "You have already liked this post")

    await db.like.create(data={"postId": post_id, "userId": current_user.id})
    count = await db.like.count(where={"postId": post_id})
    return LikeResponse(postId=post_id, liked=True, likeCount=count).model_dump(mode="json")


async def unlike_post(current_user, post_id: str) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.status == ContentStatus.REMOVED:
        raise AppException(400, "Post is removed")
    existing = await db.like.find_first(
        where={"postId": post_id, "userId": current_user.id}
    )
    if not existing:
        raise AppException(400, "You have not liked this post")

    await db.like.delete(where={"id": existing.id})
    count = await db.like.count(where={"postId": post_id})
    return LikeResponse(postId=post_id, liked=False, likeCount=count).model_dump(mode="json")


# ── Comments ──────────────────────────────────────────────────

async def create_comment(current_user, post_id: str, body) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.status == ContentStatus.REMOVED:
        raise AppException(400, "Post is removed")

    if body.parentId:
        parent = await db.comment.find_unique(where={"id": body.parentId})
        if not parent or parent.postId != post_id or parent.deletedAt is not None:
            raise AppException(404, "Parent comment not found")
        # if replying to a reply, re-point to the top-level comment
        if parent.parentId is not None:
            parent_id = parent.parentId
        else:
            parent_id = body.parentId
    else:
        parent_id = None

    comment = await db.comment.create(
        data={
            "postId": post_id,
            "authorId": current_user.id,
            "body": body.body,
            "parentId": parent_id,
            "status": ContentStatus.PUBLISHED,
        },
        include={"author": True, "replies": {"include": {"author": True}}},
    )
    return _serialize_comment(comment).model_dump(mode="json")


async def update_comment(current_user, comment_id: str, body) -> dict:
    comment = await db.comment.find_unique(where={"id": comment_id})
    if not comment or comment.deletedAt is not None:
        raise AppException(404, "Comment not found")
    if comment.status == ContentStatus.REMOVED:
        raise AppException(400, "Comment is removed")
    if comment.authorId != current_user.id:
        raise AppException(403, "You can only edit your own comments")

    updated = await db.comment.update(
        where={"id": comment_id},
        data={"body": body.body},
        include={"author": True, "replies": {"include": {"author": True}}},
    )
    return _serialize_comment(updated).model_dump(mode="json")


async def delete_comment(current_user, comment_id: str) -> dict:
    comment = await db.comment.find_unique(where={"id": comment_id})
    if not comment or comment.deletedAt is not None:
        raise AppException(404, "Comment not found")
    if comment.status == ContentStatus.REMOVED:
        raise AppException(400, "Comment is removed")
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
    return DeleteCommentResponse(deletedCommentId=comment_id).model_dump(mode="json")

async def _comment_counts_for_posts(post_ids: list[str]) -> dict[str, int]:
    if not post_ids:
        return {}
    rows = await db.comment.group_by(
        by=["postId"],
        where={
            "postId": {"in": post_ids},
            **COMMENT_COUNT_WHERE,
        },
        count=True,
    )
    counts = {pid: 0 for pid in post_ids}
    for row in rows:
        pid = row["postId"] if isinstance(row, dict) else row.postId
        cnt_obj = row["_count"] if isinstance(row, dict) else row._count
        counts[pid] = cnt_obj["_all"] if isinstance(cnt_obj, dict) else cnt_obj._all
    return counts    