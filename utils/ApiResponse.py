# utils/ApiResponse.py
from fastapi.responses import JSONResponse
from typing import Any


def api_response(
    status_code: int,
    data: Any = None,
    message: str = "Success"
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": status_code < 400,
            "statusCode": status_code,
            "message": message,
            "data": data,
            "errors": []
        }
    )

#How to use this api response utility:
# from utils.ApiResponse import api_response

# # 200 - fetch
# return api_response(200, data=user, message="User fetched successfully")

# # 201 - create
# return api_response(201, data=new_post, message="Post created successfully")

# # 200 - no data to return
# return api_response(200, message="Password updated successfully")