from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "data": None,
            "msg": "Validation error",
            "status": False,
            "err": exc.errors()
        }
    )

async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "data": None,
            "msg": "Internal server error",
            "status": False,
            "err": str(exc)
        }
    )