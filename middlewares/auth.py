# middlewares/auth.py
import os
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from db.client import db
from utils.exceptions import AppException
from constants import JWT_ALGORITHM

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    JWT auth dependency — inject into any route that requires authentication.
    Reads Bearer token from Authorization header.
    Verifies JWT → fetches user from DB → returns user.

    Usage in any protected route:
        @router.get("/protected")
        async def protected_route(current_user = Depends(get_current_user)):
            ...
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET"),
            algorithms=[JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise AppException(401, "Invalid token payload")
    except JWTError:
        raise AppException(401, "Invalid or expired token")

    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise AppException(401, "User no longer exists")

    return user