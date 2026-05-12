from fastapi import APIRouter, Depends
from middlewares.auth import get_current_user
from services import workspace_service
from utils.ApiResponse import api_response
from models.schemas.workspace import (
    CreateWorkspaceRequest,
    AddMemberRequest,
    UpdateMemberRoleRequest,
    RemoveMemberRequest,
    BulkUpdateMemberRolesRequest,
    UpdateWorkspaceRequest
)

workspace_router = APIRouter(prefix="/workspaces",tags=["workspaces"])

@workspace_router.post("")
async def create_workspace(
        body:CreateWorkspaceRequest,
        current_user = Depends(get_current_user),
    ):
        result = await workspace_service.create_workspace(current_user,body)
        return api_response(201,result,"Workspace created successfully")

@workspace_router.get("")
async def get_workspace(current_user=Depends(get_current_user)):
    result = await workspace_service.get_my_workspaces(current_user)
    return api_response(200,result,"Workspaces Fetched successfully")

@workspace_router.get("/{workspace_id}")
async def get_workspace_detail(
    workspace_id:str,
    current_user=Depends(get_current_user)
):
    result = await workspace_service.get_workspace_detail(current_user,workspace_id)
    return api_response(200,result,"Workspace detail fetched successfully")

@workspace_router.post("/{workspace_id}/members")
async def add_member(
    workspace_id:str,
    body:AddMemberRequest,
    current_user=Depends(get_current_user)
):
    result = await workspace_service.add_member_to_workspace(
            current_user, workspace_id, body.emails
        )
    return api_response(201, result,"Member added successfully")

@workspace_router.patch("/{workspace_id}/members/{user_id}/role")
async def update_member_role(
    workspace_id:str,
    user_id:str,
    body:UpdateMemberRoleRequest,
    current_user=Depends(get_current_user)
):
    result = await workspace_service.update_member_role(current_user, workspace_id,user_id,body.role)
    return api_response(200,result,"Member role updated successfully")

@workspace_router.get("/{workspace_id}/eligible-users")
async def get_eligible_users(
    workspace_id:str,
    search:str="",
    current_user=Depends(get_current_user)
):
    result = await workspace_service.get_eligible_users(
        current_user,
        workspace_id,
        search
    )
    return api_response(200, result, "Eligible users fetched successfully")

@workspace_router.delete("/{workspace_id}/members")
async def remove_members(
    workspace_id:str,
    body:RemoveMemberRequest,
    current_user=Depends(get_current_user),
):
    result = await workspace_service.remove_members_from_workspace(current_user,workspace_id,body.userIds)
    return api_response(200,result,"Members removed successfully")

@workspace_router.patch("/{workspace_id}/members/roles")
async def update_member_roles(
    workspace_id:str,
    body:BulkUpdateMemberRolesRequest,
    current_user=Depends(get_current_user)
):
    result = await workspace_service.bulk_update_member_roles(
            current_user, workspace_id, body.updates
        )
    return api_response(200,result , "Members roles updated successfully")

@workspace_router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id:str,
    body:UpdateWorkspaceRequest,
    current_user=Depends(get_current_user),
):
    result = await workspace_service.update_workspace(current_user,workspace_id,body)
    return api_response(200,result,"Workspace updated successfully.")
