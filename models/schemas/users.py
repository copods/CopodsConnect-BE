# models/schemas/users.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional
from datetime import datetime

# ============================================================
# INVITE
# ============================================================

class InvitePersonRequest(BaseModel):
    """A single person to invite — email required, all other fields optional."""
    email: EmailStr
    name: Optional[str] = None
    designation: Optional[str] = None
    dateOfJoining: Optional[datetime] = None
    birthdate: Optional[datetime] = None

class InviteUsersRequest(BaseModel):
    """IN — invite one or more users with optional profile data."""
    people: List[InvitePersonRequest]

class InviteAdminsRequest(BaseModel):
    """IN — invite one or more admins with optional profile data. SUPER_ADMIN only."""
    people: List[InvitePersonRequest]

class BulkInviteRequest(BaseModel):
    pass  # no body fields — input is a file, handled by FastAPI UploadFile directly in route

class ResendInviteRequest(BaseModel):
    """IN — resend invite emails to existing users/admins. No new DB entry created."""
    emails: List[EmailStr]

# ============================================================
# USER OUT SHAPES
# ============================================================

class UserListItem(BaseModel):
    """OUT — single user row returned in list views."""
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    designation: Optional[str] = None
    dateOfJoining: Optional[datetime] = None
    birthdate: Optional[datetime] = None
    role: str
    status: str
    appStatus: str
    panelStatus: str
    isBanned: bool
    bannedUntil: Optional[datetime] = None
    hasLoggedInApp: bool
    hasLoggedInPanel: bool
    createdAt: datetime

# ============================================================
# DELETE
# ============================================================

class DeleteUserRequest(BaseModel):
    """IN — bulk delete users by ID list."""
    userIds: List[str]

# ============================================================
# BAN
# ============================================================

class BanUserRequest(BaseModel):
    """IN — ban a user/admin for a given number of hours from now."""
    durationHours: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def strip_ban_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Ban reason cannot be empty")
        return stripped


class EditBanRequest(BaseModel):
    """IN — update ban duration, recalculated from now; optional new reason text."""
    durationHours: int = Field(..., ge=1)
    reason: str | None = Field(None, max_length=2000)

    @field_validator("reason")
    @classmethod
    def strip_optional_ban_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

# ============================================================
# ROLE CHANGE
# ============================================================

class ChangeRoleRequest(BaseModel):
    """IN — change role of an admin (ADMIN <-> MEMBER). SUPER_ADMIN only."""
    role: str  # accepts "MEMBER" or "ADMIN" only, validated in service layer


class EditUserRequest(BaseModel):
    """IN — edit profile fields of a user. ADMIN and SUPER_ADMIN only."""
    name: Optional[str] = None
    designation: Optional[str] = None
    dateOfJoining: Optional[datetime] = None
    birthdate: Optional[datetime] = None