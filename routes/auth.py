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
from services.user_service import serialize_user_with_counts

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
    result = await auth_service.handle_google_callback(body.code, body.platform)
    return api_response(200, result, "Logged In Successfully")



@auth_router.get("/me")
async def me(current_user=Depends(get_current_user)):
    """Returns the current user's information. Requires valid JWT."""
    user_data = await serialize_user_with_counts(current_user)
    return api_response(200, user_data, "Current user information")


@auth_router.post("/logout")
async def logout():
    """
    No authentication required. Logout is a client-side operation — the client
    discards the token. No server-side token invalidation is performed.
    """
    return api_response(200, "Logged out successfully")
