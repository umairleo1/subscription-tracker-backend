from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.database import Base
import enum

class NotificationType(enum.Enum):
    RENEWAL_REMINDER = "renewal_reminder"
    TRIAL_ENDING = "trial_ending"
    PRICE_CHANGE = "price_change"
    USAGE_WARNING = "usage_warning"  # Haven't used in X months
    DUPLICATE_DETECTED = "duplicate_detected"
    CANCELLATION_REMINDER = "cancellation_reminder"

class NotificationChannel(enum.Enum):
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    IN_APP = "in_app"

class NotificationStatus(enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DISMISSED = "dismissed"

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    
    type = Column(Enum(NotificationType), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    action_url = Column(String)  # Link to take action
    
    # Scheduling
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True))
    
    # Metadata
    notification_metadata = Column(Text)  # JSON for additional data
    retry_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    subscription = relationship("Subscription", back_populates="notifications")