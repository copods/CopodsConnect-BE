# routes/auth.py
from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
import os

from models.schemas.auth import GoogleCallbackRequest
from services import auth_service
from middlewares.auth import get_current_user
from utils.ApiResponse import api_response
from utils.exceptions import AppException, GoogleLoginDomainDenied
from services.user_service import serialize_user

MOBILE_REDIRECT_URI = os.getenv("MOBILE_REDIRECT_URI")

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.get("/google")
async def google_login():
    auth_url = auth_service.get_google_auth_url()
    return api_response(200, auth_url, "Google Auth URL generated")


@auth_router.post("/google/callback")
async def google_callback(body: GoogleCallbackRequest):
    """
    Web / Panel: exchange OAuth code with platform identifier.
    Only @copods.co receives a JWT; others get 403.
    """
    try:
        result = await auth_service.handle_google_callback(body.code, body.platform)
    except GoogleLoginDomainDenied:
        raise AppException(
            403,
            "Only @copods.co Google accounts are allowed to sign in.",
        )
    return api_response(200, result, "Logged In Successfully")


@auth_router.get("/google/callback")
async def google_callback_get(code: str):
    """
    Browser / misconfigured mobile redirect to the API host.
    Never issues a JWT via redirect — mobile must POST the code so Copods checks
    run before the app stores a session.
    """
    try:
        result = await auth_service.handle_google_callback(code, "app")
    except GoogleLoginDomainDenied:
        if MOBILE_REDIRECT_URI:
            query = urlencode({"oauth": "denied", "error": "access_denied"})
            return RedirectResponse(f"{MOBILE_REDIRECT_URI}?{query}")
        raise AppException(
            403,
            "Only @copods.co Google accounts are allowed to sign in.",
        )

    if MOBILE_REDIRECT_URI:
        query = urlencode({"oauth": "denied", "error": "use_post_callback"})
        return RedirectResponse(f"{MOBILE_REDIRECT_URI}?{query}")

    return api_response(200, result, "Logged In Successfully")


@auth_router.post("/google/verify")
async def verify_google_token(body: dict):
    """
    Mobile: verify Google idToken directly (no code exchange needed).
    Only @copods.co receives a JWT; others get 403.
    """
    try:
        id_token = body.get("idToken")
        if not id_token:
            raise AppException(400, "idToken is required")
        result = await auth_service.verify_google_id_token_flow(id_token)
        return api_response(200, result, "Logged In Successfully")
    except GoogleLoginDomainDenied:
        raise AppException(403, "Only @copods.co Google accounts are allowed.")


@auth_router.get("/me")
async def me(current_user=Depends(get_current_user)):
    """Returns the current user's information. Requires valid JWT."""
    return api_response(200, serialize_user(current_user), "Current user information")


@auth_router.post("/logout")
async def logout():
    """
    No authentication required. Logout is a client-side operation — the client
    discards the token. No server-side token invalidation is performed.
    """
    return api_response(200, "Logged out successfully")
