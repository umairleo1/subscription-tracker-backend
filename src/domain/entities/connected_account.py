from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.database import Base

class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    email = Column(String, nullable=False)
    provider = Column(String, nullable=False)  # 'google', 'outlook', etc.
    is_primary = Column(Boolean, default=False)
    oauth_tokens = Column(Text)  # JSON string storing tokens
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="connected_accounts")
    subscriptions = relationship("Subscription", back_populates="connected_account")
    processing_logs = relationship("EmailProcessingLog", back_populates="connected_account")