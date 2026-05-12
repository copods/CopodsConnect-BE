# services/auth_service.py
import os
import urllib.parse
import httpx
from datetime import datetime, timedelta, timezone
from jose import jwt as jose_jwt
from db.client import db
from prisma.enums import Role
from utils.exceptions import AppException
from constants import JWT_ALGORITHM, ALLOWED_EMAIL_DOMAIN
from models.schemas.auth import AuthResponse, UserOut

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def get_google_auth_url() -> str:
    """
    Builds the Google OAuth authorization URL.
    Frontend redirects user to this URL to begin login.
    No async needed — pure string construction.
    """
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def _exchange_code_for_tokens(code: str) -> dict:
    """
    Exchanges the one-time code from Google for access + id tokens.
    Private function — only called by handle_google_callback.
    """
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
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


async def _get_or_create_user(user_info: dict, platform: str):
    """
    Validates email domain, then gets or creates the user in DB.
    Private function — only called by handle_google_callback.

    Domain check happens before any DB operation —
    if the email is not @copods.co, the request is rejected immediately.

    Pre-invited users (googleSub=null) are matched by email on first login
    and their name, picture, googleSub fields are filled in at that point.

    Sets hasLoggedInApp or hasLoggedInPanel based on platform.
    """
    email = user_info.get("email")
    google_sub = user_info.get("sub")
    name = user_info.get("name")
    picture = user_info.get("picture")

    if not email:
        raise AppException(400, "Email not provided by Google")

    # --- Domain restriction ---
    if not email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        raise AppException(
            403,
            f"Access restricted to @{ALLOWED_EMAIL_DOMAIN} accounts only"
        )

    # --- Platform validation ---
    if platform not in ("app", "panel"):
        raise AppException(400, "Invalid platform. Must be 'app' or 'panel'")

    # --- Determine which login flag to set ---
    login_flag = "hasLoggedInApp" if platform == "app" else "hasLoggedInPanel"

    existing_user = await db.user.find_unique(where={"email": email})

    if existing_user:
        # Panel login — only ADMIN and SUPER_ADMIN should be able to access panel
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
        # No stub record exists — this person was never invited
        raise AppException(403, "You have not been invited to this platform")

    return user


def _create_jwt(user, platform: str) -> str:
    """
    Creates the platform JWT session token.
    Contains user id, email, role, and platform.
    Signed with JWT_SECRET, expires after JWT_EXPIRE_HOURS.
    """
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "platform": platform,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jose_jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def handle_google_callback(code: str, platform: str) -> dict:
    """
    Full OAuth callback flow:
    1. Exchange code for tokens
    2. Fetch user info from Google
    3. Validate domain + get or create user in DB
    4. Set hasLoggedInApp or hasLoggedInPanel based on platform
    5. Issue JWT with platform embedded
    6. Return token + user
    """
    tokens = await _exchange_code_for_tokens(code)

    access_token = tokens.get("access_token")
    if not access_token:
        raise AppException(400, "No access token received from Google")

    user_info = await _get_google_user_info(access_token)

    user = await _get_or_create_user(user_info, platform)

    token = _create_jwt(user, platform)

    return AuthResponse(
        token=token,
        user=UserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            picture=user.picture,
            role=str(user.role)
        )
    ).model_dump()