# models/schemas/alerts.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from prisma.enums import AlertAction, ContentStatus, FlagReason
from enum import Enum


# ── Request DTOs (IN) ─────────────────────────────────────────

class ResolveAlertAction(str, Enum):
    RESTORE         = "restore"
    CONFIRM_REMOVAL = "confirm_removal"
    BLACKLIST       = "blacklist"
    WHITELIST       = "whitelist"



class ResolveAlertRequest(BaseModel):
    action: ResolveAlertAction


# ── Nested response shapes (OUT) ─────────────────────────────

class AlertTaggedUserOut(BaseModel):
    id: str
    name: Optional[str]

class AlertTagOut(BaseModel):
    taggedUserId: str
    taggedUser: Optional[AlertTaggedUserOut]

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
    tags: Optional[list[AlertTagOut]] = None

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

class AlertCommentOut(BaseModel):
    id: str
    body: str
    createdAt: datetime
    tags: Optional[list[AlertTagOut]] = None
    model_config = {"from_attributes": True}

# ── Main alert response DTO (OUT) ─────────────────────────────

class AlertOut(BaseModel):
    id: str
    postId: str
    commentId: Optional[str] = None
    reportedUserId: str
    flagDetails: Optional[dict]
    flaggedPhrase: Optional[str] = None      # exact word/phrase the static layer or AI caught
    resolvedAction: Optional[AlertAction]
    resolvedAt: Optional[datetime]
    resolvedById: Optional[str]
    createdAt: datetime
    post: Optional[AlertPostOut]
    comment: Optional[AlertCommentOut] = None
    reportedUser: Optional[AlertUserOut]
    resolvedBy: Optional[AlertResolvedByOut]
    priorFlagCount: int = 0                  # how many times user was flagged — display only

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