import os 
import urllib.parse

from utils.exceptions import AppException
from models.schemas.app.auth import (
    AppUserOut,
    AppGoogleAuthUrlResponse,
    AppAuthResponse,
)
from services.auth_service import (
    GOOGLE_AUTH_URL,
    GOOGLE_CLIENT_ID,
    _exchange_code_for_tokens,
    _get_google_user_info,
    _get_and_update_user,
    _create_jwt,
)

APP_GOOGLE_REDIRECT_URI = os.getenv("APP_GOOGLE_REDIRECT_URI")


def _build_google_auth_url(redirect_uri:str | None=None) -> str:
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }

    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

async def get_app_google_auth_url() -> AppGoogleAuthUrlResponse:
    if not APP_GOOGLE_REDIRECT_URI:
        raise AppException(400, "APP_GOOGLE_REDIRECT_URI is not configured")
    return AppGoogleAuthUrlResponse(
        auth_url = _build_google_auth_url(APP_GOOGLE_REDIRECT_URI)
    )

async def handle_app_google_callback(code:str,platform:str) -> AppAuthResponse:
    tokens = await _exchange_code_for_tokens(
        code,
        redirect_uri=APP_GOOGLE_REDIRECT_URI
    )

    access_token = tokens.get("access_token")
    if not access_token:
        raise AppException(400, "No access token received from Google")
    
    user_info = await _get_google_user_info(access_token)

    user = await _get_and_update_user(user_info, platform)

    token = _create_jwt(user, platform="app")

    return AppAuthResponse(
        token=token,
        user=AppUserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            picture=user.picture,
            designation=user.designation,
            dateOfJoining=user.dateOfJoining,
            birthdate=user.birthdate,
            role=str(user.role),
            hasLoggedInApp=user.hasLoggedInApp,
        )
    )

