from db.client import db
from prisma.enums import Role , WorkspaceRole
from utils.exceptions import AppException
from models.schemas.workspace import WorkspaceOut ,WorkspaceDetailOut , AddMemberToWorkspaceResponse, UpdatedMemberResponse,WorkspaceMemberOut

async def create_workspace(current_user,body) -> dict:
    """Create new workspace
    Only platform SuperAdmins can call this. 
    Creator is automatically added as the workspace SUPER_ADMIN member.
    """
    if current_user.role!=Role.SUPER_ADMIN:
        raise AppException(403,"Only Platform SuperAdmins can create Workspaces.")
    
    # TODO: Implement workspace creation logic
    # - Validate input parameters
    # - Check for duplicate workspace name
    # - Create workspace record in database
    # - Add creator as SUPER_ADMIN member
    # - Return created workspace object
    if not body.name or not body.name.strip():
        raise AppException(400,"Workspace name is required.")
    
    if not body.allowedEmailDomains:
        raise AppException(400,"At least one allowed email domain is required.")

    #create workspace
    workspace = await db.workspace.create(
        data={
            "name":body.name,
            "description":body.description,
            "ownerId":current_user.id,
            "allowedEmailDomains":body.allowedEmailDomains
        }
    )

    if not workspace:
        raise AppException(500,"Failed to create workspace.")

    #Auto-add creator as SuperAdmin member
    member = await db.workspacemember.create(
        data={
            "userId":current_user.id,
            "workspaceId":workspace.id,
            "role":WorkspaceRole.SUPER_ADMIN,
        }
    )
    
    if not member:
        raise AppException(500,"Failed to add creator as workspace member.")
    
    return WorkspaceOut(
        id=workspace.id,
        name=workspace.name,
        ownerId=workspace.ownerId,
        memberCount=1
    ).model_dump()

async def get_my_workspaces(current_user)->list:
    """
    SUPER_ADMIN → all workspaces they own.
    ADMIN / MEMBER → all workspaces they are a member of.
    """
    """Get all workspaces the current user is a member of"""
    # TODO: Implement workspace retrieval logic
    # - Query workspaces where user is a member
    # - Return list of workspaces with user's role
    # - Handle pagination if needed

    if current_user.role==  Role.SUPER_ADMIN:
        workspaces = await db.workspace.find_many(
            where={"ownerId":current_user.id},
            include={"members":True}
        )

        return [
            WorkspaceOut(
                id=w.id,
                name=w.name,
                ownerId=w.ownerId,
                memberCount=len(w.members)
            ).model_dump()
            for w in workspaces
        ]
    else:
        memberships = await db.workspacemember.find_many(
            where={"userId":current_user.id},
            include={"workspace":{"include":{"members":True}}}
        )
        return [
            WorkspaceOut(
                id=m.workspace.id,
                name=m.workspace.name,
                ownerId=m.workspace.ownerId,
                memberCount=len(m.workspace.members)
            ).model_dump()
            for m in memberships
        ]


async def get_workspace_detail(current_user, workspace_id:str) -> dict:
    """
    Returns full workspace detail including members list.
    User must be a member of the workspace to view it.
    Platform SUPER_ADMIN (owner) can always view.
    """
    # TODO: Implement workspace detail retrieval logic
    # - Validate workspace exists
    # - Check if user is a member of the workspace
    # - Return workspace details with members list
    # - Handle permission checks based on user role
    workspace = await db.workspace.find_unique(
        where={"id":workspace_id},
        include={"members":{"include":{"user":True}}}
    )
    if not workspace:
        raise AppException(404,"Workspace not found.")
    
    #Check access - must be owner or a member 
    is_member = any(m.userId == current_user.id for m in workspace.members)

    if not is_member:
        raise AppException(403,"You are not a member of this workspace.")
    
    members=[
        WorkspaceMemberOut(
            id=m.id,
            userId=m.userId,
            email=m.user.email,
            name=m.user.name,
            role=m.role
        )
        for m in workspace.members
    ]

    return WorkspaceDetailOut(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        allowedEmailDomains=workspace.allowedEmailDomains,
        ownerId=workspace.ownerId,
        memberCount=len(workspace.members),
        members=members
    ).model_dump()

