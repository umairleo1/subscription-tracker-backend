from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.database.database import Base

class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    
    # Notification preferences
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    sms_notifications = Column(Boolean, default=False)
    
    # Reminder timing (days before)
    trial_reminder_days = Column(Integer, default=3)
    renewal_reminder_days = Column(Integer, default=7)
    annual_reminder_days = Column(Integer, default=30)
    
    # Usage tracking
    usage_tracking_enabled = Column(Boolean, default=True)
    inactive_threshold_days = Column(Integer, default=90)  # Days without usage to trigger alert
    
    # AI processing preferences
    auto_detect_subscriptions = Column(Boolean, default=True)
    require_confirmation_threshold = Column(String, default="0.8")  # Confidence threshold
    
    # Privacy settings
    data_retention_months = Column(Integer, default=24)
    email_content_retention_days = Column(Integer, default=90)
    
    # UI preferences
    default_currency = Column(String, default="USD")
    date_format = Column(String, default="%Y-%m-%d")
    timezone = Column(String, default="UTC")
    
    # Notification channels per type (JSON)
    notification_channels = Column(Text)  # JSON mapping of notification types to channels
    
    user = relationship("User", back_populates="preferences")