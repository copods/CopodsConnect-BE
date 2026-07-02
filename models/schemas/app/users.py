# models/schemas/app/users.py
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class AppEditProfileTextRequest(BaseModel):
    """IN — editable text fields for the logged-in app user's own profile."""
    name: Optional[str] = None
    designation: Optional[str] = None
    birthdate: Optional[datetime] = None


class AppProfilePictureUploadUrlRequest(BaseModel):
    """IN — request a signed Supabase URL to upload a profile picture."""
    contentType: str = "image/jpeg"


class AppEditProfilePictureRequest(BaseModel):
    """IN — save the final Supabase public URL as the user's profile picture."""
    picture: str
