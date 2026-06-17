#services/app/post_service.py
from datetime import datetime, timezone
from services.audit_service import write_audit_log
from prisma.enums import AuditActorType, AuditEntityType, AuditEventType

from db.client import db
from prisma.enums import PostType, ContentStatus, FlagReason
from utils.exceptions import AppException
from constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from models.schemas.app.posts import (
    PostOut,
    PostDetailOut,
    MediaOut,
    TagOut,
    CommentTagOut,
    AuthorOut,
    CommentOut,
    FeedResponse,
    LikeResponse,
    DeletePostResponse,
    DeleteCommentResponse,
)
from services.app import storage_service
from fastapi import BackgroundTasks
from services.moderation_service import scan_text, scan_images
from services.alert_service import create_alert
from constants import MODERATION_REVIEW_THRESHOLD

POST_INCLUDE = {
    "author": True,
    "media": {"order_by": {"order": "asc"}},
    "tags": {"include": {"taggedUser": True}},
    "likes": True,
    "comments": {
        "where": {"deletedAt": None, "parentId": None, "status": {"equals": ContentStatus.PUBLISHED}},
        "include": {
            "author": True,
            "tags": {"include": {"taggedUser": True}},
            "replies": {
                "where": {"deletedAt": None, "status": {"equals": ContentStatus.PUBLISHED}},
                "include": {
                    "author": True,
                    "tags": {"include": {"taggedUser": True}},
                },
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
    "status": {"equals": ContentStatus.PUBLISHED},
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

def _serialize_comment_tag(tag) -> CommentTagOut:
    user = getattr(tag, "taggedUser", None)
    return CommentTagOut(
        id=tag.id,
        taggedUserId=tag.taggedUserId,
        taggedUserName=user.name if user else None,
        taggedUserPicture=user.picture if user else None,
    )

def _serialize_comment(comment) -> CommentOut:
    replies = getattr(comment, "replies", []) or []
    tags = getattr(comment, "tags", []) or []
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
        tags=[_serialize_comment_tag(t) for t in tags],
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

async def create_post(current_user, body, background_tasks: BackgroundTasks) -> dict:
    for m in body.media:
        storage_service.assert_allowed_post_media_url(m.url)

    create_data: dict = {
        "caption": body.caption,
        "type": body.type,
        "status": ContentStatus.PENDING_SCAN,
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
    await write_audit_log(
        event_type=AuditEventType.POST_CREATED,
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.POST,
        entity_id=post.id,
        metadata={
            "caption": body.caption[:80] if body.caption else None,
            "postType": str(post.type),
        },
    )

    background_tasks.add_task(_scan_post, post.id, current_user.id, body.caption, body.media)

    return _serialize_post(post, current_user.id, include_comments=False)

async def _scan_post(post_id: str, author_id: str, caption: str | None, media: list) -> None:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    try:
        text_score, text_reason = await scan_text(caption) if caption else (0.0, None)
        image_urls = [m.url for m in media] if media else []
        image_score, image_reason = await scan_images(image_urls) if image_urls else (0.0, None)
    except Exception as e:
        # If moderation API fails for any reason, publish the post so it
        # doesn't get stuck in PENDING_SCAN forever. Log for visibility.
        print(f"[moderation] scan failed for post {post_id}: {e}")
        await db.post.update(
            where={"id": post_id},
            data={"status": ContentStatus.PUBLISHED},
        )
        return

    score = max(text_score, image_score)
    flag_reason = (
        FlagReason.NSFW_IMAGE if image_score >= text_score else FlagReason.NSFW_TEXT
    ) if score >= MODERATION_REVIEW_THRESHOLD else None

    if score >= MODERATION_REVIEW_THRESHOLD:
        await db.post.update(
            where={"id": post_id},
            data={
                "status": ContentStatus.FLAGGED,
                "flagReason": flag_reason,
                "flaggedAt": now,
            },
        )
        await create_alert(post_id=post_id, author_id=author_id,
        flag_details={
            "text_score": text_score,
            "image_score": image_score,
            "reason": flag_reason.value if flag_reason else None,
        })
        await write_audit_log(
            event_type=AuditEventType.POST_SCAN_COMPLETED,
            actor_type=AuditActorType.SYSTEM,
            entity_type=AuditEntityType.POST,
            entity_id=post_id,
            metadata={
                "finalStatus": "FLAGGED",
                "postAuthorId": author_id,
                "textScore": text_score,
                "imageScore": image_score,
                "flagReason": flag_reason.value if flag_reason else None,
            },
        )

    else:
        post = await db.post.update(
            where={"id": post_id},
            data={"status": ContentStatus.PUBLISHED},
            include={"tags": True},
        )
        await write_audit_log(
            event_type=AuditEventType.POST_SCAN_COMPLETED,
            actor_type=AuditActorType.SYSTEM,
            entity_type=AuditEntityType.POST,
            entity_id=post_id,
            metadata={
                "finalStatus": "PUBLISHED",
                "postAuthorId": author_id,
                "textScore": text_score,
                "imageScore": image_score,
            },
        )
        # Write a USER_TAGGED_IN_POST audit event per tag.
        # The notification engine will fan out notifications from these.
        if post.type == PostType.USER_POST and post.tags:
            for tag in post.tags:
                await write_audit_log(
                    event_type=AuditEventType.USER_TAGGED_IN_POST,
                    actor_type=AuditActorType.USER,
                    actor_id=author_id,
                    entity_type=AuditEntityType.POST,
                    entity_id=post_id,
                    metadata={
                        "taggedUserId": tag.taggedUserId,
                        "postCaption": post.caption[:80] if post.caption else None,
                    },
                )


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
    await write_audit_log(
        event_type=AuditEventType.POST_DELETED_BY_AUTHOR,
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.POST,
        entity_id=post_id,
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

    # Notify post author — skipped internally if liker == author
    await write_audit_log(
        event_type=AuditEventType.POST_LIKED,
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.LIKE,
        entity_id=post_id,
        metadata={
            "postAuthorId":post.authorId,
            "postCaption":post.caption[:80] if post.caption else None
        },
    )

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
        parent_id = parent.parentId if parent.parentId is not None else body.parentId
    else:
        parent_id = None

    # Validate tagged user IDs exist
    if body.taggedUserIds:
        tagged_users = await db.user.find_many(
            where={
                "id": {"in": body.taggedUserIds},
                "deletedAt": None,
                "hasLoggedInApp": True,
            }
        )
        valid_tagged_ids = [u.id for u in tagged_users]
    else:
        valid_tagged_ids = []

    COMMENT_INCLUDE = {
        "author": True,
        "tags": {"include": {"taggedUser": True}},
        "replies": {
            "include": {
                "author": True,
                "tags": {"include": {"taggedUser": True}},
            }
        },
    }

    now = datetime.now(timezone.utc)
    text_score, text_reason = await scan_text(body.body)

    tag_create = [{"taggedUserId": uid} for uid in valid_tagged_ids]

    if text_score >= MODERATION_REVIEW_THRESHOLD:
        comment = await db.comment.create(
            data={
                "postId": post_id,
                "authorId": current_user.id,
                "body": body.body,
                "parentId": parent_id,
                "status": ContentStatus.FLAGGED,
                "flagReason": FlagReason.NSFW_TEXT,
                "flaggedAt": now,
                **({"tags": {"create": tag_create}} if tag_create else {}),
            },
            include=COMMENT_INCLUDE,
        )
        await create_alert(
            comment_id=comment.id,
            post_id=post_id, author_id=current_user.id, flag_details={
            "text_score": text_score,
            "reason": FlagReason.NSFW_TEXT.value,
        })
        return _serialize_comment(comment).model_dump(mode="json")
    else:
        comment = await db.comment.create(
            data={
                "postId": post_id,
                "authorId": current_user.id,
                "body": body.body,
                "parentId": parent_id,
                "status": ContentStatus.PUBLISHED,
                **({"tags": {"create": tag_create}} if tag_create else {}),
            },
            include=COMMENT_INCLUDE,
        )

        # Resolve parent comment to get its author id for the metadata
        parent_comment = None
        if parent_id:
            parent_comment = await db.comment.find_unique(where={"id": parent_id})

        await write_audit_log(
            event_type=AuditEventType.COMMENT_CREATED,
            actor_type=AuditActorType.USER,
            actor_id=current_user.id,
            entity_type=AuditEntityType.COMMENT,
            entity_id=comment.id,
            parent_entity_type=AuditEntityType.POST,
            parent_entity_id=post_id,
            metadata={
                "postAuthorId": post.authorId,
                "parentCommentId": parent_id,
                "parentCommentAuthorId": parent_comment.authorId if parent_comment else None,
                "commentSnippet": body.body[:80],
            },
        )

        # One audit event per tagged user — notification engine fans out per event
        for uid in valid_tagged_ids:
            await write_audit_log(
                event_type=AuditEventType.USER_TAGGED_IN_COMMENT,
                actor_type=AuditActorType.USER,
                actor_id=current_user.id,
                entity_type=AuditEntityType.COMMENT,
                entity_id=comment.id,
                parent_entity_type=AuditEntityType.POST,
                parent_entity_id=post_id,
                metadata={
                    "taggedUserId": uid,
                    "postId": post_id,
                    "commentSnippet": body.body[:80],
                },
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
        include={
            "author": True,
            "tags": {"include": {"taggedUser": True}},
            "replies": {
                "include": {
                    "author": True,
                    "tags": {"include": {"taggedUser": True}},
                }
            },
        },
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
    await write_audit_log(
        event_type=AuditEventType.COMMENT_DELETED_BY_AUTHOR,
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.COMMENT,
        entity_id=comment_id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=comment.postId,
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