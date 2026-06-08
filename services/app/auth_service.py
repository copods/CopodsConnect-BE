import os 
from utils.exceptions import AppException, GoogleLoginDomainDenied
from models.schemas.auth import (
    AuthResponse,
    UserOut,
)
from utils.allowed_email import (
    assert_copods_google_workspace,
    is_allowed_signin_email,
    normalize_email,
)
from utils.ban_check import raise_if_user_ban_active
from services.auth_service import (
    GOOGLE_CLIENT_ID,
    _exchange_code_for_tokens,
    _get_google_user_info,
    _get_and_update_user,
    _create_jwt,
)
from db.client import db
import httpx
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests


GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

async def _verify_google_id_token(id_token: str) -> dict:
    """Validate id_token with Google; returns claims (email, hd, aud, …)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_TOKENINFO_URL,
            params={"id_token": id_token},
        )
    if response.status_code != 200:
        raise GoogleLoginDomainDenied()
    claims = response.json()
    aud = claims.get("aud") or claims.get("azp")
    if aud != GOOGLE_CLIENT_ID:
        raise GoogleLoginDomainDenied()
    return claims


def _enforce_copods_signin_policy(user_info: dict, id_token_claims: dict | None) -> str:
    try:
        return assert_copods_google_workspace(
            userinfo=user_info,
            id_token_claims=id_token_claims,
        )
    except ValueError:
        raise GoogleLoginDomainDenied() from None




async def verify_google_id_token_flow(token: str) -> dict:
    """
    Mobile login flow: validates Google idToken directly (no code exchange).
    1. Verify idToken via google-auth library
    2. Enforce @copods.co domain
    3. Get or create user in DB
    4. Issue JWT
    """
    try:
        idinfo = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
        email = normalize_email(idinfo.get("email"))

        if not is_allowed_signin_email(email):
            raise GoogleLoginDomainDenied()

        user_info = {
            "email": email,
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
            "sub": idinfo.get("sub"),
        }
        user = await _get_or_create_user(user_info, email, platform="app")
        jwt_token = _create_jwt(user, "app")
        return {
            "token": jwt_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "role": str(user.role)
            }
        }
    except ValueError:
        raise AppException(401, "Invalid Google token")

# ── Mobile flow ───────────────────────────────────────────────────
# Used by POST /auth/google/verify (idToken from mobile client)

async def _get_or_create_user(user_info: dict, verified_email: str, platform: str):
    """
    Mobile login: fetch invited user by email and update profile/googleSub/login flag.
    Never creates a new user.
    """
    google_sub = user_info.get("sub")
    name = user_info.get("name")
    picture = user_info.get("picture")

    if not verified_email or not google_sub:
        raise AppException(400, "Google account missing required information")

    if not is_allowed_signin_email(verified_email):
        raise GoogleLoginDomainDenied()

    if platform != "app":
        raise AppException(400, "Invalid platform. Must be 'app'")

    existing_user = await db.user.find_unique(where={"email": verified_email})
    if not existing_user:
        raise AppException(403, "You have not been invited to this application")

    if existing_user.deletedAt is not None:
        raise AppException(403, "This account has been deleted. Please contact your administrator.")

    if existing_user.isBanned:
        raise_if_user_ban_active(existing_user)
        await db.user.update(
            where={"id": existing_user.id},
            data={"isBanned": False, "bannedUntil": None, "banReason": None},
        )

    user = await db.user.update(
        where={"email": verified_email},
        data={
            "googleSub": google_sub,
            # Only fill name/picture from Google if the user has not set their own yet
            **({
                "name": name,
            } if existing_user.name is None else {}),
            **({
                "picture": picture,
            } if existing_user.picture is None else {}),
            "hasLoggedInApp": True,
            # do NOT force role here; keep invite-assigned role
        },
    )

    if not is_allowed_signin_email(user.email):
        raise GoogleLoginDomainDenied()

    return user