import uuid
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.database import Base
from enum import Enum

class SubscriptionStatus(str, Enum):
    """Subscription status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIAL = "trial"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class SubscriptionPlan(str, Enum):
    """Subscription plan enumeration"""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class User(Base):
    """
    Represents a primary user in the system. Users authenticate via Google OAuth
    and can have multiple Google accounts linked to their profile as secondary accounts.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Primary identifier (email from primary Google account)
    email = Column(String(255), unique=True, index=True, nullable=False)
    
    # User profile information from primary account
    name = Column(String(200), nullable=True)  # Full name
    picture = Column(Text, nullable=True)  # Profile picture URL
    
    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Subscription fields (future-proof)
    subscription_plan = Column(String(50), default=SubscriptionPlan.FREE.value, nullable=False)
    subscription_status = Column(String(50), default=SubscriptionStatus.ACTIVE.value, nullable=False)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    linked_accounts = relationship("LinkedAccount", back_populates="user", cascade="all, delete-orphan", lazy="select")
    subscriptions = relationship("Subscription", back_populates="user", lazy="select")
    notifications = relationship("Notification", back_populates="user", lazy="select")
    preferences = relationship("UserPreferences", back_populates="user", uselist=False, lazy="select")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, plan={self.subscription_plan})>"
    
    @property
    def primary_account(self):
        """Get the primary linked account"""
        for account in self.linked_accounts:
            if account.is_primary:
                return account
        return None
    
    @property
    def secondary_accounts(self):
        """Get all secondary linked accounts"""
        return [account for account in self.linked_accounts if not account.is_primary]
    
    @property
    def active_accounts_count(self):
        """Count of accounts that don't need re-authentication"""
        return sum(1 for account in self.linked_accounts if not account.needs_reauth)
    
    @property
    def expired_tokens_count(self):
        """Count of accounts with expired or invalid tokens"""
        return sum(1 for account in self.linked_accounts if account.needs_reauth)
    
    def to_dict(self, include_accounts=True):
        """Convert to dictionary for API responses"""
        data = {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "is_active": self.is_active,
            "subscription_plan": self.subscription_plan,
            "subscription_status": self.subscription_status,
            "subscription_expires_at": self.subscription_expires_at.isoformat() if self.subscription_expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
        
        if include_accounts:
            data.update({
                "primary_account": self.primary_account.to_dict() if self.primary_account else None,
                "secondary_accounts": [account.to_dict() for account in self.secondary_accounts],
                "total_accounts": len(self.linked_accounts),
                "active_accounts": self.active_accounts_count,
                "expired_tokens": self.expired_tokens_count
            })
        
        return data