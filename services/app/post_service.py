#services/app/post_service.py
import asyncio
from datetime import datetime, timezone
from services.audit_service import write_audit_log
from prisma.enums import AuditActorType, AuditEntityType, AuditEventType
from services.app.appreciation_service import _validate_recipients
from db.client import db
from prisma.enums import PostType, ContentStatus, FlagReason
from utils.exceptions import AppException
from constants import (
    DEFAULT_PAGE_SIZE, 
    MAX_PAGE_SIZE,
    POLL_MIN_OPTIONS,
    POLL_MAX_OPTIONS
)
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
from services.moderation_service import (
    scan_text,
    scan_images,
    check_blacklist,
    check_whitelist,
)
from services.alert_service import create_alert, auto_resolve_alert
from constants import MODERATION_REVIEW_THRESHOLD
from utils.link_preview import fetch_link_metadata


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
    "appreciation": {  
        "include": {
            "appreciationType": True,
            "recipients": {"include": {"user": True}}
        }
    },
    "poll": { # NEW
        "include": {
            "options": {"order_by":{"order":"asc"}},
        }
    }
}

FEED_INCLUDE = {
    "author": True,
    "media": {"order_by": {"order": "asc"}},
    "tags": {"include": {"taggedUser": True}},
    "likes": True,
    "appreciation": {  # NEW
        "include": {
            "appreciationType": True,
            "recipients": {"include": {"user": True}}
        }
    },
    "poll": { # NEW
        "include": {
            "options": {"order_by":{"order":"asc"}},
        }
    }
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

# ── Poll helpers ─────────────────────────────────────────────

def _is_poll_open(poll) -> bool:
    """
    A poll is open unless it was manually closed, or its natural
    deadline has passed. Reopening clears isManuallyClosed but does
    NOT touch closesAt — if closesAt is still in the past after a
    reopen, the poll falls back into "naturally expired" state, which
    is exactly what extend_poll() exists to fix.
    """
    if poll.isManuallyClosed:
        return False
    if poll.closesAt and datetime.now(timezone.utc) >= poll.closesAt: 
        return False
    return True

def _serialize_poll(poll, user_vote_option_id: str | None) -> dict:
    options = sorted(getattr(poll, "options", []) or [], key=lambda o: o.order)
    total_votes = sum(o.voteCount for o in options)
    return {
        "id" : poll.id, 
        "closesAt": poll.closesAt,
        "isManuallyClosed": poll.isManuallyClosed,
        "manuallyClosedAt": poll.manuallyClosedAt,
        "isOpen": _is_poll_open(poll),
        "totalVotes":total_votes,
        "userVoteOptionId": user_vote_option_id,
        "options":[
            {"id": o.id, "text": o.text, "order":o.order, "voteCount": o.voteCount}
            for o in options
        ],
    }

async def _single_user_poll_vote(poll_id:str , user_id:str)-> str | None:
    vote = await db.pollvote.find_first(
        where={
            "pollId": poll_id,
            "userId":user_id
        }
    )
    return vote.optionId if vote else None

async def _user_poll_votes(poll_ids:list[str], user_id:str)-> dict[str,str]:
    """Batch version of _single_user_poll_vote, used in feed serialization."""
    if not poll_ids:
        return {}
    votes = await db.pollvote.find_many(
        where={
            "pollId":{
                "in": poll_ids
            },
            "userId":user_id
        }
    )
    return {v.pollId: v.optionId for v in votes}

def _build_poll_flag_details(body)->dict:
    """
    Captures everything needed to materialize a poll later — used both
    when a poll is queued for AI review AND when it's auto-removed by
    the blacklist, since an admin can restore either case and we need
    the option texts/deadline to reconstruct the Poll/PollOption rows.
    """
    return {
        "pollOptionTexts": body.pollOptions,
        "pollClosesAt": body.pollClosesAt.isoformat() if body.pollClosesAt else None,
    }

async def _serialize_post(
    post,
    current_user_id: str,
    include_comments: bool = False,
    comment_count: int | None = None,
    user_vote_option_id: str | None = None, # NEW: Added for Polls
    link_metadata: list[dict] | None = None,  # Pre-fetched by caller; None triggers self-fetch (single-post path)
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
    
    # Fetch link metadata if not pre-supplied by the caller. 
    # The feed path (get_feed) pre-fetches for all posts concurrently and passes 
    # it in via the link_metadata param to avoid serial waits per post. 
    # The single-post path (get_post , create_post return) passes it in as well
    # after fetching alongside image moderation. This self-fetch is a safe 
    # fallback for any caller that doesnt pre-fetch. 
    # 
    # Future scope (TODO): once link metadata is stored in the PostLink DB table, remove this fetch entirely - read from post.links join like post.media

    if link_metadata is None:
        link_metadata = await fetch_link_metadata(post.caption or "")

    payload = {
        "id": post.id,
        "type": post.type,
        "caption": post.caption,
        "status": post.status,
        "sourceUrl": post.sourceUrl,
        "createdAt": post.createdAt,
        "updatedAt": post.updatedAt,
        "captionEditedAt": getattr(post, "captionEditedAt", None),
        "authorId": post.authorId,
        "author": _serialize_author(getattr(post, "author", None)),
        "media": [MediaOut.model_validate(m) for m in media],
        "tags": [_serialize_tag(t) for t in tags],
        "likeCount": len(likes),
        "commentCount": comment_count,
        "isLikedByMe": any(like.userId == current_user_id for like in likes),
        "reactionType": next(
            (like.reactionType for like in likes if like.userId == current_user_id), None
        ),
        "appreciation": {
            "appreciationTypeId": post.appreciation.appreciationTypeId,
            "appreciationTypeName": post.appreciation.appreciationType.name,
            "badgePath": post.appreciation.appreciationType.badgePath,
            "description": post.appreciation.appreciationType.description,
            "recipients": [
                {
                    "id": r.id,
                    "taggedUserId": r.userId,
                    "taggedUserName": r.user.name,
                    "taggedUserPicture": r.user.picture
                } for r in post.appreciation.recipients
            ]
        } if getattr(post, "type", None) == PostType.APPRECIATION and getattr(post, "appreciation", None) else None,
        
        # --- NEW POLL SERIALIZATION ---
        "poll": (
            _serialize_poll(post.poll, user_vote_option_id)
            if getattr(post, "type", None) == PostType.POLL and getattr(post, "poll", None)
            else None
        ),
        # ------------------------------
        "linkMetadata": link_metadata,
    }
    if include_comments:
        payload["comments"] = [_serialize_comment(c) for c in comments_rel]
        return PostDetailOut(**payload).model_dump(mode="json")

    return PostOut(**payload).model_dump(mode="json")


# ── CRUD: Posts ───────────────────────────────────────────────

async def create_post(current_user, body, background_tasks) -> dict:
    if body.type == PostType.APPRECIATION:
        if not body.appreciationTypeId or not body.recipientIds:
            raise AppException(400, "appreciationTypeId and recipientIds are required for appreciation posts")
        await _validate_recipients(body.recipientIds, current_user.id)
        body.taggedUserIds = [uid for uid in body.taggedUserIds if uid not in body.recipientIds]

        # ── FAST PATH: Default Appreciation Message ──
        # The frontend explicitly flags this. Caption is system-generated and safe.
        # Skip moderation entirely and publish immediately.
        if body.isDefaultMessage:
            import re
            app_type = await db.appreciationtype.find_unique(where={"id": body.appreciationTypeId})
            if app_type and app_type.description:
                tokens = re.findall(r'@\[[^\]]+\]', body.caption or "")
                mention_prefix = " , ".join(tokens)
                body.caption = (mention_prefix + "\n\n" + app_type.description) if mention_prefix else app_type.description
            return await _instant_publish_appreciation(current_user, body)


    if body.type == PostType.POLL:
        if body.taggedUserIds:
            raise AppException(400, "Polls do not support tagging users")
        if body.media:
            raise AppException(400, "Polls do not support media")
        if not body.caption or not body.caption.strip():
            raise AppException(400, "Poll question (caption) is required")
        if not (POLL_MIN_OPTIONS <= len(body.pollOptions) <= POLL_MAX_OPTIONS):
            raise AppException(400, f"Poll must have between {POLL_MIN_OPTIONS} and {POLL_MAX_OPTIONS} options")
        cleaned_options = [o.strip() for o in body.pollOptions]
        if any(not o for o in cleaned_options):
            raise AppException(400, "Poll options cannot be empty")
        if len(set(o.lower() for o in cleaned_options)) != len(cleaned_options):
            raise AppException(400, "Poll options must be unique")
        body.pollOptions = cleaned_options
        if body.pollClosesAt and body.pollClosesAt <= datetime.now(timezone.utc):
            raise AppException(400, "Poll closing time must be in the future")

    for m in body.media:
        storage_service.assert_allowed_post_media_url(m.url)

    create_data: dict = {
        "caption": body.caption,
        "type":    body.type,
        "status":  ContentStatus.PENDING_SCAN,
        "author":  {"connect": {"id": current_user.id}},
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

    post = await db.post.create(data=create_data, include=FEED_INCLUDE)
     # Re-fetch to ensure nested tag→user relations are populated
    # (Prisma Python doesn't always hydrate deeply-nested includes in create responses)
    post = await db.post.find_unique(where={"id": post.id}, include=FEED_INCLUDE)
    await write_audit_log(
        event_type=AuditEventType.POST_CREATED,
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.POST,
        entity_id=post.id,
        metadata={
            "caption":  body.caption[:80] if body.caption else None,
            "postType": str(post.type),
        },
    )

    # ── Queue moderation to run AFTER the response is sent ──
    background_tasks.add_task(
        _moderate_post_background,
        post_id=post.id,
        author_id=current_user.id,
        body=body,
    )

    return await _serialize_post(post, current_user.id, include_comments=False, link_metadata=None)

async def _instant_publish_appreciation(current_user, body) -> dict:
    """Fast-path for default appreciations with no images."""
    create_data: dict = {
        "caption": body.caption,
        "type":    body.type,
        "status":  ContentStatus.PUBLISHED,
        "author":  {"connect": {"id": current_user.id}},
    }
    if body.taggedUserIds:
        create_data["tags"] = {"create": [{"taggedUserId": uid} for uid in body.taggedUserIds]}
        
    if body.media:
        create_data["media"] = {
            "create": [
                {"url": m.url, "order": m.order, "altText": m.altText}
                for m in body.media
            ],
        }

    post = await db.post.create(data=create_data, include=FEED_INCLUDE)
       # Re-fetch to ensure nested tag→user relations are populated
    # (Prisma Python doesn't always hydrate deeply-nested includes in create responses)
    post = await db.post.find_unique(where={"id": post.id}, include=FEED_INCLUDE)
    await write_audit_log(
        event_type=AuditEventType.POST_CREATED, actor_type=AuditActorType.USER,
        actor_id=current_user.id, entity_type=AuditEntityType.POST, entity_id=post.id,
        metadata={"caption": body.caption[:80], "postType": str(post.type)},
    )
    
    await _materialize_appreciation(
        post_id=post.id, sender_id=current_user.id,
        appreciation_type_id=body.appreciationTypeId,
        recipient_ids=body.recipientIds
    )
    
    await _write_published_audit(post, current_user.id, text_score=0.0, image_score=0.0)
    
    return await _serialize_post(post, current_user.id, include_comments=False, link_metadata=None)

async def _moderate_post_background(post_id: str, author_id: str, body) -> None:
    """
    Runs AFTER the API response is already sent to the client.
    Fetches link metadata, scans text + images, then publishes or flags the post.
    """
    try:
        now = datetime.now(timezone.utc)
        image_urls = [m.url for m in body.media] if body.media else []

        link_metadata, (image_score, image_reason) = await asyncio.gather(
            fetch_link_metadata(body.caption or ""),
            scan_images(image_urls) if image_urls else _noop_image_scan(),
        )

        moderation_text = body.caption or ""
        if body.type == PostType.POLL and body.pollOptions:
            moderation_text = (moderation_text + " " + " | ".join(body.pollOptions)).strip()

        if link_metadata:
            titles_combined = " | ".join(
                f"[link] {m['title']}" for m in link_metadata if m.get("title")
            )
            if titles_combined:
                moderation_text = (moderation_text + " " + titles_combined).strip()

        # ── Static blacklist ──────────────────────────────────
        if moderation_text:
            blacklist_hit = await check_blacklist(moderation_text)
            if blacklist_hit:
                await db.post.update(
                    where={"id": post_id},
                    data={"status": ContentStatus.REMOVED, "flagReason": FlagReason.NSFW_TEXT},
                )
                await auto_resolve_alert(
                    post_id=post_id,
                    author_id=author_id,
                    flagged_phrase=blacklist_hit,
                    extra_flag_details=_build_poll_flag_details(body) if body.type == PostType.POLL else None,
                )
                return

        # ── AI scan ───────────────────────────────────────────
        try:
            (text_score, text_category, text_phrase, text_confidence), = await asyncio.gather(
                scan_text(moderation_text) if moderation_text else _noop_text_scan(),
            )
        except Exception as e:
            print(f"[moderation] AI scan failed for post {post_id}: {e}")
            return  # stays PENDING_SCAN — recovery job will handle it

        # ── Text flagged ──────────────────────────────────────
        if text_score >= MODERATION_REVIEW_THRESHOLD:
            whitelist_decision = await check_whitelist(text_phrase, text_confidence)

            if whitelist_decision == "auto_publish":
                post = await db.post.update(
                    where={"id": post_id},
                    data={"status": ContentStatus.PUBLISHED},
                    include=FEED_INCLUDE,
                )
                if body.type == PostType.APPRECIATION:
                    await _materialize_appreciation(
                        post_id=post_id, sender_id=author_id,
                        appreciation_type_id=body.appreciationTypeId,
                        recipient_ids=body.recipientIds
                    )
                elif body.type == PostType.POLL:
                    await _materialize_poll(
                        post_id=post_id, creator_id=author_id,
                        option_texts=body.pollOptions, closes_at=body.pollClosesAt,
                    )
                await _write_published_audit(post, author_id, text_score, image_score)
                return

            note = (
                f"Whitelisted term ('{text_phrase}') — AI flagged anyway "
                f"(confidence: {text_confidence:.2f})"
                if whitelist_decision == "queue_with_note" else None
            )
            await db.post.update(
                where={"id": post_id},
                data={"status": ContentStatus.FLAGGED, "flagReason": FlagReason.NSFW_TEXT, "flaggedAt": now},
            )
            await create_alert(
                post_id=post_id, author_id=author_id,
                flag_details={
                    "text_score": text_score, "image_score": image_score,
                    "reason": FlagReason.NSFW_TEXT.value,
                    "appreciationTypeId": body.appreciationTypeId if body.type == PostType.APPRECIATION else None,
                    "recipientIds": body.recipientIds if body.type == PostType.APPRECIATION else None,
                    **(_build_poll_flag_details(body) if body.type == PostType.POLL else {}),
                    "category": text_category, "confidence": text_confidence,
                },
                flagged_phrase=text_phrase, note=note,
            )
            await write_audit_log(
                event_type=AuditEventType.POST_SCAN_COMPLETED, actor_type=AuditActorType.SYSTEM,
                entity_type=AuditEntityType.POST, entity_id=post_id,
                metadata={"finalStatus": "FLAGGED", "postAuthorId": author_id,
                          "textScore": text_score, "imageScore": image_score,
                          "flagReason": FlagReason.NSFW_TEXT.value},
            )
            return

        # ── Image flagged ─────────────────────────────────────
        if image_score >= MODERATION_REVIEW_THRESHOLD:
            await db.post.update(
                where={"id": post_id},
                data={"status": ContentStatus.FLAGGED, "flagReason": FlagReason.NSFW_IMAGE, "flaggedAt": now},
            )
            await create_alert(
                post_id=post_id, author_id=author_id,
                flag_details={
                    "text_score": text_score, "image_score": image_score,
                    "reason": FlagReason.NSFW_IMAGE.value,
                    "appreciationTypeId": body.appreciationTypeId if body.type == PostType.APPRECIATION else None,
                    "recipientIds": body.recipientIds if body.type == PostType.APPRECIATION else None,
                    **(_build_poll_flag_details(body) if body.type == PostType.POLL else {}),
                },
                flagged_phrase=None,
            )
            await write_audit_log(
                event_type=AuditEventType.POST_SCAN_COMPLETED, actor_type=AuditActorType.SYSTEM,
                entity_type=AuditEntityType.POST, entity_id=post_id,
                metadata={"finalStatus": "FLAGGED", "postAuthorId": author_id,
                          "textScore": text_score, "imageScore": image_score,
                          "flagReason": FlagReason.NSFW_IMAGE.value},
            )
            return

        # ── All clean — publish ───────────────────────────────
        post = await db.post.update(
            where={"id": post_id},
            data={"status": ContentStatus.PUBLISHED},
            include=FEED_INCLUDE,
        )
        if body.type == PostType.APPRECIATION:
            await _materialize_appreciation(
                post_id=post_id, sender_id=author_id,
                appreciation_type_id=body.appreciationTypeId,
                recipient_ids=body.recipientIds
            )
        elif body.type == PostType.POLL:
            await _materialize_poll(
                post_id=post_id, creator_id=author_id,
                option_texts=body.pollOptions, closes_at=body.pollClosesAt,
            )
        await _write_published_audit(post, author_id, text_score, image_score)

    except Exception as e:
        print(f"[moderation] Unhandled error in background task for post {post_id}: {e}")

async def recover_stuck_pending_posts(background_tasks) -> None:
    """Finds posts stuck in PENDING_SCAN for > 2 minutes and re-queues moderation."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)

    stuck_posts = await db.post.find_many(
        where={
            "status": ContentStatus.PENDING_SCAN,
            "createdAt": {"lt": cutoff},
        },
        include=FEED_INCLUDE,
        take=50,
    )

    for post in stuck_posts:
        print(f"[recovery] Re-queuing moderation for stuck post {post.id}")
        background_tasks.add_task(_recover_single_post, post_id=post.id, author_id=post.authorId)


async def _recover_single_post(post_id: str, author_id: str) -> None:
    """Recovery: re-runs full moderation instead of blindly publishing."""
    try:
        post = await db.post.find_unique(
            where={"id": post_id},
            include={
                "media": True,
                "appreciation": {"include": {"recipients": True}},
                "poll": {"include": {"options": {"order_by": {"order": "asc"}}}},
            },
        )
        if not post or post.status != ContentStatus.PENDING_SCAN:
            return

        # Reconstruct a minimal body from the DB so _moderate_post_background can re-run.
        class _RecoveryBody:
            def __init__(self, p):
                self.caption = p.caption
                self.type = p.type
                self.taggedUserIds = []
                self.media = [
                    type('M', (), {'url': m.url, 'order': m.order, 'altText': m.altText})()
                    for m in (getattr(p, 'media', None) or [])
                ]
                app = getattr(p, 'appreciation', None)
                self.appreciationTypeId = app.appreciationTypeId if app else None
                self.recipientIds = [r.userId for r in app.recipients] if app else []
                poll = getattr(p, 'poll', None)
                self.pollOptions = [o.text for o in (poll.options if poll else [])]
                self.pollClosesAt = poll.closesAt if poll else None

        print(f"[recovery] Re-running moderation for stuck post {post_id}")
        await _moderate_post_background(post_id=post_id, author_id=author_id, body=_RecoveryBody(post))

    except Exception as e:
        print(f"[recovery] Failed to recover post {post_id}: {e}")


async def _noop_text_scan():
    return (0.0, None, None, 0.0)

async def _noop_image_scan():
    return (0.0, None)

async def _write_published_audit(post, author_id: str, text_score: float, image_score: float):
    await write_audit_log(
        event_type=AuditEventType.POST_SCAN_COMPLETED,
        actor_type=AuditActorType.SYSTEM,
        entity_type=AuditEntityType.POST,
        entity_id=post.id,
        metadata={
            "finalStatus":  "PUBLISHED",
            "postAuthorId": author_id,
            "textScore":    text_score,
            "imageScore":   image_score,
        },
    )
    if post.type == PostType.USER_POST and post.tags:
        for tag in post.tags:
            await write_audit_log(
                event_type=AuditEventType.USER_TAGGED_IN_POST,
                actor_type=AuditActorType.USER,
                actor_id=author_id,
                entity_type=AuditEntityType.POST,
                entity_id=post.id,
                metadata={
                    "taggedUserId": tag.taggedUserId,
                    "postCaption":  post.caption[:80] if post.caption else None,
                },
            )

async def _materialize_appreciation(post_id: str, sender_id: str, appreciation_type_id: str, recipient_ids: list[str]):
    appreciation = await db.appreciation.create(
        data={
            "postId": post_id,
            "senderId": sender_id,
            "appreciationTypeId": appreciation_type_id,
            "recipients": {
                "create": [{"userId": rid} for rid in recipient_ids]
            }
        },
        include={"appreciationType": True}
    )
    
    # Fire the audit event which triggers the notification
    from services.audit_service import write_audit_log
    await write_audit_log(
        event_type=AuditEventType.APPRECIATION_SENT,
        actor_type=AuditActorType.USER,
        actor_id=sender_id,
        entity_type=AuditEntityType.APPRECIATION,
        entity_id=appreciation.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post_id,
        metadata={
            "recipientIds": recipient_ids,
            "appreciationTypeName": appreciation.appreciationType.name,
            "badgePath": appreciation.appreciationType.badgePath,
        }
    )

async def _materialize_poll(
    post_id: str,
    creator_id: str,
    option_texts: list[str],
    closes_at: datetime | None = None,
):
    """
    Standalone/importable — same pattern as _materialize_appreciation.
    Called from create_post on a clean publish, AND from alert_service's
    resolve_alert() for late materialization when an admin restores a
    previously flagged or auto-removed poll.
    """
    poll = await db.poll.create(
        data={
            "postId": post_id,
            "creatorId": creator_id,
            "closesAt": closes_at,
            "options": {
                "create": [
                    {"text": text, "order": idx}
                    for idx, text in enumerate(option_texts)
                ]
            },
        },
        include={"options": {"order_by": {"order": "asc"}}},
    )

    from services.audit_service import write_audit_log
    await write_audit_log(
        event_type=AuditEventType.POLL_CREATED,
        actor_type=AuditActorType.USER,
        actor_id=creator_id,
        entity_type=AuditEntityType.POLL,
        entity_id=poll.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post_id,
        metadata={
            "creatorId": creator_id,
            "optionCount": len(option_texts),
            "closesAt": closes_at.isoformat() if closes_at else None,
        },
    )
    return poll


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
        "OR": [
            {"status": ContentStatus.PUBLISHED},
            {"status": ContentStatus.PENDING_SCAN, "authorId": current_user.id},
        ],
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

    # --- NEW: Fetch user poll votes for feed ---
    poll_ids = [
        p.poll.id for p in posts
        if getattr(p, "type", None) == PostType.POLL and getattr(p, "poll", None)
    ]
    poll_votes_map = await _user_poll_votes(poll_ids, current_user.id)
    # -------------------------------------------

        # Pre-fetch link metadata for all posts concurrently.
    # asyncio.gather fires all caption fetches at the same time, so the
    # total wait = slowest single URL across ALL posts (not the sum).
    # Posts with no links in their caption resolve instantly.
    #
    # Future scope (TODO): once PostLink DB table exists, replace this entire
    # gather with a batch DB lookup — no live HTTP calls on feed load at all.
    all_link_metadata = await asyncio.gather(
        *[fetch_link_metadata(p.caption or "") for p in posts]
    )

    serialized_posts = await asyncio.gather(
        *[
            _serialize_post(
                p,
                current_user.id,
                comment_count=comment_counts.get(p.id, 0),
                user_vote_option_id=(
                    poll_votes_map.get(p.poll.id)
                    if getattr(p, "type", None) == PostType.POLL and getattr(p, "poll", None)
                    else None
                ),
                link_metadata=lm,
            )
            for p, lm in zip(posts, all_link_metadata)
        ]
    )

    return FeedResponse(
        posts=list(serialized_posts),
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
        
    # --- NEW: Fetch user poll vote ---
    user_vote_option_id = None
    if post.type == PostType.POLL and getattr(post, "poll", None):
        user_vote_option_id = await _single_user_poll_vote(post.poll.id, current_user.id)
    # ---------------------------------
    
    return await _serialize_post(
        post, current_user.id, include_comments=True, user_vote_option_id=user_vote_option_id
    )


async def update_post(current_user, post_id: str, body) -> dict:
    post = await db.post.find_unique(
        where={"id": post_id},
        include={
            "poll": {"include": {"options": {"order_by": {"order": "asc"}}}},
            "tags": True
        },
    )
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.status == ContentStatus.REMOVED:
        raise AppException(400, "Post is removed")
    if post.authorId != current_user.id:
        raise AppException(403, "You can only edit your own posts")

    if post.type == PostType.POLL:
        return await _update_poll_post(current_user, post, body)
    # ------------------------------------------

    update_data: dict = {}
    if body.caption is not None:
        update_data["caption"] = body.caption
        update_data["captionEditedAt"] = datetime.now(timezone.utc)

    if update_data:
        updated = await db.post.update(
            where={"id": post_id},
            data=update_data,
            include=POST_INCLUDE,
        )
    else:
        updated = await db.post.find_unique(where={"id": post_id}, include=POST_INCLUDE)

    # ── Tagged users: diff-based add / remove ─────────────────────────
    if body.taggedUserIds is not None:
        await _update_post_tags(current_user, post_id, body.taggedUserIds, post.type)
        # Re-fetch so the serialized response reflects the updated tag list
        updated = await db.post.find_unique(where={"id": post_id}, include=POST_INCLUDE)
    # ------------------------------------------------------------------

    return await _serialize_post(updated, current_user.id, include_comments=True)


async def _update_post_tags(current_user, post_id: str, incoming_user_ids: list[str], post_type) -> None:
    """
    Diff-based tagged-user update for a post (USER_POST or APPRECIATION).

    - incoming_user_ids = full replacement list; [] clears all tags.
    - POLL posts: rejected — tagging is not supported on polls.
    - APPRECIATION posts: any ID already in the appreciation's recipient list
      is silently dropped (recipients != tags, no duplication).
    - Validates every incoming ID is a real, active user.
    - Fires USER_TAGGED_IN_POST / USER_UNTAGGED_FROM_POST audit events.
    """
    if post_type == PostType.POLL:
        raise AppException(400, "Polls do not support tagging users")

    # ── Deduplicate against appreciation recipients ────────────────────
    if post_type == PostType.APPRECIATION:
        appreciation = await db.appreciation.find_first(
            where={"postId": post_id, "deletedAt": None},
            include={"recipients": True},
        )
        if appreciation and appreciation.recipients:
            recipient_user_ids = {r.userId for r in appreciation.recipients}
            incoming_user_ids = [uid for uid in incoming_user_ids if uid not in recipient_user_ids]

    # ── Deduplicate the incoming list itself (preserve order) ─────────
    incoming_user_ids = list(dict.fromkeys(incoming_user_ids))

    # ── Validate that all incoming IDs are real, active users ─────────
    if incoming_user_ids:
        found_users = await db.user.find_many(
            where={"id": {"in": incoming_user_ids}, "deletedAt": None}
        )
        if len(found_users) != len(incoming_user_ids):
            raise AppException(400, "One or more tagged users not found")

    # ── Diff against current DB state ─────────────────────────────────
    existing_tags = await db.posttag.find_many(where={"postId": post_id})
    existing_user_ids = {t.taggedUserId for t in existing_tags}
    incoming_set = set(incoming_user_ids)

    ids_to_add = [uid for uid in incoming_user_ids if uid not in existing_user_ids]
    ids_to_remove = list(existing_user_ids - incoming_set)

    # ── Apply DB changes ───────────────────────────────────────────────
    if ids_to_remove:
        await db.posttag.delete_many(
            where={"postId": post_id, "taggedUserId": {"in": ids_to_remove}}
        )

    for uid in ids_to_add:
        await db.posttag.create(data={"postId": post_id, "taggedUserId": uid})

    # ── Audit log ─────────────────────────────────────────────────────
    for uid in ids_to_add:
        await write_audit_log(
            event_type=AuditEventType.USER_TAGGED_IN_POST,
            actor_type=AuditActorType.USER,
            actor_id=current_user.id,
            entity_type=AuditEntityType.POST,
            entity_id=post_id,
            metadata={"taggedUserId": uid},
        )

    for uid in ids_to_remove:
        await write_audit_log(
            event_type=AuditEventType.USER_UNTAGGED_FROM_POST,
            actor_type=AuditActorType.USER,
            actor_id=current_user.id,
            entity_type=AuditEntityType.POST,
            entity_id=post_id,
            metadata={"taggedUserId": uid},
        )


async def _update_poll_post(current_user, post, body) -> dict:
    """
    Since the spec explicitly requires poll caption + options to go through 
    moderation "just like creation", this path adds synchronous moderation 
    that did not exist before for posts in general. Edits that fail moderation 
    are rejected outright (400).
    """
    poll = getattr(post, "poll", None)
    if not poll:
        raise AppException(400, "Poll data not found for this post")

    new_caption = body.caption if body.caption is not None else post.caption
    if not new_caption or not new_caption.strip():
        raise AppException(400, "Poll question (caption) is required")

    existing_options = sorted(poll.options, key=lambda o: o.order)

    if body.pollOptions is not None:
        if len(body.pollOptions) != len(existing_options):
            raise AppException(400, "Cannot add or remove poll options — only option text can be edited")
        cleaned = [o.strip() for o in body.pollOptions]
        if any(not o for o in cleaned):
            raise AppException(400, "Poll options cannot be empty")
        if len(set(o.lower() for o in cleaned)) != len(cleaned):
            raise AppException(400, "Poll options must be unique")
        new_option_texts = cleaned
    else:
        new_option_texts = [o.text for o in existing_options]

    moderation_text = (new_caption + " " + " | ".join(new_option_texts)).strip()

    blacklist_hit = await check_blacklist(moderation_text)
    if blacklist_hit:
        raise AppException(400, "Your edit contains restricted content and cannot be saved")

    try:
        text_score, _, _, _ = await scan_text(moderation_text)
    except Exception as e:
        print(f"[moderation] poll edit scan failed for post {post.id}: {e}")
        raise AppException(503, "Edit could not be processed. Please try again.")

    if text_score >= MODERATION_REVIEW_THRESHOLD:
        raise AppException(400, "Your edit was flagged by our content filter and cannot be saved. Please revise.")

    now = datetime.now(timezone.utc)
    await db.post.update(
        where={"id": post.id},
        data={"caption": new_caption, "captionEditedAt": now},
    )
    for option, new_text in zip(existing_options, new_option_texts):
        if option.text != new_text:
            await db.polloption.update(where={"id": option.id}, data={"text": new_text})

    await write_audit_log(
        event_type=AuditEventType.POLL_OPTIONS_OR_CAPTION_EDITED,
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.POLL,
        entity_id=poll.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post.id,
        metadata={"newCaption": new_caption[:80], "optionCount": len(new_option_texts)},
    )

    updated = await db.post.find_unique(where={"id": post.id}, include=POST_INCLUDE)
    user_vote_option_id = await _single_user_poll_vote(poll.id, current_user.id)
    return await _serialize_post(
        updated, current_user.id, include_comments=True, user_vote_option_id=user_vote_option_id
    )


async def delete_post(current_user, post_id: str) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.status == ContentStatus.REMOVED:
        raise AppException(400, "Post is removed")
    if post.authorId != current_user.id:
        raise AppException(403, "You can only delete your own posts")

    now = datetime.now(timezone.utc)
    
    if post.type == PostType.APPRECIATION:
        await db.appreciation.update_many(
            where={"postId": post.id},
            data={"deletedAt": now}
        )
    # --- NEW: Soft-delete poll cascade ---
    elif post.type == PostType.POLL:
        await db.poll.update_many(
            where={"postId": post.id},
            data={"deletedAt": now}
        )
    # -------------------------------------
    
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

async def like_post(current_user, post_id: str, body=None) -> dict:
    post = await db.post.find_unique(where={"id": post_id})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.status == ContentStatus.REMOVED:
        raise AppException(400, "Post is removed")

    reaction_type = getattr(body, "reactionType", None) if body else None
    if not reaction_type:
        reaction_type = "LIKE"

    existing = await db.like.find_first(
        where={"postId": post_id, "userId": current_user.id}
    )
    if existing:
        if existing.reactionType == reaction_type:
            raise AppException(400, "You have already liked this post with this reaction.")
        await db.like.update(
            where={"id":existing.id},
            data={"reactionType":reaction_type},
        )
    else:
        await db.like.create(
            data={"postId":post_id,"userId":current_user.id, "reactionType":reaction_type},
        )
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
    count = await db.like.count(where={"postId": post_id})

    return LikeResponse(postId=post_id, liked=True, likeCount=count,reactionType=reaction_type).model_dump(mode="json")


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

    return LikeResponse(postId=post_id, liked=False, likeCount=count,reactionType=None).model_dump(mode="json")


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

    # ── Blacklist check ───────────────────────────────────────
    blacklist_hit = await check_blacklist(body.body)
    if blacklist_hit:
        comment = await db.comment.create(
            data={
                "postId":     post_id,
                "authorId":   current_user.id,
                "body":       body.body,
                "parentId":   parent_id,
                "status":     ContentStatus.REMOVED,
                "flagReason": FlagReason.NSFW_TEXT,
                "flaggedAt":  now,
                **({
                    "tags": {"create": [{"taggedUserId": uid} for uid in valid_tagged_ids]}
                } if valid_tagged_ids else {}),
            },
            include=COMMENT_INCLUDE,
        )
        await auto_resolve_alert(
            post_id=post_id,
            author_id=current_user.id,
            flagged_phrase=blacklist_hit,
            comment_id=comment.id,
        )
        return _serialize_comment(comment).model_dump(mode="json")

    # ── AI scan ───────────────────────────────────────────────
    try:
        text_score, text_category, text_phrase, text_confidence = await scan_text(body.body)
    except Exception as e:
        print(f"[moderation] comment scan failed: {e}")
        raise AppException(503, "Comment could not be processed. Please try again.")

    tag_create = [{"taggedUserId": uid} for uid in valid_tagged_ids]

    if text_score >= MODERATION_REVIEW_THRESHOLD:
        whitelist_decision = await check_whitelist(text_phrase, text_confidence)

        if whitelist_decision == "auto_publish":
            comment = await db.comment.create(
                data={
                    "postId":   post_id,
                    "authorId": current_user.id,
                    "body":     body.body,
                    "parentId": parent_id,
                    "status":   ContentStatus.PUBLISHED,
                    **({
                        "tags": {"create": tag_create}
                    } if tag_create else {}),
                },
                include=COMMENT_INCLUDE,
            )
            return _serialize_comment(comment).model_dump(mode="json")

        note = (
            f"Whitelisted term ('{text_phrase}') — AI flagged anyway "
            f"(confidence: {text_confidence:.2f})"
            if whitelist_decision == "queue_with_note" else None
        )

        comment = await db.comment.create(
            data={
                "postId":     post_id,
                "authorId":   current_user.id,
                "body":       body.body,
                "parentId":   parent_id,
                "status":     ContentStatus.FLAGGED,
                "flagReason": FlagReason.NSFW_TEXT,
                "flaggedAt":  now,
                **({
                    "tags": {"create": tag_create}
                } if tag_create else {}),
            },
            include=COMMENT_INCLUDE,
        )
        await create_alert(
            comment_id=comment.id,
            post_id=post_id,
            author_id=current_user.id,
            flag_details={
                "text_score": text_score,
                "reason":     FlagReason.NSFW_TEXT.value,
                "category":   text_category,
                "confidence": text_confidence,
            },
            flagged_phrase=text_phrase,
            note=note,
        )
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