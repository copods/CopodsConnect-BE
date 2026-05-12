# routes/auth.py
from fastapi import APIRouter, Depends
from services import auth_service
from utils.ApiResponse import api_response
from models.schemas.auth import GoogleCallbackRequest, AuthResponse, GoogleInitResponse
from middlewares.auth import get_current_user

auth_router = APIRouter(prefix="/auth", tags=["auth"])

@auth_router.get("/google", response_model=GoogleInitResponse)
async def google_login():
    auth_url = auth_service.get_google_auth_url()
    return api_response(200, auth_url, "Google Auth URL generated")

@auth_router.post("/google/callback", response_model=AuthResponse)
async def google_callback(body: GoogleCallbackRequest):
    result = await auth_service.handle_google_callback(body.code, body.platform)
    return api_response(200, result, "Logged In Successfully")

@auth_router.post("/logout")
async def logout():
    """
    Client side logout — frontend must delete the JWT from storage.
    Route exists for consistency and future refresh token support.
    Requires valid JWT in Authorization header to confirm user is logged in.
    """
    return api_response(200, "Logged out successfully")

@auth_router.get("/me")
async def me(
    current_user=Depends(get_current_user)
):
    """
    Returns the current user's information.
    Requires valid JWT in Authorization header.
    """
    return api_response(200, current_user, "Current user information")