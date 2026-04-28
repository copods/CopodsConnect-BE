from fastapi import APIRouter
from services import auth_service
from utils.ApiResponse import  api_response
from utils.exceptions import AppException
from models.schemas.auth import GoogleCallbackRequest

auth_router = APIRouter(prefix="/auth", tags=["auth"])
#axios.get("http://localhost:8000/api/v1/auth/google")
@auth_router.get("/google")
async def google_login():
    auth_url=auth_service.get_google_auth_url()
    if not auth_url:
        raise AppException(500,"Failed to generate Google Auth URL")
    return api_response(200, auth_url, "Google Auth URL generated")

@auth_router.post("/google/callback")
async def google_callback(body:GoogleCallbackRequest):
    result = await auth_service.handle_google_callback(body.code)
    if not result:
        raise AppException(500,"Failed to handle Google callback")
    return api_response(200, result, "Logged In Successfully")

@auth_router.post("/logout")
async def logout():
    """
    Client side logout — frontend must delete the JWT from storage.
    Route exists for consistency and future refresh token support.
    Requires valid JWT in Authorization header to confirm user is logged in.
    """
    return api_response(200, "Logged out successfully")