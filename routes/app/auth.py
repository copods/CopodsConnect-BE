from fastapi import APIRouter
from fastapi.routing import APIRoute

from models.schemas.app.auth import AppGoogleCallbackRequest
from services.app import auth_service as app_service 
from utils.ApiResponse import api_response

app_auth_router = APIRouter(
    prefix="/auth/app",
    tags=["App Auth"],
)

@app_auth_router.get("/google")
async def get_app_google_auth_url():
    result = await app_service.get_app_google_auth_url()
    return api_response(200, result.model_dump(), "Google Auth URL generated")

@app_auth_router.post("/google/callback")
async def app_google_callback(body: AppGoogleCallbackRequest):
    result = await app_service.handle_app_google_callback(body.code, body.platform)
    return api_response(
        200,
        result.model_dump(),
        "Logged In Successfully"
    )