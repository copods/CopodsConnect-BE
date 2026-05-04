# models/schemas/workspace.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from prisma.enums import WorkspaceRole

class CreateWorkspaceRequest(BaseModel):
    """IN — body when superadmin creates a new workspace."""
    name:str
    description:Optional[str]=None
    allowedEmailDomains:List[str]=[]

class AddMemberRequest(BaseModel):
    """IN — body when adding a user to a workspace by email."""
    emails:List[EmailStr]

class UpdateMemberRoleRequest(BaseModel):
    """IN — body when changing a member's workspace role."""
    role:WorkspaceRole

class WorkspaceMemberOut(BaseModel):
    """OUT — A single member inside a workspace detail response."""
    id:str
    userId:str
    email:str
    name:Optional[str]=None
    role:WorkspaceRole

class WorkspaceOut(BaseModel):
    """OUT — lean workspace shape for dashboard listing."""
    id:str
    name:str
    ownerId:str
    memberCount:int

class WorkspaceDetailOut(BaseModel):
    """OUT - full workspace shape including members, for workspace detail page."""
    id:str
    name:str
    description:Optional[str]=None
    allowedEmailDomains:List[str]=[]
    ownerId:str
    memberCount:int
    members:List[WorkspaceMemberOut]

class AddMemberToWorkspaceResponse(BaseModel):
    """OUT — response when adding a member to a workspace.This is an Array of members"""
    id:str
    userId:str
    email:str
    name:Optional[str]=None
    role:WorkspaceRole

class UpdatedMemberResponse(BaseModel):
    """OUT — response when updating a member's role in a workspace."""
    id:str
    userId:str
    workspaceId:str
    role:WorkspaceRole

class RemoveMemberRequest(BaseModel):
    """IN — body when removing members from a workspace."""
    userIds:List[str]

class BulkRoleUpdateItem(BaseModel):
    """A single userId + role pair for bulk role update."""
    userId:str
    role:WorkspaceRole

class BulkUpdateMemberRolesRequest(BaseModel):
    """IN — list of userId + role pairs to update in one request."""
    updates:List[BulkRoleUpdateItem]

class UpdateWorkspaceRequest(BaseModel):
    """IN — body when updating a workspace."""
    name:Optional[str]=None
    description:Optional[str]=None
    allowedEmailDomains:Optional[List[str]]=None
    