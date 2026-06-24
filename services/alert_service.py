# services/alert_service.py
import json
from datetime import datetime, timezone

from db.client import db
from prisma.enums import AlertAction, ContentStatus, Role
from services.audit_service import write_audit_log
from prisma.enums import AuditActorType, AuditEntityType, AuditEventType
from utils.email import send_nsfw_alert_email
from utils.exceptions import AppException


async def create_alert(
    post_id: str,
    author_id: str,
    flag_details: dict,
    comment_id: str | None = None,
    flagged_phrase: str | None = None,
    note: str | None = None,
) -> None:
    """
    Creates an AdminAlert pending admin review.
    flagged_phrase: the exact word/phrase caught by static layer or AI.
    note: optional admin-facing context (e.g. whitelist override situation).
    """
    if note:
        flag_details = {**flag_details, "note": note}

    alert = await db.adminalert.create(
        data={
            "postId":         post_id,
            "commentId":      comment_id,
            "reportedUserId": author_id,
            "flagDetails":    json.dumps(flag_details),
            "flaggedPhrase":  flagged_phrase,
            "resolvedAction": None,
            "resolvedAt":     None,
        }
    )

    await write_audit_log(
        event_type=AuditEventType.ALERT_CREATED,
        actor_type=AuditActorType.SYSTEM,
        entity_type=AuditEntityType.ALERT,
        entity_id=alert.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post_id,
        metadata={
            "reportedUserId": author_id,
            "commentId":      comment_id,
            "flagDetails":    flag_details,
            "flaggedPhrase":  flagged_phrase,
        },
    )

    admins = await db.user.find_many(
        where={
            "role":      {"in": [Role.ADMIN, Role.SUPER_ADMIN]},
            "deletedAt": None,
            "isBanned":  False,
        }
    )
    flagged_user = await db.user.find_unique(where={"id": author_id})
    if not flagged_user or not admins:
        return

    for admin in admins:
        await send_nsfw_alert_email(
            to_email=admin.email,
            flagged_user_name=flagged_user.name or "Unknown",
            flagged_user_email=flagged_user.email,
            post_id=post_id,
        )


async def auto_resolve_alert(
    post_id: str,
    author_id: str,
    flagged_phrase: str | None,
    comment_id: str | None = None,
    reason: str = "BLACKLIST_HIT",
) -> None:
    """
    Creates an AdminAlert pre-resolved as AUTO_REMOVED.
    Used when a blacklist hit auto-removes content without admin review.
    Still emails admins for visibility, does NOT appear in the pending queue.
    """
    now = datetime.now(timezone.utc)
    flag_details = {"reason": reason, "flaggedPhrase": flagged_phrase}

    alert = await db.adminalert.create(
        data={
            "postId":         post_id,
            "commentId":      comment_id,
            "reportedUserId": author_id,
            "flagDetails":    json.dumps(flag_details),
            "flaggedPhrase":  flagged_phrase,
            "resolvedAction": AlertAction.AUTO_REMOVED,
            "resolvedAt":     now,
        }
    )

    await write_audit_log(
        event_type=AuditEventType.ALERT_CREATED,
        actor_type=AuditActorType.SYSTEM,
        entity_type=AuditEntityType.ALERT,
        entity_id=alert.id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=post_id,
        metadata={
            "reportedUserId": author_id,
            "flaggedPhrase":  flagged_phrase,
            "reason":         reason,
            "autoResolved":   True,
        },
    )

    admins = await db.user.find_many(
        where={
            "role":      {"in": [Role.ADMIN, Role.SUPER_ADMIN]},
            "deletedAt": None,
            "isBanned":  False,
        }
    )
    flagged_user = await db.user.find_unique(where={"id": author_id})
    if not flagged_user or not admins:
        return

    for admin in admins:
        await send_nsfw_alert_email(
            to_email=admin.email,
            flagged_user_name=flagged_user.name or "Unknown",
            flagged_user_email=flagged_user.email,
            post_id=post_id,
        )