async def add_member_to_workspace(current_user,workspace_id:str,emails:list)->dict:
    """
    Adds a member to a workspace.
    Only workspace owner or platform SUPER_ADMIN can add members.
    """
    # TODO: Implement member addition logic
    # - Validate workspace exists
    # - Check if user is allowed to add members (owner or SUPER_ADMIN)
    # - Create workspace member record
    # - Return success response
    workspace = await db.workspace.find_unique(
        where={"id":workspace_id}
    )
    if not workspace:
        raise AppException(404,"Workspace not found")
    
    #verify user is workspace admin or superadmin
    caller_membership = await db.workspacemember.find_unique(
        where={
            'userId_workspaceId':{
                "userId":current_user.id,
                "workspaceId":workspace_id
            }
        }
    )
    if not caller_membership or caller_membership.role == WorkspaceRole.MEMBER  :
        raise AppException(403,"You do not have permission to add members to this workspace.")

    #find target user emails 
    added=[]
    skipped=[]
    for email in emails:
        target_user = await db.user.find_unique(
            where={"email":email}
        )
        if not target_user:
            skipped.append({"email":email,"reason":"User Not Found in system"})
            continue

        existing = await db.workspacemember.find_unique(
            where={
                "userId_workspaceId":{
                    "userId":target_user.id,
                    "workspaceId":workspace_id
                }
            }
        )

        if existing:
            skipped.append({"email":email,"reason":"User is already a member of this workspace"}) 
            continue

        member =await db.workspacemember.create(
            data={
                "userId":target_user.id,
                "workspaceId":workspace_id,
                "role":WorkspaceRole.MEMBER,
            }
        )       
        added.append(AddMemberToWorkspaceResponse(
            id=member.id,
            userId=target_user.id,
            email=target_user.email,
            name=target_user.name,
            role=member.role
        ).model_dump())

    return {"added":added,"skipped":skipped}

    
async def update_member_role(current_user,workspace_id:str,target_user_id:str,new_role:WorkspaceRole)->dict:
    """
    Changes a member's workspace role.
    Only workspace SUPER_ADMIN can do this.
    Cannot change your own role.
    """
    workspace=await db.workspace.find_unique(
        where={
            "id":workspace_id
        }
    )
    if not workspace:
        raise AppException(404,"Workspace not found")
    
    #verify user is workspace superadmin
    caller_membership=await db.workspacemember.find_unique(
        where={
            "userId_workspaceId":{
                "userId":current_user.id,
                "workspaceId":workspace_id
            }
        }
    )
    if not caller_membership or caller_membership.role != WorkspaceRole.SUPER_ADMIN:
        raise AppException(403,"You do not have permission to update member roles in this workspace.")
    
    #prevent self role change
    if target_user_id == current_user.id:
        raise AppException(400,"You cannot change your own role.")
    
    #check target is a member
    target_member = await db.workspacemember.find_unique(
        where={
            "userId_workspaceId":{
                "userId":target_user_id,
                "workspaceId":workspace_id
            }
        }
    )
    if not target_member:
        raise AppException(404,"Target user is not a member of this workspace.")
    
    #update role
    updated_member = await db.workspacemember.update(
        where={
            "userId_workspaceId":{
                "userId":target_user_id,
                "workspaceId":workspace_id
            }
        },
        data={
            "role":new_role
        }
    )
    return UpdatedMemberResponse(
        id=updated_member.id,
        userId=updated_member.userId,
        workspaceId=updated_member.workspaceId,
        role=updated_member.role
    ).model_dump()

async def get_eligible_users(
    current_user,
    workspace_id:str,
    search:str=""
) -> list:
    """
    Returns users eligible to be added to a workspace.
    Searches by email or name, excludes existing members.
    """
    # TODO: Implement user search and filtering logic
    # - Search users by email or name (case-insensitive)
    # - Exclude users who are already members of the workspace
    # - Return paginated results
    # - Include user details (id, email, name)
    
    # Placeholder implementation
    """
    Returns users who:
    1. Have an email domain matching one of the workspace's allowedEmailDomains
    2. Are NOT yet a member of this workspace
    3. Optionally filtered by name or email search string

    Only workspace SUPER_ADMIN or ADMIN can call this.
    """
    workspace= await db.workspace.find_unique(
        where={"id":workspace_id}
    )
    if not workspace:
        raise AppException(404,"Workspace not found")
    
    #verify caller is workspace admin or superadmin
    caller_membership = await db.workspacemember.find_unique(
        where={
            "userId_workspaceId":{
                "userId":current_user.id,
                "workspaceId":workspace_id
            }
        }
    )

    if not caller_membership or caller_membership.role == WorkspaceRole.MEMBER:
        raise AppException(403,"Only workspace admins or superadmins can manage members.")

    #get all current member user ids to exclude them from search
    existing_members= await db.workspacemember.find_many(
        where={
            "workspaceId":workspace_id
        }
    )
    existing_member_ids={m.userId for m in existing_members}

    #fetch all users and filter in python
    #(Prisma-client-py doesn't support OR on array contains cleanly in one query)

    all_users= await db.user.find_many()
    
    eligible=[]
    for user in all_users:
        #skip already members
        if user.id in existing_member_ids:
            continue
        
        #check domain match
        user_domain= user.email.split("@")[-1]
        if user_domain not in workspace.allowedEmailDomains:
            continue

        #Apply search filter if provided
        if search:
            search_lower = search.lower()
            name_match=user.name and search_lower in user.name.lower()
            email_match=user.email and search_lower in user.email.lower()
            if not name_match and not email_match:
                continue 
            
        eligible.append({
            "id":user.id,
            "email":user.email,
            "name":user.name,
            "picture":user.picture,
        })

    return eligible

