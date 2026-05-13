# utils/ban_check.py
"""Shared ban evaluation for OAuth login and authenticated API requests."""
from datetime import datetime, timezone

from utils.exceptions import AppException


def raise_if_user_ban_active(user) -> None:
    """
    If the user has an active ban (permanent or time-bound and not yet elapsed),
    raises AppException(403).

    If not banned, returns immediately.
    If banned with an end time that has already passed, returns without raising;
    the caller should clear isBanned / bannedUntil in the database.
    """
    if not user.isBanned:
        return

    if user.bannedUntil is None:
        raise AppException(
            403,
            "Your account has been permanently suspended. Please contact your administrator.",
        )

    now = datetime.now(timezone.utc)
    banned_until = (
        user.bannedUntil.replace(tzinfo=timezone.utc)
        if user.bannedUntil.tzinfo is None
        else user.bannedUntil
    )

    if now < banned_until:
        raise AppException(
            403,
            f"Your account has been suspended until {banned_until.isoformat()}. Please contact your administrator.",
        )
