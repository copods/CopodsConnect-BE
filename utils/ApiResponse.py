from typing import Any
from pydantic import BaseModel

class ApiResponse(BaseModel):
    data: Any
    message: str
    status: int
    success: bool