async def remove_members_from_workspace(
    current_user,
    workspace_id:str,
    user_ids:list[str]
)->dict:
    """
    Removes one or more members from a workspace.
    Only workspace SUPER_ADMIN or ADMIN can do this.
    Cannot remove yourself.
    Deletes WorkspaceMember record only — user stays on platform.
    """
    workspace = await db.workspace.find_unique(
        where={
            "id":workspace_id
        }
    )

    if not workspace:
        raise AppException(404, "Workspace Not Found")

    caller_membership= await db.workspacemember.find_unique(
        where={
            "userId_workspaceId":{
                "userId":current_user.id,
                "workspaceId":workspace_id
            }
        }
    )

    if not caller_membership or caller_membership.role == WorkspaceRole.MEMBER:
        raise AppException(403, "Only workspace admins or superadmins can remove members.")

    removed=[]
    skipped=[]

    for user_id in user_ids:
        if user_id == current_user.id:
            skipped.append({"userId":user_id, "reason":"Cannot remove yourself"})
            continue
        
        existing = await db.workspacemember.find_unique(
            where={
                "userId_workspaceId":{
                    "userId":user_id,
                    "workspaceId":workspace_id
                }
            }
        )

        if not existing:
            skipped.append({"userId":user_id, "reason":"User is not the member of this workspace."})
            continue
        
        await db.workspacemember.delete(
            where={
                "userId_workspaceId":{
                    "userId":user_id,
                    "workspaceId":workspace_id
                }
            }
        )

        removed.append({"userId":user_id})

    return {
        "removed":removed,
        "skipped":skipped
    }


async def bulk_update_member_roles(
    current_user,
    workspace_id:str,
    updates:list
) -> dict:
    """
    Updates roles for multiple members in one request.
    Only workspace SUPER_ADMIN can do this.
    Cannot change your own role.
    """
    workspace= await db.workspace.find_unique(
        where={
            "id":workspace_id
        }
    )

    if not workspace:
        raise AppException(404, "Workspace Not Found")
    
    caller_membership = await db.workspacemember.find_unique(
        where={
            "userId_workspaceId":{
                "userId":current_user.id,
                "workspaceId":workspace_id
            }
        }
    )

    if not caller_membership or caller_membership.role != WorkspaceRole.SUPER_ADMIN:
        raise AppException(403, "Only workspace superadmins can update member roles.")
    
    updated=[]
    skipped=[]

    for item in updates:
        user_id = item.userId
        new_role = item.role

        if user_id == current_user.id:
            skipped.append({"userId":user_id,"reason":"Cannot change your own role"})    
            continue
        
        target_member = await db.workspacemember.find_unique(
            where={
                "userId_workspaceId":{
                    "userId":user_id,
                    "workspaceId":workspace_id
                }
            }
        )

        if not target_member:
            skipped.append({"userId":user_id, "reason":"User is not a member of this workspace"})
            continue
        
        update_member = await db.workspacemember.update(
            where={
                "userId_workspaceId":{
                    "userId":user_id,
                    "workspaceId":workspace_id
                }
            },
            data={
                "role":new_role
            }
        )
        updated.append(
            UpdatedMemberResponse(
                id=update_member.id,
                userId=update_member.userId,
                role=update_member.role,
                workspaceId=update_member.workspaceId
            ).model_dump()
        )

    return {"updated":updated, "skipped":skipped}

async def update_workspace(
    current_user,
    workspace_id:str,
    body
) -> dict:
    """
    Updates workspace name, description, or allowedEmailDomains.
    Only workspace SUPER_ADMIN can do this.
    Only provided fields are updated — others stay unchanged.
    """
    workspace= await db.workspace.find_unique(
        where={
            "id":workspace_id
        }
    )

    if not workspace:
        raise AppException(404, "Workspace Not Found")
    
    # TODO: Add logic to update workspace fields
    caller_membership = await db.workspacemember.find_unique(
        where={
            "userId_workspaceId":{
                "userId":current_user.id,
                "workspaceId":workspace_id
            }
        }
    )

    if not caller_membership or caller_membership.role != WorkspaceRole.SUPER_ADMIN:
        raise AppException(403, "Only workspace superadmins can update workspace settings.")
    
    # Build update data with only the fields that were provided
    update_data = {}
    if body.name is not None:
        if not body.name.strip():
            raise AppException(400, "Workspace name cannot be empty")
        update_data["name"] = body.name
    if body.description is not None:
        update_data["description"] = body.description
    if body.allowedEmailDomains is not None:
        if not body.allowedEmailDomains:
            raise AppException(400,"At least one allowed email domain is required.")
        update_data["allowedEmailDomains"] = body.allowedEmailDomains

    if not update_data:
        raise AppException(400,"No fields provided to update.")
    
    updated_workspace = await db.workspace.update(
        where={
            "id":workspace_id
        },
        data=update_data,
        include={
            "members":{"include":{"user":True}}
        }
    )

    return WorkspaceDetailOut(
        id=updated_workspace.id,
        name=updated_workspace.name,
        description=updated_workspace.description,
        allowedEmailDomains=updated_workspace.allowedEmailDomains,
        ownerId=updated_workspace.ownerId,
        memberCount=len(updated_workspace.members),
        members=[
            WorkspaceMemberOut(
                id=m.id,
                userId=m.userId,
                email=m.user.email,
                name=m.user.name if m.user else None,
                role=m.role
            )
            for m in updated_workspace.members
        ]
    ).model_dump()
