"""
LinkedAccount entity for managing OAuth-connected Google accounts
Supports encrypted token storage and token lifecycle management
"""
import uuid
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.database import Base
from enum import Enum

class TokenStatus(str, Enum):
    """OAuth token status enumeration"""
    ACTIVE = "active"
    NEEDS_REAUTH = "needs_reauth" 
    EXPIRED = "expired"
    REVOKED = "revoked"

class LinkedAccount(Base):
    """
    Represents a linked Google account (primary or secondary) for a user.
    Stores encrypted OAuth tokens and manages token lifecycle.
    """
    __tablename__ = "linked_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Google account information
    google_id = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=False, index=True)
    name = Column(String(200), nullable=True)  # Full name
    picture = Column(Text, nullable=True)  # Profile picture URL
    
    # Account type and status
    is_primary = Column(Boolean, default=False, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # OAuth token fields (encrypted at rest)
    access_token_encrypted = Column(Text, nullable=True)  # Encrypted access token
    refresh_token_encrypted = Column(Text, nullable=True)  # Encrypted refresh token
    id_token_encrypted = Column(Text, nullable=True)  # Encrypted ID token
    
    # Token metadata
    token_type = Column(String(50), default="Bearer", nullable=False)
    scope = Column(Text, nullable=True)  # OAuth scopes granted
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Token expiry
    token_status = Column(String(50), default=TokenStatus.ACTIVE.value, nullable=False, index=True)
    needs_reauth = Column(Boolean, default=False, nullable=False, index=True)
    
    # Token lifecycle tracking
    last_token_refresh = Column(DateTime(timezone=True), nullable=True)
    token_refresh_count = Column(Integer, default=0, nullable=False)
    last_auth_error = Column(Text, nullable=True)  # Last authentication error message
    
    # Timestamps
    connected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # When account was linked
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)  # Last time tokens were used
    
    # Relationships
    user = relationship("User", back_populates="linked_accounts")
    subscriptions = relationship("Subscription", back_populates="linked_account")
    processing_logs = relationship("EmailProcessingLog", back_populates="linked_account")
    
    def __repr__(self):
        account_type = "Primary" if self.is_primary else "Secondary"
        return f"<LinkedAccount(id={self.id}, email={self.email}, type={account_type}, status={self.token_status})>"
    
    @property
    def is_token_expired(self):
        """Check if the access token is expired"""
        if not self.expires_at:
            return False
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        expires_at = self.expires_at
        # Ensure both datetimes are timezone-aware for comparison
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return now_utc >= expires_at
    
    @property 
    def requires_refresh(self):
        """Check if token needs refresh (expired but refresh token available)"""
        return self.is_token_expired and self.refresh_token_encrypted and not self.needs_reauth
    
    def mark_needs_reauth(self, error_message: str = None):
        """Mark account as needing re-authentication"""
        self.needs_reauth = True
        self.token_status = TokenStatus.NEEDS_REAUTH.value
        if error_message:
            self.last_auth_error = error_message
        self.updated_at = func.now()
    
    def mark_reauth_complete(self):
        """Mark account as successfully re-authenticated"""
        self.needs_reauth = False
        self.token_status = TokenStatus.ACTIVE.value
        self.last_auth_error = None
        self.updated_at = func.now()
    
    def update_token_info(self, expires_at: DateTime = None):
        """Update token metadata after successful refresh"""
        if expires_at:
            self.expires_at = expires_at
        self.last_token_refresh = func.now()
        self.token_refresh_count += 1
        self.token_status = TokenStatus.ACTIVE.value
        self.needs_reauth = False
        self.last_auth_error = None
        self.updated_at = func.now()
    
    def to_dict(self, include_tokens=False):
        """Convert to dictionary for API responses"""
        data = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "google_id": self.google_id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "is_primary": self.is_primary,
            "is_active": self.is_active,
            "token_type": self.token_type,
            "scope": self.scope,
            "token_expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_login_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "token_status": self.token_status,
            "needs_reauth": self.needs_reauth,
            "is_token_expired": self.is_token_expired,
            "requires_refresh": self.requires_refresh,
            "last_token_refresh": self.last_token_refresh.isoformat() if self.last_token_refresh else None,
            "token_refresh_count": self.token_refresh_count,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
        
        # Only include encrypted tokens if explicitly requested (for internal use)
        if include_tokens:
            data.update({
                "access_token_encrypted": self.access_token_encrypted,
                "refresh_token_encrypted": self.refresh_token_encrypted, 
                "id_token_encrypted": self.id_token_encrypted,
                "last_auth_error": self.last_auth_error
            })
        
        return data