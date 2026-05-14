# utils/ban_check.py
"""Shared ban evaluation for OAuth login and authenticated API requests."""
from datetime import datetime, timezone

from utils.exceptions import AppException

ACCOUNT_SUSPENDED_CODE = "ACCOUNT_SUSPENDED"


def raise_if_user_ban_active(user) -> None:
    """
    If the user has an active ban (permanent or time-bound and not yet elapsed),
    raises AppException(403) with message and structured data (code ACCOUNT_SUSPENDED).

    If not banned, returns immediately.
    If banned with an end time that has already passed, returns without raising;
    the caller should clear isBanned / bannedUntil / banReason in the database.
    """
    if not user.isBanned:
        return

    reason_text = (user.banReason or "").strip()
    reason_sentence = (
        f" Reason: {reason_text}" if reason_text else ""
    )

    if user.bannedUntil is None:
        msg = (
            "Your account has been permanently suspended."
            + reason_sentence
            + " Please contact your administrator."
        )
        raise AppException(
            403,
            msg,
            data={
                "code": ACCOUNT_SUSPENDED_CODE,
                "banReason": user.banReason,
                "bannedUntil": None,
                "permanent": True,
            },
        )

    now = datetime.now(timezone.utc)
    banned_until = (
        user.bannedUntil.replace(tzinfo=timezone.utc)
        if user.bannedUntil.tzinfo is None
        else user.bannedUntil
    )

    if now < banned_until:
        until_iso = banned_until.isoformat()
        msg = (
            f"Your account has been suspended until {until_iso}."
            + reason_sentence
            + " Please contact your administrator."
        )
        raise AppException(
            403,
            msg,
            data={
                "code": ACCOUNT_SUSPENDED_CODE,
                "banReason": user.banReason,
                "bannedUntil": until_iso,
                "permanent": False,
            },
        )
