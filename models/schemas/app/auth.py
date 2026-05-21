import email
from pydantic import BaseModel, ConfigDict , EmailStr
from typing import Optional
from datetime import datetime
class AppGoogleCallbackRequest(BaseModel):
    """IN - mobile app sends Google redirect (same contract as panel callback)"""
    code:str
    platform:str # client sends "app" (validate in _get_and_update_user)
    state:Optional[str] = None

class AppUserOut(BaseModel):
    """OUT - app-facing user ; no ban/panel admin fields."""
    id:str
    email:EmailStr
    name:Optional[str] = None
    picture:Optional[str] = None
    designation:Optional[str] = None
    dateOfJoining:Optional[datetime] = None
    birthdate:Optional[datetime] = None
    role:str # plain str, not Role enum - avoids serialization issues
    hasLoggedInApp: bool

    model_config = ConfigDict(from_attributes=True)

class AppGoogleAuthUrlResponse(BaseModel):
    auth_url:str

class AppAuthResponse(BaseModel):
    token:str
    user:AppUserOut

