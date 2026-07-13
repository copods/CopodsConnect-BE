# services/notification_engine.py
"""
Notification engine — recipient resolution logic.

Called exclusively from write_audit_log() immediately after each
audit log row is written. Never called from routes directly.

For each notification-relevant event type, this module:
  1. Determines the list of recipient user IDs.
  2. Inserts one UserNotification row per recipient.

Non-notification events (e.g. USER_SEARCH_PERFORMED, USER_LOGIN_APP) are
silently ignored here — they are logged in audit_logs but produce no notifications.
"""
from db.client import db
from prisma.enums import AuditEventType


# ── Fan-out helper ────────────────────────────────────────────

async def _fan_out(audit_log_id: str, recipient_ids: list[str]) -> None:
    """
    Creates one UserNotification row per recipient.
    The unique constraint (auditLogId, recipientId) prevents duplicates.
    """
    if not recipient_ids:
        return
    # Use create_many with skipDuplicates for safety
    await db.usernotification.create_many(
        data=[
            {"auditLogId": audit_log_id, "recipientId": rid}
            for rid in recipient_ids
        ],
        skip_duplicates=True,
    )


# ── Main dispatch ─────────────────────────────────────────────

async def dispatch(audit_log) -> None:
    """
    Entry point. Receives a freshly created AuditLog row (with metadata as dict).
    Routes to the appropriate recipient-resolution function.
    Silently ignores event types that do not produce notifications.
    """
    et = audit_log.eventType
    meta = audit_log.metadata or {}

    # ── Post interactions ─────────────────────────────────────
    if et == AuditEventType.POST_LIKED:
        await _on_post_liked(audit_log, meta)

    elif et == AuditEventType.USER_TAGGED_IN_POST:
        await _on_user_tagged_in_post(audit_log, meta)

    elif et == AuditEventType.POST_SCAN_COMPLETED:
        await _on_post_scan_completed(audit_log, meta)

    # ── Comment interactions ──────────────────────────────────
    elif et == AuditEventType.COMMENT_CREATED:
        await _on_comment_created(audit_log, meta)

    elif et == AuditEventType.USER_TAGGED_IN_COMMENT:
        await _on_user_tagged_in_comment(audit_log, meta)

    # ── Appreciations ─────────────────────────────────────────
    elif et == AuditEventType.APPRECIATION_SENT:
        await _on_appreciation_sent(audit_log, meta)
        # ── Polls ──────────────────────────────────────────────────
    elif et == AuditEventType.POLL_CREATED:
        await _on_poll_created(audit_log, meta)

    elif et == AuditEventType.POLL_VOTE_CAST:
        await _on_poll_vote_cast(audit_log, meta)

    # ── System celebrations ───────────────────────────────────
    elif et == AuditEventType.SYSTEM_BIRTHDAY_POST_CREATED:
        await _on_birthday_post_created(audit_log, meta)

    elif et == AuditEventType.SYSTEM_ANNIVERSARY_POST_CREATED:
        await _on_anniversary_post_created(audit_log, meta)

    # ── Moderation ────────────────────────────────────────────
    elif et == AuditEventType.ALERT_RESOLVED:
        await _on_alert_resolved(audit_log, meta)

    # All other events produce no notifications — silently skip


# ── Event handlers ────────────────────────────────────────────

async def _on_post_liked(audit_log, meta: dict) -> None:
    """
    POST_LIKED: notify the post author.
    Skipped if the liker IS the post author.
    entityId = post_id, actorId = liker's user_id
    meta: { postAuthorId: str, postCaption: str | None }
    """
    post_author_id = meta.get("postAuthorId")
    if not post_author_id:
        return
    # Skip self-notification
    if audit_log.actorId == post_author_id:
        return
    await _fan_out(audit_log.id, [post_author_id])


async def _on_user_tagged_in_post(audit_log, meta: dict) -> None:
    """
    USER_TAGGED_IN_POST: notify the tagged user.
    Only fires once post is PUBLISHED (called from _scan_post).
    entityId = post_id, actorId = tagger's user_id
    meta: { taggedUserId: str, postCaption: str | None }
    """
    tagged_user_id = meta.get("taggedUserId")
    if not tagged_user_id:
        return
    if audit_log.actorId == tagged_user_id:
        return
    await _fan_out(audit_log.id, [tagged_user_id])


async def _on_post_scan_completed(audit_log, meta: dict) -> None:
    """
    POST_SCAN_COMPLETED (flagged path only): notify the post author.
    entityId = post_id
    meta: { postAuthorId: str, finalStatus: str, flagReason: str | None, ... }
    Only sends a notification when finalStatus == "REMOVED" or "FLAGGED".
    """
    final_status = meta.get("finalStatus")
    if final_status not in ("FLAGGED", "REMOVED"):
        return
    post_author_id = meta.get("postAuthorId")
    if not post_author_id:
        return
    await _fan_out(audit_log.id, [post_author_id])


