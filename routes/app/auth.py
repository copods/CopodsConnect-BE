from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute

from models.schemas.app.auth import AppGoogleCallbackRequest
from services.app import auth_service as app_service 
from utils.ApiResponse import api_response
from utils.exceptions import AppException, GoogleLoginDomainDenied
from urllib.parse import urlencode
from fastapi.responses import RedirectResponse
import os
from middlewares.auth import get_current_user
from services.user_service import serialize_user
MOBILE_REDIRECT_URI = os.getenv("MOBILE_REDIRECT_URI")
import services.auth_service as auth_service
app_auth_router = APIRouter(
    prefix="/auth/app",
    tags=["App Auth"],
)


@app_auth_router.get("/google")
async def google_login():
    auth_url = auth_service.get_google_auth_url()
    return api_response(200, auth_url, "Google Auth URL generated")

@app_auth_router.get("/google/callback")
async def google_callback_get(code: str):
    """
    Browser / misconfigured mobile redirect to the API host.
    Never issues a JWT via redirect — mobile must POST the code so Copods checks
    run before the app stores a session.
    """
    try:
        result = await app_service.handle_google_callback(code, "app")
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

@app_auth_router.post("/google/verify")
async def verify_google_token(body: dict):
    """
    Mobile: verify Google idToken directly (no code exchange needed).
    Only @copods.co receives a JWT; others get 403.
    """
    try:
        id_token = body.get("idToken")
        if not id_token:
            raise AppException(400, "idToken is required")
        result = await app_service.verify_google_id_token_flow(id_token)
        return api_response(200, result, "Logged In Successfully")
    except GoogleLoginDomainDenied:
        raise AppException(403, "Only @copods.co Google accounts are allowed.")

@app_auth_router.get("/me")
async def me(current_user=Depends(get_current_user)):
    """Returns the current user's information. Requires valid JWT."""
    return api_response(200, serialize_user(current_user), "Current user information")