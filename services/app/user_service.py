# services/app/user_service.py
from db.client import db
from models.schemas.app.users import AppEditProfileTextRequest, AppEditProfilePictureRequest
from services.user_service import serialize_user
from utils.exceptions import AppException


async def update_user_profile_text(user_id: str, data: AppEditProfileTextRequest):
    """Update name and/or designation of the logged-in user."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise AppException(400, "No valid fields provided for update")

    updated_user = await db.user.update(
        where={"id": user_id},
        data=update_data,
    )
    return serialize_user(updated_user)


async def update_user_profile_picture(user_id: str, data: AppEditProfilePictureRequest):
    """Save the Supabase public URL as the user's profile picture."""
    updated_user = await db.user.update(
        where={"id": user_id},
        data={"picture": data.picture},
    )
    return serialize_user(updated_user)
