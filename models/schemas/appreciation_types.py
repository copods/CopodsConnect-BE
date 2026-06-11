from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class CreateAppreciationTypeRequest(BaseModel):
    name: str
    emoji: str
    animationUrl: Optional[str] = None
    description: Optional[str] = None
    displayOrder: int = 0


class UpdateAppreciationTypeRequest(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None
    animationUrl: Optional[str] = None
    description: Optional[str] = None
    isActive: Optional[bool] = None
    displayOrder: Optional[int] = None


class AppreciationTypeOut(BaseModel):
    id: str
    name: str
    emoji: str
    animationUrl: Optional[str] = None
    description: Optional[str] = None
    isActive: bool
    displayOrder: int
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)