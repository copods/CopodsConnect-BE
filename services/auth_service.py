# services/auth_service.py
import os
import urllib.parse
import httpx
from datetime import datetime, timedelta, timezone
from jose import jwt as jose_jwt
from db.client import db
from prisma.enums import Role
from utils.exceptions import AppException, GoogleLoginDomainDenied
from utils.ban_check import raise_if_user_ban_active
from utils.allowed_email import (
    COPODS_SIGNIN_DOMAIN,
    assert_copods_google_workspace,
    is_allowed_signin_email,
    normalize_email,
)
from constants import JWT_ALGORITHM, ALLOWED_EMAIL_DOMAIN
from models.schemas.auth import AuthResponse, UserOut, GoogleInitResponse
from services.user_service import derive_app_status, derive_panel_status
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests


GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def get_google_auth_url() -> dict:
    """
    Google OAuth URL. ``hd=copods.co`` limits the account picker to Copods Workspace
    accounts (Google may still offer "Use another account"). Server-side checks run
    before any JWT is issued — not after the client redirect.
    """
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "hd": COPODS_SIGNIN_DOMAIN,
    }
    return GoogleInitResponse(auth_url=f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}").model_dump()


async def _exchange_code_for_tokens(code: str, redirect_uri: str | None = None) -> dict:
    """
    Exchanges the one-time code from Google for access + id tokens.
    Private function — only called by handle_google_callback.
    """
    uri = redirect_uri or GOOGLE_REDIRECT_URI
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": uri,
                "grant_type": "authorization_code",
            }
        )

    if token_response.status_code != 200:
        raise AppException(400, "Failed to exchange code with Google")

    return token_response.json()


async def _get_google_user_info(access_token: str) -> dict:
    """
    Uses the access token to fetch the user's profile from Google.
    Returns email, name, picture, and Google's unique user ID (sub).
    Private function — only called by handle_google_callback.
    """
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )

    if user_response.status_code != 200:
        raise AppException(400, "Failed to fetch user info from Google")

    return user_response.json()


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


# ── Web / Panel flow ─────────────────────────────────────────────
# Used by POST /auth/google/callback (code exchange with platform)

async def _get_and_update_user(user_info: dict, platform: str):
    """
    Fetches an existing invited user by email and updates their profile fields
    (name, picture, googleSub) and login flags on OAuth callback.
    Never creates a new user.

    Domain check happens before any DB operation —
    if the email is not @copods.co, the request is rejected immediately.

    Pre-invited users (googleSub=null) are matched by email on first login
    and their name, picture, googleSub fields are filled in at that point.

    Sets hasLoggedInApp or hasLoggedInPanel based on platform.
    """
    email = normalize_email(user_info.get("email"))
    google_sub = user_info.get("sub")
    name = user_info.get("name")
    picture = user_info.get("picture")

    if not email:
        raise AppException(400, "Email not provided by Google")

    if not email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        raise AppException(
            403,
            f"Access restricted to @{ALLOWED_EMAIL_DOMAIN} accounts only"
        )

    if platform not in ("app", "panel"):
        raise AppException(400, "Invalid platform. Must be 'app' or 'panel'")

    login_flag = "hasLoggedInApp" if platform == "app" else "hasLoggedInPanel"

    existing_user = await db.user.find_unique(where={"email": email})

    if existing_user:
        if existing_user.deletedAt is not None:
            raise AppException(403, "This account has been deleted. Please contact your administrator.")
        if existing_user.isBanned:
            raise_if_user_ban_active(existing_user)
            await db.user.update(
                where={"id": existing_user.id},
                data={"isBanned": False, "bannedUntil": None, "banReason": None},
            )

        if platform == "panel" and existing_user.role == Role.MEMBER:
            raise AppException(403, "You do not have access to the admin panel")

        user = await db.user.update(
            where={"email": email},
            data={
                "name": name,
                "picture": picture,
                "googleSub": google_sub,
                login_flag: True
            }
        )
    else:
        raise AppException(403, "You have not been invited to this platform")

    if not is_allowed_signin_email(user.email):
        raise GoogleLoginDomainDenied()

    return user


# ── Mobile flow ───────────────────────────────────────────────────
# Used by POST /auth/google/verify (idToken from mobile client)

async def _get_or_create_user(user_info: dict, verified_email: str):
    """
    Mobile login: looks up user by googleSub, creates if not found.
    Domain check runs before any DB operation.
    """
    google_sub = user_info.get("sub")
    name = user_info.get("name")
    picture = user_info.get("picture")

    if not verified_email or not google_sub:
        raise AppException(400, "Google account missing required information")

    if not is_allowed_signin_email(verified_email):
        raise GoogleLoginDomainDenied()

    existing_user = await db.user.find_unique(where={"googleSub": google_sub})

    if existing_user:
        if not is_allowed_signin_email(existing_user.email):
            raise GoogleLoginDomainDenied()
        user = await db.user.update(
            where={"googleSub": google_sub},
            data={"name": name, "picture": picture, "email": verified_email},
        )
    else:
        user = await db.user.create(
            data={
                "email": verified_email,
                "googleSub": google_sub,
                "name": name,
                "picture": picture,
                "role": Role.MEMBER,
            }
        )

    if not is_allowed_signin_email(user.email):
        raise GoogleLoginDomainDenied()

    return user


def _create_jwt(user, platform: str = "app") -> str:
    """
    Creates the platform JWT session token.
    Contains user id, email, role, and platform.
    Signed with JWT_SECRET, expires after JWT_EXPIRE_HOURS.
    """
    email = normalize_email(user.email)
    if not is_allowed_signin_email(email):
        raise GoogleLoginDomainDenied()

    payload = {
        "sub": user.id,
        "email": email,
        "role": user.role,
        "platform": platform,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "org_domain": "copods.co",
    }
    return jose_jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def handle_google_callback(code: str, platform: str) -> dict:
    """
    Web / Panel OAuth callback flow:
    1. Exchange code for tokens
    2. Fetch user info from Google
    3. Validate domain + fetch and update invited user in DB
    4. Set hasLoggedInApp or hasLoggedInPanel based on platform
    5. Issue JWT with platform embedded
    6. Return token + user
    """
    tokens = await _exchange_code_for_tokens(code)

    access_token = tokens.get("access_token")
    if not access_token:
        raise AppException(400, "No access token received from Google")

    user_info = await _get_google_user_info(access_token)

    user = await _get_and_update_user(user_info, platform)

    token = _create_jwt(user, platform)

    return AuthResponse(
        token=token,
        user=UserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            picture=user.picture,
            role=str(user.role),
            appStatus=derive_app_status(user),
            panelStatus=derive_panel_status(user),
        )
    ).model_dump()


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
        user = await _get_or_create_user(user_info, email)
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
