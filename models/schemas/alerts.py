# models/schemas/alerts.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from prisma.enums import AlertAction, ContentStatus, FlagReason
from enum import Enum


# ── Request DTOs (IN) ─────────────────────────────────────────

class ResolveAlertAction(str, Enum):
    RESTORE = "restore"
    CONFIRM_REMOVAL = "confirm_removal"


class ResolveAlertRequest(BaseModel):
    action: ResolveAlertAction


# ── Nested response shapes (OUT) ─────────────────────────────

class AlertPostMediaOut(BaseModel):
    url: str
    order: int

    model_config = {"from_attributes": True}


class AlertPostOut(BaseModel):
    id: str
    caption: Optional[str]
    status: ContentStatus
    flagReason: Optional[FlagReason]
    flaggedAt: Optional[datetime]
    createdAt: datetime
    media: list[AlertPostMediaOut]

    model_config = {"from_attributes": True}


class AlertUserOut(BaseModel):
    id: str
    name: Optional[str]
    email: str
    picture: Optional[str]
    designation: Optional[str]

    model_config = {"from_attributes": True}


class AlertResolvedByOut(BaseModel):
    id: str
    name: Optional[str]
    email: str

    model_config = {"from_attributes": True}


# ── Main alert response DTO (OUT) ─────────────────────────────

class AlertOut(BaseModel):
    id: str
    postId: str
    reportedUserId: str
    flagDetails: Optional[dict]
    resolvedAction: Optional[AlertAction]
    resolvedAt: Optional[datetime]
    resolvedById: Optional[str]
    createdAt: datetime
    post: Optional[AlertPostOut]
    reportedUser: Optional[AlertUserOut]
    resolvedBy: Optional[AlertResolvedByOut]

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    alerts: list[AlertOut]
    total: int
    page: int
    pageSize: int
    hasMore: bool

    model_config = {"from_attributes": True}


class ResolveAlertResponse(BaseModel):
    alertId: str
    action: ResolveAlertAction