from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from src.domain.entities.notification import NotificationType, NotificationChannel, NotificationStatus

class NotificationBase(BaseModel):
    type: NotificationType
    channel: NotificationChannel
    title: str
    message: str
    action_url: Optional[str] = None

class NotificationCreate(NotificationBase):
    user_id: int
    subscription_id: Optional[int] = None
    scheduled_for: datetime
    metadata: Optional[str] = None

class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    subscription_id: Optional[int] = None
    status: NotificationStatus
    scheduled_for: datetime
    sent_at: Optional[datetime] = None
    metadata: Optional[str] = None
    retry_count: int
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationUpdate(BaseModel):
    status: Optional[NotificationStatus] = None
    scheduled_for: Optional[datetime] = None
    retry_count: Optional[int] = None