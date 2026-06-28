# models/schemas/appreciation_types.py
from pydantic import BaseModel, ConfigDict , Field
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

class AppreciationTypeCreate(BaseModel):
    name:str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None , max_length=500)
    displayOrder : Optional[int] = Field(default=0)

class AppreciationTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None , min_length=1, max_length=100)
    description: Optional[str] = Field(default=None , max_length=500)
    displayOrder : Optional[int] = Field(default=None)

class ReorderItem(BaseModel):
    id:str
    displayOrder: int 

class AppreciationTypeReorderBody(BaseModel):
    items: list[ReorderItem]