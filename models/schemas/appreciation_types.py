# models/schemas/appreciation_types.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class AppreciationTypeOut(BaseModel):
    id: str
    name: str
    emojiPath: str
    description: Optional[str] = None
    isActive: bool
    displayOrder: int
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)