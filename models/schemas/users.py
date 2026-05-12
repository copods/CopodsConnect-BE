# models/schemas/users.py
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# ============================================================
# INVITE
# ============================================================

class InviteUsersRequest(BaseModel):
    """IN — invite one or more users to the app (creates MEMBER stub records)."""
    emails: List[EmailStr]

class InviteAdminsRequest(BaseModel):
    """IN — invite one or more admins to the panel (creates ADMIN stub records). SUPER_ADMIN only."""
    emails: List[EmailStr]

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
    role: str
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
    durationHours: int

class EditBanRequest(BaseModel):
    """IN — update ban duration, recalculated from now."""
    durationHours: int

# ============================================================
# ROLE CHANGE
# ============================================================

class ChangeRoleRequest(BaseModel):
    """IN — change role of an admin (ADMIN <-> MEMBER). SUPER_ADMIN only."""
    role: str  # accepts "MEMBER" or "ADMIN" only, validated in service layer