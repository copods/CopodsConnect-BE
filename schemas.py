from pydantic import BaseModel
from typing import Any, Optional

class APIResponse(BaseModel):
    data: Optional[Any] = None
    msg: str
    status: bool
    err: Optional[Any] = None