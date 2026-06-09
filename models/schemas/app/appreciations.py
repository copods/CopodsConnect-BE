# models/schemas/app/appreciations.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


# ── Request schemas ───────────────────────────────────────────

class CreateAppreciationRequest(BaseModel):
    appreciationTypeId: str
    message: Optional[str] = None
    recipientIds: list[str]


class UpdateAppreciationRequest(BaseModel):
    message: Optional[str] = None
    recipientIds: Optional[list[str]] = None


# ── Response schemas ──────────────────────────────────────────

class AppreciationTypeMinimalOut(BaseModel):
    id: str
    name: str
    emojiUrl: str
    description: Optional[str] = None
    displayOrder: int

    model_config = ConfigDict(from_attributes=True)


class AppreciationSenderOut(BaseModel):
    id: str
    name: Optional[str] = None
    picture: Optional[str] = None
    designation: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RecipientOut(BaseModel):
    id: str
    userId: str
    userName: Optional[str] = None
    userPicture: Optional[str] = None
    seenAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AppreciationOut(BaseModel):
    id: str
    senderId: str
    sender: Optional[AppreciationSenderOut] = None
    appreciationTypeId: str
    appreciationType: Optional[AppreciationTypeMinimalOut] = None
    message: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    recipients: list[RecipientOut] = []

    model_config = ConfigDict(from_attributes=True)


class AppreciationListResponse(BaseModel):
    appreciations: list[AppreciationOut]
    total: int
    page: int
    pageSize: int


class MarkSeenResponse(BaseModel):
    appreciationId: str
    seenAt: datetime


class DeleteAppreciationResponse(BaseModel):
    deletedAppreciationId: str