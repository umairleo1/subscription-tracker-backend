from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class GoogleOAuthProfile(BaseModel):
    """Google OAuth profile data from NextAuth.js"""
    id: str = Field(..., description="Google user ID")
    email: EmailStr = Field(..., description="Google email address")
    name: Optional[str] = Field(None, description="Full name from Google profile")
    image: Optional[str] = Field(None, description="Profile picture URL")

class GoogleOAuthTokens(BaseModel):
    """Google OAuth tokens from NextAuth.js"""
    access_token: str = Field(..., description="Google access token")
    refresh_token: Optional[str] = Field(None, description="Google refresh token")
    id_token: Optional[str] = Field(None, description="Google ID token")
    expires_at: Optional[int] = Field(None, description="Token expiration timestamp")
    token_type: Optional[str] = Field("Bearer", description="Token type")
    scope: Optional[str] = Field(None, description="Granted OAuth scopes")

class SaveUserRequest(BaseModel):
    """Request payload for saving/updating user from NextAuth.js"""
    profile: GoogleOAuthProfile = Field(..., description="Google OAuth profile")
    tokens: GoogleOAuthTokens = Field(..., description="Google OAuth tokens")
    is_primary: Optional[bool] = Field(True, description="Whether this is the primary account")
    
    class Config:
        schema_extra = {
            "example": {
                "profile": {
                    "id": "123456789012345678901",
                    "email": "user@gmail.com",
                    "name": "John Doe",
                    "image": "https://lh3.googleusercontent.com/a/example"
                },
                "tokens": {
                    "access_token": "ya29.a0ARrdaM...",
                    "refresh_token": "1//0GWIt...",
                    "id_token": "eyJhbGciOiJSUzI1NiIs...",
                    "expires_at": 1691234567,
                    "token_type": "Bearer",
                    "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly"
                },
                "is_primary": True
            }
        }

class GoogleAccountResponse(BaseModel):
    """Response model for Google account information"""
    id: str
    google_id: str
    email: EmailStr
    name: Optional[str]
    picture: Optional[str]
    is_primary: bool
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    last_login_at: Optional[str]
    scope: Optional[str]
    token_expires_at: Optional[str]
    is_token_expired: bool

class UserResponse(BaseModel):
    """Response model for user information with linked accounts"""
    id: str
    email: EmailStr
    name: Optional[str]
    picture: Optional[str]
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    last_login_at: Optional[str]
    primary_account: Optional[GoogleAccountResponse]
    secondary_accounts: List[GoogleAccountResponse]
    total_accounts: int

class SaveUserResponse(BaseModel):
    """Response after saving user data"""
    user: UserResponse
    account_created: bool = Field(..., description="Whether a new account was created")
    is_new_user: bool = Field(..., description="Whether this is a completely new user")
    
    class Config:
        schema_extra = {
            "example": {
                "user": {
                    "id": 1,
                    "email": "user@gmail.com",
                    "name": "John Doe",
                    "picture": "https://lh3.googleusercontent.com/a/example",
                    "is_active": True,
                    "created_at": "2025-08-08T13:48:49.000Z",
                    "primary_account": {
                        "id": 1,
                        "google_id": "123456789012345678901",
                        "email": "user@gmail.com",
                        "is_primary": True
                    },
                    "secondary_accounts": [],
                    "total_accounts": 1
                },
                "account_created": True,
                "is_new_user": True
            }
        }