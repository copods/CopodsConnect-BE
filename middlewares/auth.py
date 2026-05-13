# middlewares/auth.py
import os
import asyncio
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from db.client import db
from utils.exceptions import AppException
from utils.ban_check import raise_if_user_ban_active
from constants import JWT_ALGORITHM
from prisma.enums import Role

security = HTTPBearer()


# ============================================================
# INTERNAL HELPER — never used directly in routes
# ============================================================

async def _clear_expired_ban(user_id: str):
    """
    Silently clears ban fields when a ban has naturally expired.
    Runs as a background task — never blocks the request.
    """
    try:
        await db.user.update(
            where={"id": user_id},
            data={
                "isBanned": False,
                "bannedUntil": None
            }
        )
    except Exception:
        pass


# ============================================================
# 1. IDENTITY — who is this person?
# ============================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Verifies JWT and returns the current user.
    Also checks if the user is banned.

    Use on any route that requires the user to be logged in.
    Does NOT check roles — that is the job of the role guards below.

    Usage:
        @router.get("/profile")
        async def get_profile(current_user = Depends(get_current_user)):
            ...
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET"),
            algorithms=[JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise AppException(401, "Invalid token payload")
    except JWTError:
        raise AppException(401, "Invalid or expired token")

    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise AppException(401, "User no longer exists")

    # Ban check — same rules as OAuth login (utils.ban_check.raise_if_user_ban_active)
    if user.isBanned:
        raise_if_user_ban_active(user)
        # Expired temporary ban — let through, clean up silently in background
        asyncio.create_task(_clear_expired_ban(user.id))

    return user


# ============================================================
# 2. AUTHORIZATION — is this person allowed here?
# ============================================================

async def require_admin(
    current_user=Depends(get_current_user)
):
    """
    Allows ADMIN and SUPER_ADMIN only.

    Use on admin panel routes — invite users, delete users, ban users,
    view violations, view platform stats etc.

    Usage:
        @router.post("/users/invite")
        async def invite(current_user = Depends(require_admin)):
            ...
    """
    if current_user.role not in (Role.ADMIN, Role.SUPER_ADMIN):
        raise AppException(403, "Forbidden: Admin access required")
    return current_user


async def require_super_admin(
    current_user=Depends(get_current_user)
):
    """
    Allows SUPER_ADMIN only.

    Use on routes that only the super admin can access —
    promoting/demoting admins, inviting admins, deleting admins,
    banning admins etc.

    Usage:
        @router.patch("/users/{user_id}/role")
        async def update_role(current_user = Depends(require_super_admin)):
            ...
    """
    if current_user.role != Role.SUPER_ADMIN:
        raise AppException(403, "Forbidden: Super Admin access required")
    return current_user


# ============================================================
# 3. PLATFORM GUARD — optional, wire only if needed
# ============================================================

def require_platform(expected_platform: str):
    """
    Returns a dependency that checks the platform field in the JWT.
    Use if app and panel share the same backend and you want to
    prevent a panel JWT from being used on app routes or vice versa.

    Usage:
        @router.get("/app/profile")
        async def profile(current_user = Depends(require_platform("app"))):
            ...
    """
    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        token = credentials.credentials
        try:
            payload = jwt.decode(
                token,
                os.getenv("JWT_SECRET"),
                algorithms=[JWT_ALGORITHM]
            )
        except JWTError:
            raise AppException(401, "Invalid or expired token")

        platform = payload.get("platform")
        if platform != expected_platform:
            raise AppException(403, f"This token is not valid for the {expected_platform}.")

        # Re-use get_current_user logic by calling it directly
        from fastapi.security import HTTPAuthorizationCredentials as HAC
        from fastapi import Request
        return await get_current_user(credentials)

    return _check