"""
User response models for API endpoints
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
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
    """Request payload for saving/updating user from NextAuth.js (used by GoogleAuthService)"""
    profile: GoogleOAuthProfile = Field(..., description="Google OAuth profile")
    tokens: GoogleOAuthTokens = Field(..., description="Google OAuth tokens")
    is_primary: Optional[bool] = Field(True, description="Whether this is the primary account")

class CreateUserRequest(BaseModel):
    """Request model for creating or upserting a user with Google OAuth"""
    profile: dict = Field(..., description="Google OAuth profile data")
    tokens: dict = Field(..., description="OAuth tokens from Google")
    is_primary: Optional[bool] = Field(True, description="Whether this should be the primary account (for new users)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "profile": {
                    "id": "1234567890",
                    "email": "user@example.com",
                    "given_name": "John",
                    "family_name": "Doe",
                    "name": "John Doe",
                    "picture": "https://lh3.googleusercontent.com/a/photo.jpg"
                },
                "tokens": {
                    "access_token": "ya29.access_token",
                    "refresh_token": "1//refresh_token",
                    "id_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                    "expires_at": 1700000000,
                    "token_type": "Bearer",
                    "scope": "openid email profile"
                }
            }
        }

class LinkAccountRequest(BaseModel):
    """Request model for linking a secondary Google account"""
    profile: dict = Field(..., description="Google OAuth profile data")
    tokens: dict = Field(..., description="OAuth tokens from Google")
    
    class Config:
        json_schema_extra = {
            "example": {
                "profile": {
                    "id": "0987654321",
                    "email": "secondary@example.com",
                    "given_name": "Jane",
                    "family_name": "Smith",
                    "name": "Jane Smith",
                    "picture": "https://lh3.googleusercontent.com/b/photo.jpg"
                },
                "tokens": {
                    "access_token": "ya29.secondary_access_token",
                    "refresh_token": "1//secondary_refresh_token",
                    "id_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                    "expires_at": 1700000000,
                    "token_type": "Bearer",
                    "scope": "openid email profile"
                }
            }
        }

class UpdateTokenRequest(BaseModel):
    """Request model for updating OAuth tokens after refresh"""
    access_token: str = Field(..., description="New access token")
    refresh_token: Optional[str] = Field(None, description="New refresh token (if provided)")
    expires_at: int = Field(..., description="Token expiry timestamp")
    token_type: str = Field(default="Bearer", description="Token type")

class LinkedAccountResponse(BaseModel):
    """Response model for linked account data"""
    id: str
    user_id: str
    google_id: str
    email: EmailStr
    name: Optional[str]
    picture: Optional[str]
    is_primary: bool
    is_active: bool
    token_status: str
    needs_reauth: bool
    is_token_expired: bool
    requires_refresh: bool
    connected_at: datetime
    last_token_refresh: Optional[datetime]
    token_refresh_count: int
    last_used_at: Optional[datetime]

class UserResponse(BaseModel):
    """Response model for user data with linked accounts"""
    id: str
    email: EmailStr
    name: Optional[str]
    picture: Optional[str]
    is_active: bool
    subscription_plan: str
    subscription_status: str
    subscription_expires_at: Optional[datetime]
    primary_account: Optional[LinkedAccountResponse]
    secondary_accounts: List[LinkedAccountResponse]
    total_accounts: int
    active_accounts: int
    expired_tokens: int
    created_at: datetime
    updated_at: Optional[datetime]
    last_login_at: Optional[datetime]

class CreateUserResponse(BaseModel):
    """Response model for user creation"""
    user: UserResponse
    is_new_user: bool
    account_created: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "user": {
                    "id": 1,
                    "email": "user@example.com",
                    "name": "John Doe",
                    "picture": "https://lh3.googleusercontent.com/a/photo.jpg",
                    "is_active": True,
                    "subscription_plan": "free",
                    "subscription_status": "active",
                    "subscription_expires_at": None,
                    "primary_account": {
                        "id": 1,
                        "user_id": 1,
                        "google_id": "1234567890",
                        "email": "user@example.com",
                        "is_primary": True,
                        "token_status": "active",
                        "needs_reauth": False
                    },
                    "secondary_accounts": [],
                    "total_accounts": 1,
                    "active_accounts": 1,
                    "expired_tokens": 0
                },
                "is_new_user": True,
                "account_created": True
            }
        }

class LinkAccountResponse(BaseModel):
    """Response model for linking account"""
    user: UserResponse
    linked_account: LinkedAccountResponse
    is_new_account: bool
    
class TokenUpdateResponse(BaseModel):
    """Response model for token updates"""
    account_id: str
    token_status: str
    expires_at: datetime
    last_token_refresh: datetime
    message: str

# Legacy models for backward compatibility
class UserBase(BaseModel):
    email: EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None