from db.client import db
from prisma.enums import Role
from utils.exceptions import AppException
from utils.email import send_invitation_email

async def invite_users(emails:list)->dict:
    return await _process_email_invites(emails)

async def _process_email_invites(emails:list)->dict:
    invited=[]
    skipped=[]

    for email in emails:
        existing_user = await db.user.find_unique(
            where={
                "email":email
            }
        )

        if existing_user:
            skipped.append({"email":email, "reason":"User already exists"})
            continue 
        
        await db.user.create(
            data={
                "email":email,
                "role":Role.MEMBER
            }
        )

        send_invitation_email(email)
        invited.append({"email":email})
    
    return {
        "invited": invited,
        "skipped": skipped
    }

async def bulk_invite_users(file_bytes:bytes, filename:str)->dict:
    #validate file extension
    if not filename.lower().endswith(".xlsx") and not filename.lower().endswith(".xls"):
        raise AppException(400, "Invalid file format. Only .xlsx and .xls files are allowed")

    #parse in memory
    import openpyxl 
    import io 

    try:
        workbook = openpyxl.load_workbook(io.BytesIO(file_bytes))
    except Exception as e:
        raise AppException(400, "Invalid Excel file")

    sheet = workbook.active 

    #find email column (case insensitive)
    headers = [cell.value for cell in sheet[1]]
    email_col_index = None 

    for i , header in enumerate(headers):
        if header and header.lower() == "email":
            email_col_index = i + 1
            break

    if email_col_index is None:
        raise AppException(400, "Email column not found in the Excel file")
    
    #extract emails from the rows
    raw_emails = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        value = row[email_col_index - 1]
        if value and str(value).strip():
            raw_emails.append(str(value).strip())
        
    if not raw_emails:
        raise AppException(400, "No valid emails found in the Excel file")
    
    #validate the email formats 
    import re 
    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    valid_emails=[]
    skipped=[]

    for email in raw_emails:
        if email_regex.match(email):
            valid_emails.append(email)
        else:
            skipped.append({"email":email, "reason":"Invalid email format"})
    
    # process valid emails through shared helper
    result = await _process_email_invites(valid_emails)

    #merge skipped lists
    all_skipped = skipped + result["skipped"]
    invited=result["invited"]

    return {
        "invited": invited,
        "skipped": all_skipped,
        "totalProcessed": len(raw_emails),
        "totalInvited": len(invited),
        "totalSkipped": len(all_skipped)
    }

async def resend_invite(emails:list)->dict:
    sent=[]
    skipped=[]

    for email in emails:
        user = await db.user.find_unique(
            where={
                "email":email
            }
        )

        if not user:
            skipped.append({"email":email,"reason":"User not found"})
            continue 

        send_invitation_email(email)
        sent.append({"email":email})

    return {
        "sent":sent,
        "skipped":skipped
    }

async def _check_delete_permission(caller,target_user):
    #block self deletion            
    if caller.id == target_user.id:
        raise AppException(400, "You cannot delete yourself")

    #Admin can only delete Members 
    if caller.role == Role.ADMIN and target_user.role != Role.MEMBER:
        raise AppException(403, "Admins can only delete members")
    
    # SUPER_ADMIN cannot delete another SUPER_ADMIN
    if caller.role == Role.SUPER_ADMIN and target_user.role == Role.SUPER_ADMIN:
        raise AppException(403, "Demote this user from SUPER_ADMIN before deleting them.")

async def delete_user(current_user, target_user_id:str) -> dict:
    target_user = await db.user.find_unique(where={"id":target_user_id})

    if not target_user:
        raise AppException(404, "User not found")

    await _check_delete_permission(current_user, target_user)

    await db.workspacemember.delete_many(
        where={
            "userId":target_user_id
        }
    )

    await db.user.delete(
        where={
            "id":target_user_id
        }
    )

    return {"deletedUserId": target_user_id}

async def bulk_delete_users(current_user, user_ids:list) -> dict:
    deleted=[]
    skipped=[]
    
    for user_id in user_ids:
        target_user = await db.user.find_unique(where={"id":user_id})

        if not target_user:
            skipped.append({"userId":user_id,"reason":"User not found"})
            continue 

        try:
            await _check_delete_permission(current_user, target_user)
        except AppException as e:
            skipped.append({"userId":user_id, "reason":e.message})
            continue

        await db.workspacemember.delete_many(where={"userId":user_id})

        await db.user.delete(where={"id":user_id})
        
        deleted.append({"userId":user_id})
    
    return {"deleted":deleted,"skipped":skipped}    