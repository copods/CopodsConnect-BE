from pydantic import BaseModel, EmailStr
from typing import List

#IN
class InviteUsersRequest(BaseModel):
    emails: List[EmailStr]

class BulkInviteRequest(BaseModel):
    pass  # no body fields — input is a file, handled by FastAPI UploadFile directly in route   

class ResendInviteRequest(BaseModel):
    emails: List[EmailStr]

class DeleteUserRequest(BaseModel):
    userIds: List[str]