async def resolve_alert(alert_id: str, action: AlertAction, resolved_by_id: str) -> None:
    """
    Resolves a flagged alert.
    Handles: RESTORED, CONFIRMED_REMOVAL, BLACKLISTED, WHITELISTED.

    Special case: WHITELISTED is also allowed on already-AUTO_REMOVED alerts.
    This is the "undo" escape hatch — admin saw a blacklist auto-removal in the
    log and wants to reverse it because it was a false positive.
    """
    from services.moderation_service import (
        invalidate_blacklist_cache,
        reload_static_filter,
        squish_normalize,
    )

    now = datetime.now(timezone.utc)

    alert = await db.adminalert.find_unique(where={"id": alert_id})
    if not alert:
        raise AppException(404, "Alert not found")

    # Allow WHITELIST and RESTORE on AUTO_REMOVED alerts only — this is the undo/restore path
    # for blacklist false positives. All other already-resolved alerts are blocked.
    is_auto_removed_undo = (
        alert.resolvedAction == AlertAction.AUTO_REMOVED
        and action in (AlertAction.WHITELISTED, AlertAction.RESTORED)
    )
    if alert.resolvedAction is not None and not is_auto_removed_undo:
        raise AppException(400, "Alert is already resolved")

    # Determine new content status
    if action in (AlertAction.RESTORED, AlertAction.WHITELISTED):
        new_content_status = ContentStatus.PUBLISHED
    else:
        new_content_status = ContentStatus.REMOVED

    # ── BLACKLISTED ───────────────────────────────────────────
    if action == AlertAction.BLACKLISTED:
        if not alert.flaggedPhrase:
            raise AppException(400, "Cannot blacklist: alert has no flagged phrase")

        raw = alert.flaggedPhrase
        normalized_key = squish_normalize(raw)

        existing = await db.moderationblacklist.find_first(
            where={"normalizedKey": normalized_key}
        )
        if not existing:
            await db.moderationblacklist.create(
                data={
                    "rawPhrase":     raw,
                    "normalizedKey": normalized_key,
                    "addedById":     resolved_by_id,
                    "alertId":       alert_id,
                }
            )
        await invalidate_blacklist_cache()   # rebuild automatons immediately

    # ── WHITELISTED ───────────────────────────────────────────
    elif action == AlertAction.WHITELISTED:
        if not alert.flaggedPhrase:
            raise AppException(400, "Cannot whitelist: alert has no flagged phrase")

        raw = alert.flaggedPhrase
        normalized_key = squish_normalize(raw)

        # Add to whitelist
        existing_wl = await db.moderationwhitelist.find_first(
            where={"normalizedKey": normalized_key}
        )
        if not existing_wl:
            await db.moderationwhitelist.create(
                data={
                    "rawPhrase":     raw,
                    "normalizedKey": normalized_key,
                    "addedById":     resolved_by_id,
                    "alertId":       alert_id,
                }
            )

        # Enforce mutual exclusion: remove from blacklist if present
        # (whitelist always wins — admin is explicitly saying this phrase is OK)
        existing_bl = await db.moderationblacklist.find_first(
            where={"normalizedKey": normalized_key}
        )
        if existing_bl:
            await db.moderationblacklist.delete(where={"id": existing_bl.id})
            await invalidate_blacklist_cache()   # rebuild automata without the removed phrase

        await reload_static_filter()   # reload better-profanity with updated whitelist

    # ── Update alert row ──────────────────────────────────────
    await db.adminalert.update(
        where={"id": alert_id},
        data={
            "resolvedAction": action,
            "resolvedAt":     now,
            "resolvedById":   resolved_by_id,
        },
    )

    # ── Update content status ─────────────────────────────────
    if alert.commentId:
        updated_content = await db.comment.update(
            where={"id": alert.commentId},
            data={"status": new_content_status},
        )
    else:
        updated_content = await db.post.update(
            where={"id": alert.postId},
            data={"status": new_content_status},
        )

    await write_audit_log(
        event_type=AuditEventType.ALERT_RESOLVED,
        actor_type=AuditActorType.ADMIN,
        actor_id=resolved_by_id,
        entity_type=AuditEntityType.ALERT,
        entity_id=alert_id,
        parent_entity_type=AuditEntityType.POST,
        parent_entity_id=alert.postId,
        metadata={
            "resolvedAction":  action.value,
            "reportedUserId":  alert.reportedUserId,
            "postId":          alert.postId,
            "commentId":       alert.commentId,
            "flaggedPhrase":   alert.flaggedPhrase,
            "flagReason": (
                updated_content.flagReason.value
                if updated_content and updated_content.flagReason
                else None
            ),
        },
    )
