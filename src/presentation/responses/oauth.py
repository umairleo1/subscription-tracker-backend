from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime

class GoogleOAuthRequest(BaseModel):
    authorization_code: str
    is_primary: bool = False

class GoogleOAuthResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int
    token_type: str = "Bearer"
    scope: str
    email: EmailStr

class ConnectedAccountBase(BaseModel):
    email: EmailStr
    provider: str
    is_primary: bool = False

class ConnectedAccountCreate(ConnectedAccountBase):
    oauth_tokens: str  # JSON string

class ConnectedAccountResponse(ConnectedAccountBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ConnectedAccountUpdate(BaseModel):
    is_primary: Optional[bool] = None
    oauth_tokens: Optional[str] = None

class OAuthTokenRefresh(BaseModel):
    refresh_token: str

class AccountLinkRequest(BaseModel):
    authorization_code: str
    email: Optional[EmailStr] = None