async def _on_comment_created(audit_log, meta: dict) -> None:
    """
    COMMENT_CREATED: two possible notifications —
      a) If top-level comment (parentId=None): notify post author (skip if commenter==author).
      b) If reply (parentId set): notify parent comment's author (skip if replier==that author).
    entityId = comment_id, parentEntityId = post_id, actorId = commenter's user_id
    meta: {
        postAuthorId: str,
        parentCommentId: str | None,
        parentCommentAuthorId: str | None,
        commentSnippet: str,
    }
    """
    parent_comment_id = meta.get("parentCommentId")
    actor_id = audit_log.actorId

    if parent_comment_id:
        # Reply — notify parent comment author
        parent_author_id = meta.get("parentCommentAuthorId")
        if parent_author_id and actor_id != parent_author_id:
            await _fan_out(audit_log.id, [parent_author_id])
    else:
        # Top-level — notify post author
        post_author_id = meta.get("postAuthorId")
        if post_author_id and actor_id != post_author_id:
            await _fan_out(audit_log.id, [post_author_id])


async def _on_user_tagged_in_comment(audit_log, meta: dict) -> None:
    """
    USER_TAGGED_IN_COMMENT: notify the tagged user.
    entityId = comment_id, actorId = tagger's user_id
    meta: { taggedUserId: str, postId: str, commentSnippet: str }
    """
    tagged_user_id = meta.get("taggedUserId")
    if not tagged_user_id:
        return
    if audit_log.actorId == tagged_user_id:
        return
    await _fan_out(audit_log.id, [tagged_user_id])


async def _on_appreciation_sent(audit_log, meta: dict) -> None:
    """
    APPRECIATION_SENT: notify every recipient (fan-out from metadata).
    entityId = appreciation_id, actorId = sender_id
    meta: {
        recipientIds: list[str],
        appreciationTypeName: str,
        emojiPath: str,
        message: str | None,
    }
    """
    recipient_ids = meta.get("recipientIds", [])
    sender_id = audit_log.actorId
    # Filter out the sender in case they somehow appear in recipients
    targets = [rid for rid in recipient_ids if rid != sender_id]
    await _fan_out(audit_log.id, targets)

async def _on_poll_created(audit_log, meta: dict) -> None:
    """
    POLL_CREATED: broadcast to every active, non-banned, non-deleted
    user who has logged into the app — excluding the poll creator.
    Users who've never logged into the app (panel-invited but inactive)
    are deliberately excluded per product decision.
    entityId = poll_id, parentEntityId = post_id, actorId = creator's user_id
    """
    creator_id = audit_log.actorId

    where: dict = {
        "deletedAt": None,
        "isBanned": False,
        "hasLoggedInApp": True,
    }
    if creator_id:
        where["id"] = {"not": creator_id}

    recipients = await db.user.find_many(where=where)
    recipient_ids = [u.id for u in recipients]
    await _fan_out(audit_log.id, recipient_ids)


async def _on_poll_vote_cast(audit_log, meta: dict) -> None:
    """
    POLL_VOTE_CAST: notify the poll creator. Skipped if voter IS creator.
    Reuses the same per-event-row fan-out as POST_LIKED/COMMENT_CREATED —
    aggregation into "X and N others voted" happens at read time in
    notification_service.get_notifications(), same pattern as likes.
    entityId = poll_vote_id, parentEntityId = post_id, actorId = voter's user_id
    """
    poll_creator_id = meta.get("pollCreatorId")
    if not poll_creator_id:
        return
    if audit_log.actorId == poll_creator_id:
        return
    await _fan_out(audit_log.id, [poll_creator_id])


async def _on_birthday_post_created(audit_log, meta: dict) -> None:
    """
    SYSTEM_BIRTHDAY_POST_CREATED:
      - Personal notification to the birthday user.
      - Broadcast to all OTHER active app users (PEER_BIRTHDAY equivalent).
    entityId = post_id (the system birthday post)
    meta: {
        birthdayUserId: str,
        personName: str,
        peerRecipientIds: list[str],   ← all other active user IDs, computed at job time
    }
    """
    birthday_user_id = meta.get("birthdayUserId")
    peer_ids = meta.get("peerRecipientIds", [])

    all_recipients = []
    if birthday_user_id:
        all_recipients.append(birthday_user_id)
    all_recipients.extend([rid for rid in peer_ids if rid != birthday_user_id])

    await _fan_out(audit_log.id, all_recipients)


async def _on_anniversary_post_created(audit_log, meta: dict) -> None:
    """
    SYSTEM_ANNIVERSARY_POST_CREATED: same pattern as birthday.
    meta: {
        anniversaryUserId: str,
        personName: str,
        yearsAtCompany: int,
        peerRecipientIds: list[str],
    }
    """
    anniversary_user_id = meta.get("anniversaryUserId")
    peer_ids = meta.get("peerRecipientIds", [])

    all_recipients = []
    if anniversary_user_id:
        all_recipients.append(anniversary_user_id)
    all_recipients.extend([rid for rid in peer_ids if rid != anniversary_user_id])

    await _fan_out(audit_log.id, all_recipients)


async def _on_alert_resolved(audit_log, meta: dict) -> None:
    """
    ALERT_RESOLVED with action=CONFIRMED_REMOVAL: notify the content author.
    entityId = alert_id, actorId = admin who resolved it
    meta: {
        resolvedAction: str,
        reportedUserId: str,
        postId: str,
        commentId: str | None,
        flagReason: str | None,
    }
    Only sends a notification when resolvedAction == "CONFIRMED_REMOVAL".
    """
    if meta.get("resolvedAction") != "CONFIRMED_REMOVAL":
        return
    reported_user_id = meta.get("reportedUserId")
    if not reported_user_id:
        return
    await _fan_out(audit_log.id, [reported_user_id])
