# utils/exceptions.py
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from prisma.errors import PrismaError


class GoogleLoginDomainDenied(Exception):
    """Email is outside ALLOWED_DOMAIN — OAuth callback returns redirect with error."""

    pass


class AppException(Exception):
    """Single custom exception for all intentional application errors."""
    def __init__(
        self,
        status_code: int = 500,
        message: str = "Something went wrong.",
        errors=None,
        data=None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.errors = errors or []
        self.data = data
        self.success = False


# --- Handlers (registered in main.py) ---

async def app_exception_handler(request: Request, exc: AppException):
    """Handles all intentional errors raised via raise AppException(...)"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "statusCode": exc.status_code,
            "message": exc.message,
            "data": exc.data,
            "errors": exc.errors
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles Pydantic validation failures — wrong/missing fields in request body."""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "statusCode": 422,
            "message": "Validation error. Please check the request body.",
            "data": None,
            "errors": exc.errors()
        }
    )


async def prisma_exception_handler(request: Request, exc: PrismaError):
    """Handles Prisma/DB failures — connection issues, constraint violations etc."""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "statusCode": 500,
            "message": "Database operation failed.",
            "data": None,
            "errors": []
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Catches any unexpected crash that was not explicitly handled."""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "statusCode": 500,
            "message": "Internal server error.",
            "data": None,
            "errors": []
        }
    )

    
# # =============================================================================
# # HOW TO USE AppException — raise it yourself when YOU detect a problem
# # =============================================================================

# # --- 404: Resource not found ---
# user = await db.user.find_unique(where={"id": user_id})
# if not user:
#     raise AppException(404, "User not found")

# post = await db.post.find_unique(where={"id": post_id})
# if not post:
#     raise AppException(404, "Post not found")

# # --- 409: Conflict / already exists ---
# existing_user = await db.user.find_unique(where={"email": email})
# if existing_user:
#     raise AppException(409, "Email already registered")

# # --- 401: Not authenticated ---
# if not token:
#     raise AppException(401, "No token provided. Please log in.")

# # Token is present but invalid/expired
# if not decoded_token:
#     raise AppException(401, "Invalid or expired token. Please log in again.")

# # --- 403: Authenticated but not allowed ---
# if user.role != UserRole.ADMIN:
#     raise AppException(403, "You do not have permission to perform this action")

# # --- 400: Bad request / business logic violation ---
# if new_password != confirm_password:
#     raise AppException(400, "Passwords do not match")

# if user.id == target_user_id:
#     raise AppException(400, "You cannot follow yourself")

# # Already following someone (Copods specific)
# existing_follow = await db.follow.find_first(where={"followerId": user.id, "followingId": target_id})
# if existing_follow:
#     raise AppException(400, "You are already following this user")

# # --- 500: You know something went wrong server side ---
# token_saved = await db.user.update(where={"id": user.id}, data={"refreshToken": refresh_token})
# if not token_saved:
#     raise AppException(500, "Failed to save session. Please try again.")


# # =============================================================================
# # HOW Pydantic's RequestValidationError works — YOU never raise this
# # Pydantic raises it automatically when request body doesn't match schema
# # Your handler just reformats it into your consistent shape
# # =============================================================================

# # Example schema in models/schemas.py:
# class UserRegisterSchema(BaseModel):
#     username: str
#     email: EmailStr
#     password: str

# # If client sends this request body:
# # { "username": "krishna" }   ← missing email and password

# # Pydantic automatically raises RequestValidationError
# # Your validation_exception_handler catches it and returns:
# # {
# #     "success": false,
# #     "statusCode": 422,
# #     "message": "Validation error. Please check the request body.",
# #     "data": null,
# #     "errors": [
# #         { "loc": ["body", "email"], "msg": "field required", "type": "missing" },
# #         { "loc": ["body", "password"], "msg": "field required", "type": "missing" }
# #     ]
# # }
# # YOU write zero code for this — it's fully automatic


# # =============================================================================
# # HOW Prisma's PrismaError works — YOU never raise this
# # Prisma raises it automatically when a DB operation fails
# # Your handler catches it and hides internal details from the client
# # =============================================================================

# # These are situations where Prisma raises PrismaError on its own:

# # 1. DB connection is down
# await db.user.find_many()  # Prisma raises PrismaError → your handler returns 500

# # 2. Unique constraint violated at DB level (even if you forgot to check)
# await db.user.create(data={"email": "already@exists.com"})  # Prisma raises PrismaError

# # 3. Foreign key constraint violated
# await db.post.create(data={"authorId": "nonexistent-id"})  # Prisma raises PrismaError

# # 4. Supabase DB is temporarily unavailable
# await db.recognition.find_many()  # Prisma raises PrismaError → your handler returns:
# # {
# #     "success": false,
# #     "statusCode": 500,
# #     "message": "Database operation failed.",
# #     "data": null,
# #     "errors": []    ← intentionally empty, never expose DB internals to client
# # }


# # =============================================================================
# # HOW generic_exception_handler works — catches everything else
# # For bugs and crashes you didn't anticipate
# # =============================================================================

# # Example: you made a typo accessing a variable that doesn't exist
# user_data = None
# print(user_data.email)  # AttributeError — you didn't raise this, it's a bug

# # generic_exception_handler catches it and returns:
# # {
# #     "success": false,
# #     "statusCode": 500,
# #     "message": "Internal server error.",
# #     "data": null,
# #     "errors": []
# # }
# # Client gets a clean response, not a Python traceback
# # You see the full traceback in your server logs for debugging


# # =============================================================================
# # QUICK DECISION GUIDE — which one to use?
# # =============================================================================

# # Q: Did YOU detect the problem in your own code?
# #    → raise AppException(status_code, "message")

# # Q: Did the client send a malformed/incomplete request body?
# #    → Don't write anything — Pydantic + your handler covers it automatically

# # Q: Did a DB query fail?
# #    → Don't write anything — Prisma + your handler covers it automatically

# # Q: Is it a bug/crash you didn't expect?
# #    → Don't write anything — generic_exception_handler covers it automatically