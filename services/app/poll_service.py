# services/app/poll_service.py
"""
Poll-specific write operations: voting, manual close/reopen, and
deadline extension. Read/serialization logic lives in post_service.py
alongside the rest of the feed serializer — polls are still Posts.
"""
from datetime import datetime, timezone

from db.client import db
from prisma.enums import PostType, ContentStatus, Role, AuditActorType, AuditEntityType, AuditEventType
from utils.exceptions import AppException
from services.audit_service import write_audit_log
from services.app import post_service


def _assert_can_manage_poll(current_user, poll) -> None:
    if poll.creatorId == current_user.id:
        return
    if current_user.role in (Role.ADMIN, Role.SUPER_ADMIN):
        return
    raise AppException(403, "Only the poll creator or an admin can manage this poll")


async def _get_post_and_poll(post_id: str):
    post = await db.post.find_unique(where={"id": post_id}, include={"poll": True})
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.type != PostType.POLL:
        raise AppException(400, "This post is not a poll")
    poll = post.poll
    if not poll or poll.deletedAt is not None:
        raise AppException(404, "Poll not found")
    return post, poll


async def _serialized_poll_post(post_id: str, current_user_id: str) -> dict:
    post = await db.post.find_unique(where={"id": post_id}, include=post_service.POST_INCLUDE)
    user_vote_option_id = await post_service._single_user_poll_vote(post.poll.id, current_user_id)
    return post_service._serialize_post(
        post, current_user_id, include_comments=False, user_vote_option_id=user_vote_option_id
    )


# ── Voting ────────────────────────────────────────────────────

async def cast_vote(current_user, post_id: str, option_id: str) -> dict:
    post = await db.post.find_unique(
        where={"id": post_id}, include={"poll": {"include": {"options": True}}}
    )
    if not post or post.deletedAt is not None:
        raise AppException(404, "Post not found")
    if post.type != PostType.POLL:
        raise AppException(400, "This post is not a poll")
    if post.status != ContentStatus.PUBLISHED:
        raise AppException(400, "This poll is not available")

    poll = post.poll
    if not poll or poll.deletedAt is not None:
        raise AppException(404, "Poll not found")
    if not post_service._is_poll_open(poll):
        raise AppException(409, "This poll is closed")

    valid_options = {o.id: o for o in poll.options}
    if option_id not in valid_options:
        raise AppException(400, "Invalid poll option")

    # Banned users' past votes are kept and counted (per product decision) —
    # this endpoint does not gate on isBanned, consistent with like_post()
    # and create_comment() which also don't check ban status at write time.
    existing_vote = await db.pollvote.find_first(where={"pollId": poll.id, "userId": current_user.id})

    if existing_vote and existing_vote.optionId == option_id:
        raise AppException(400, "You have already voted for this option")

    async with db.tx() as tx:
        if existing_vote:
            await tx.polloption.update(
                where={"id": existing_vote.optionId},
                data={"voteCount": {"decrement": 1}},
            )
            vote_row = await tx.pollvote.update(
                where={"id": existing_vote.id},
                data={"optionId": option_id},
            )
        else:
            vote_row = await tx.pollvote.create(
                data={"pollId": poll.id, "optionId": option_id, "userId": current_user.id},
            )
        await tx.polloption.update(
            where={"id": option_id},
            data={"voteCount": {"increment": 1}},
        )

    await write_audit_log(
        event_type=AuditEventType.POLL_VOTE_CAST,
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.POLL_VOTE,
        entity_id=vote_row.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post_id,
        metadata={
            "pollCreatorId": poll.creatorId,
            "optionId": option_id,
            "optionText": valid_options[option_id].text,
            "isVoteChange": bool(existing_vote),
        },
    )

    return await _serialized_poll_post(post_id, current_user.id)


# ── Close / Reopen / Extend ──────────────────────────────────

async def close_poll(current_user, post_id: str) -> dict:
    post, poll = await _get_post_and_poll(post_id)
    _assert_can_manage_poll(current_user, poll)
    if not post_service._is_poll_open(poll):
        raise AppException(400, "Poll is already closed")

    now = datetime.now(timezone.utc)
    await db.poll.update(
        where={"id": poll.id},
        data={"isManuallyClosed": True, "manuallyClosedAt": now},
    )
    await write_audit_log(
        event_type=AuditEventType.POLL_CLOSED_MANUALLY,
        actor_type=AuditActorType.ADMIN if current_user.role != Role.MEMBER else AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.POLL,
        entity_id=poll.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post_id,
        metadata={"closedByRole": getattr(current_user.role, "value", current_user.role)},
    )
    return await _serialized_poll_post(post_id, current_user.id)


async def reopen_poll(current_user, post_id: str) -> dict:
    post, poll = await _get_post_and_poll(post_id)
    _assert_can_manage_poll(current_user, poll)
    if not poll.isManuallyClosed:
        raise AppException(400, "Poll is not manually closed")

    await db.poll.update(
        where={"id": poll.id},
        data={"isManuallyClosed": False, "manuallyClosedAt": None},
    )
    await write_audit_log(
        event_type=AuditEventType.POLL_REOPENED_MANUALLY,
        actor_type=AuditActorType.ADMIN if current_user.role != Role.MEMBER else AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.POLL,
        entity_id=poll.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post_id,
        metadata={"reopenedByRole": getattr(current_user.role, "value", current_user.role)},
    )
    return await _serialized_poll_post(post_id, current_user.id)


async def extend_poll(current_user, post_id: str, new_closes_at: datetime) -> dict:
    post, poll = await _get_post_and_poll(post_id)
    _assert_can_manage_poll(current_user, poll)
    if poll.isManuallyClosed:
        raise AppException(400, "Reopen the poll before extending its deadline")

    now = datetime.now(timezone.utc)
    if new_closes_at <= now:
        raise AppException(400, "New closing time must be in the future")

    previous_closes_at = poll.closesAt
    await db.poll.update(where={"id": poll.id}, data={"closesAt": new_closes_at})

    await write_audit_log(
        event_type=AuditEventType.POLL_EXTENDED,
        actor_type=AuditActorType.ADMIN if current_user.role != Role.MEMBER else AuditActorType.USER,
        actor_id=current_user.id,
        entity_type=AuditEntityType.POLL,
        entity_id=poll.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post_id,
        metadata={
            "previousClosesAt": previous_closes_at.isoformat() if previous_closes_at else None,
            "newClosesAt": new_closes_at.isoformat(),
        },
    )
    return await _serialized_poll_post(post_id, current_user.id)