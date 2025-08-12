from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.database import Base
import enum

class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class EmailProcessingLog(Base):
    __tablename__ = "email_processing_logs"

    id = Column(Integer, primary_key=True, index=True)
    linked_account_id = Column(UUID(as_uuid=True), ForeignKey("linked_accounts.id"), nullable=False)
    
    # Email metadata
    email_id = Column(String, nullable=False)  # Gmail message ID
    email_subject = Column(String)
    email_sender = Column(String)
    email_date = Column(DateTime(timezone=True))
    
    # Processing info
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    processing_method = Column(String)  # regex, nlp, gpt4
    subscriptions_found = Column(Integer, default=0)
    confidence_score = Column(String)  # JSON array of confidence scores
    
    # Results
    parsed_data = Column(Text)  # JSON of extracted data
    error_message = Column(Text)
    processing_time_ms = Column(Integer)
    
    # Flags
    is_subscription_related = Column(Boolean, default=False)
    requires_manual_review = Column(Boolean, default=False)
    user_reviewed = Column(Boolean, default=False)
    
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    linked_account = relationship("LinkedAccount", back_populates="processing_logs")