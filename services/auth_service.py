# services/auth_service.py
import os
import urllib.parse
import httpx
from datetime import datetime, timedelta, timezone
from jose import jwt as jose_jwt
from db.client import db
from prisma.enums import Role
from utils.exceptions import AppException
from constants import JWT_ALGORITHM
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
    Uses httpx to make async HTTP call to Google's token endpoint.
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


async def _get_or_create_user(user_info: dict):
    """
    Checks if user exists in DB by googleSub.
    If yes — updates name and picture in case they changed on Google.
    If no — creates new user.
    Returns the user object either way.
    Private function — only called by handle_google_callback.
    """
    email = user_info.get("email")
    google_sub = user_info.get("sub")
    name = user_info.get("name")
    picture = user_info.get("picture")

    if not email:
        raise AppException(400, "Email is required")

    existing_user = await db.user.find_unique(where={"email": email})

    if existing_user:
        user = await db.user.update(
            where={"email": email},
            data={"name": name, "picture": picture , "googleSub": google_sub}
        )
    else:
        user_data={
            "email":email,
            "name":name,
            "picture":picture,
            "role":Role.MEMBER
        }
        if google_sub:
            user_data["googleSub"] = google_sub

        user = await db.user.create(data=user_data)
        
    return user


def _create_jwt(user) -> str:
    """
    Creates your platform's own JWT session token.
    Contains user id, email, and role.
    Signed with JWT_SECRET, expires after JWT_EXPIRE_HOURS.
    """
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jose_jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def handle_google_callback(code: str) -> dict:
    print("=== CALLBACK STARTED ===")
    print("CODE RECEIVED:", code)
    print("GOOGLE_CLIENT_ID:", GOOGLE_CLIENT_ID)
    print("GOOGLE_CLIENT_SECRET:", "SET" if GOOGLE_CLIENT_SECRET else "NOT SET")
    print("GOOGLE_REDIRECT_URI:", GOOGLE_REDIRECT_URI)
    
    #Code is exchanged for access token
    tokens = await _exchange_code_for_tokens(code)
    print("TOKENS RECEIVED:", tokens)
    
    #access token is extracted from tokens
    access_token = tokens.get("access_token")
    print("ACCESS TOKEN:", "SET" if access_token else "NOT SET")

    #Check if access token is present
    if not access_token:
        raise AppException(400, "No access token received from Google")

    #User info is fetched using access token
    user_info = await _get_google_user_info(access_token)
    print("USER INFO:", user_info)
    
    #User is created or fetched from database
    user = await _get_or_create_user(user_info)
    print("USER OBJECT:", user)
    print("ROLE:", user.role)

    #Token is created using user object
    token = _create_jwt(user)

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