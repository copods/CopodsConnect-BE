# models/schemas/auth.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from prisma.enums import Role


class GoogleCallbackRequest(BaseModel):
    """IN — receives code from frontend after Google redirects to frontend."""
    code: str
    state: Optional[str] = None


class GoogleInitResponse(BaseModel):
    """OUT — Step 1: returned when frontend requests Google OAuth URL."""
    auth_url: str


class UserOut(BaseModel):
    """OUT — Safe user shape sent to frontend after login."""
    id: str
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None
    role: str #plain str, not Role enum - avoids serialization issues 


class AuthResponse(BaseModel):
    """OUT — Complete response after successful Google OAuth login."""
    token: str
    user: UserOut