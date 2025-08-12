from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship
from src.database.database import Base

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    logo_url = Column(String)
    website_url = Column(String)
    category = Column(String)  # streaming, software, gaming, news, etc.
    
    # Pattern matching for email detection
    email_patterns = Column(Text)  # JSON array of regex patterns
    domain_patterns = Column(Text)  # JSON array of domain patterns
    sender_patterns = Column(Text)  # JSON array of sender email patterns
    
    # Service metadata
    typical_cost_range = Column(String)  # e.g., "$9.99-$19.99"
    cancellation_difficulty = Column(String)  # easy, medium, hard
    cancellation_url = Column(String)
    cancellation_instructions = Column(Text)
    
    # API integration info
    has_api = Column(Boolean, default=False)
    api_endpoint = Column(String)
    usage_tracking_available = Column(Boolean, default=False)
    
    subscriptions = relationship("Subscription", back_populates="service")