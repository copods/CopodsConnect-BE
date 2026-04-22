from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class CustomException(Exception):
    """Custom exception for all intentional application errors."""
    def __init__(
        self,
        message: str = "Something went wrong.",
        status_code: int = 500,
        errors=None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.data = None
        self.success = False
        self.error = errors


async def custom_exception_handler(request: Request, exc: CustomException):
    """Handles all intentional errors raised via raise CustomException(...)"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": exc.success,
            "message": exc.message,
            "data": exc.data,
            "error": exc.error
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles Pydantic validation failures — wrong/missing fields in request body."""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation error. Please check the request body.",
            "data": None,
            "error": exc.errors()
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Catches any unexpected crash that was not explicitly handled."""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error.",
            "data": None,
            "error": str(exc)
        }
    )
