from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Numeric, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.database import Base
import enum

class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    TRIAL = "trial"
    EXPIRED = "expired"
    PAUSED = "paused"

class BillingCycle(enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    WEEKLY = "weekly"
    ONE_TIME = "one_time"

class CancellationDifficulty(enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    VERY_HARD = "very_hard"

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    linked_account_id = Column(UUID(as_uuid=True), ForeignKey("linked_accounts.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    
    # Basic subscription info
    service_name = Column(String, nullable=False)
    cost = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="USD")
    billing_cycle = Column(Enum(BillingCycle), nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    
    # Billing dates
    next_billing_date = Column(DateTime(timezone=True))
    trial_end_date = Column(DateTime(timezone=True))
    subscription_start_date = Column(DateTime(timezone=True))
    cancelled_date = Column(DateTime(timezone=True))
    
    # Usage tracking
    usage_last_detected = Column(DateTime(timezone=True))
    usage_frequency = Column(String)  # daily, weekly, monthly, rarely, never
    last_login_detected = Column(DateTime(timezone=True))
    
    # AI/Processing metadata
    detected_from_email_id = Column(String)  # Email ID where this was detected
    confidence_score = Column(Numeric(3, 2))  # 0.00 to 1.00
    manual_override = Column(Boolean, default=False)
    parsing_method = Column(String)  # regex, nlp, gpt4, manual
    
    # Cancellation info
    cancellation_difficulty = Column(Enum(CancellationDifficulty))
    cancellation_url = Column(String)
    cancellation_phone = Column(String)
    cancellation_notes = Column(Text)
    
    # Notifications
    renewal_reminder_sent = Column(Boolean, default=False)
    price_change_alert_sent = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    linked_account = relationship("LinkedAccount", back_populates="subscriptions")
    service = relationship("Service", back_populates="subscriptions")
    notifications = relationship("Notification", back_populates="subscription")