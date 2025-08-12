from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.database import Base

class GoogleAccount(Base):
    """
    Represents a Google account linked to a user's profile.
    Users can have multiple Google accounts - one primary and multiple secondary.
    """
    __tablename__ = "google_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Google account information
    google_id = Column(String, nullable=False, unique=True, index=True)  # Google's unique user ID
    email = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    
    # Account type and status
    is_primary = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # OAuth tokens (encrypted/secure storage in production)
    access_token = Column(Text, nullable=True)  # Current access token
    refresh_token = Column(Text, nullable=True)  # Refresh token for getting new access tokens
    id_token = Column(Text, nullable=True)  # ID token from Google
    token_expires_at = Column(DateTime(timezone=True), nullable=True)  # When access token expires
    
    # Additional OAuth metadata
    scope = Column(String, nullable=True)  # Granted scopes
    token_type = Column(String, default="Bearer", nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User")
    subscriptions = relationship("Subscription", back_populates="google_account")
    processing_logs = relationship("EmailProcessingLog", back_populates="google_account")

    def __repr__(self):
        return f"<GoogleAccount(id={self.id}, email={self.email}, is_primary={self.is_primary})>"

    @property
    def is_token_expired(self):
        """Check if the access token is expired"""
        if not self.token_expires_at:
            return True
        from datetime import datetime
        return datetime.utcnow() > self.token_expires_at
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "google_id": self.google_id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "is_primary": self.is_primary,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "scope": self.scope,
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "is_token_expired": self.is_token_expired
        }