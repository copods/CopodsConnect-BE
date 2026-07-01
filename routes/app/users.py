# routes/app/users.py
from fastapi import APIRouter, Depends, Query
from middlewares.auth import get_current_user, require_platform
from services.app import user_search_service, user_service, storage_service
from utils.ApiResponse import api_response
from models.schemas.app.users import (
    AppEditProfileTextRequest,
    AppProfilePictureUploadUrlRequest,
    AppEditProfilePictureRequest,
)

app_users_router = APIRouter(
    prefix="/app/users",
    tags=["App Users"],
    dependencies=[Depends(require_platform("app"))],
)


@app_users_router.get("/search")
async def search_users(
    q: str = Query(default=""),
    current_user=Depends(get_current_user),
):
    result = await user_search_service.search_users(q.strip(), current_user.id)
    return api_response(200, result, "Users fetched successfully")


@app_users_router.put("/me")
async def edit_my_profile(
    body: AppEditProfileTextRequest,
    current_user=Depends(get_current_user),
):
    """Update the logged-in user's name and/or designation."""
    result = await user_service.update_user_profile_text(current_user.id, body)
    return api_response(200, result, "Profile updated successfully")


@app_users_router.post("/me/picture/upload-url")
async def get_picture_upload_url(
    body: AppProfilePictureUploadUrlRequest,
    current_user=Depends(get_current_user),
):
    """Request a signed Supabase URL to upload a new profile picture.
    The frontend uploads the image directly to Supabase using this URL,
    then calls PUT /me/picture with the resulting publicUrl.
    """
    result = await storage_service.create_avatar_upload_url(
        current_user.id,
        body.contentType,
    )
    return api_response(200, result, "Upload URL created")


@app_users_router.put("/me/picture")
async def update_my_picture(
    body: AppEditProfilePictureRequest,
    current_user=Depends(get_current_user),
):
    """Save the Supabase public URL as the user's profile picture.
    Call this after uploading the image to the signed URL from /me/picture/upload-url.
    """
    result = await user_service.update_user_profile_picture(current_user.id, body)
    return api_response(200, result, "Profile picture updated successfully")

@app_users_router.get("/{target_user_id}")
async def get_user_profile(
    target_user_id: str,
    current_user=Depends(get_current_user),
):
    """Fetch another user's highly optimized public profile details."""
    from db.client import db
    from utils.exceptions import AppException

    user = await db.user.find_unique(
        where={"id": target_user_id, "deletedAt": None}
    )
    if not user:
        raise AppException(404, "User not found")
        
    # Count appreciations directly in the endpoint
    sent_count = await db.appreciation.count(
        where={"senderId": user.id, "deletedAt": None}
    )
    received_count = await db.appreciationrecipient.count(
        where={"userId": user.id, "appreciation": {"deletedAt": None}}
    )
    
    # Send ONLY the exact data points you requested!
    public_profile_data = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "designation": user.designation,
        "dateOfJoining": user.dateOfJoining.isoformat() if user.dateOfJoining else None,
        "birthdate": user.birthdate.isoformat() if user.birthdate else None,
        "appreciationGivenCount": sent_count,
        "appreciationReceivedCount": received_count
    }
    
    return api_response(200, public_profile_data, "User fetched successfully")
