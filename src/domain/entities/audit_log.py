"""
Immutable audit log system for tracking all system activities
Provides comprehensive audit trail with integrity protection
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, Index
from sqlalchemy.sql import func
from src.database.database import Base
from enum import Enum
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional

class AuditAction(str, Enum):
    """Audit action enumeration"""
    # User management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    
    # Account management
    ACCOUNT_LINKED = "account_linked"
    ACCOUNT_UNLINKED = "account_unlinked"
    ACCOUNT_REAUTH = "account_reauth"
    
    # Token management
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REFRESH_BATCH = "token_refresh_batch"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_EXPIRED = "token_expired"
    
    # Security events
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SECURITY_VIOLATION = "security_violation"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    BACKUP_CREATED = "backup_created"
    MIGRATION_EXECUTED = "migration_executed"

class AuditStatus(str, Enum):
    """Audit status enumeration"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    WARNING = "warning"

class AuditLog(Base):
    """
    Immutable audit log table for comprehensive system activity tracking
    """
    __tablename__ = "audit_logs"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Event identification
    action = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    
    # Entity information (what was affected)
    entity_type = Column(String(100), nullable=True, index=True)  # User, LinkedAccount, etc.
    entity_id = Column(Integer, nullable=True, index=True)
    
    # Actor information (who performed the action)
    user_id = Column(Integer, nullable=True, index=True)  # User who performed action
    created_by_system = Column(Boolean, default=False, nullable=False)  # System vs user action
    
    # Request context
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6 address
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(255), nullable=True, index=True)
    request_id = Column(String(255), nullable=True, index=True)
    
    # Event details
    details = Column(JSON, nullable=True)  # Structured event data
    error_message = Column(Text, nullable=True)  # Error details if status=failure
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Integrity protection
    hash_value = Column(String(64), nullable=False, index=True)  # SHA-256 hash of record
    previous_hash = Column(String(64), nullable=True)  # Hash of previous record for chain
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Calculate hash value for integrity
        self.hash_value = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate SHA-256 hash of the audit record for integrity protection"""
        # Create consistent hash input
        hash_data = {
            "action": self.action,
            "status": self.status,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "user_id": self.user_id,
            "created_by_system": self.created_by_system,
            "ip_address": self.ip_address,
            "details": self.details,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        
        # Convert to JSON string for consistent hashing
        hash_string = json.dumps(hash_data, sort_keys=True, default=str)
        
        # Calculate SHA-256 hash
        return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify the integrity of this audit record"""
        expected_hash = self._calculate_hash()
        return self.hash_value == expected_hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log to dictionary for API responses"""
        return {
            "id": self.id,
            "action": self.action,
            "status": self.status,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "user_id": self.user_id,
            "created_by_system": self.created_by_system,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "details": self.details,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "hash_value": self.hash_value,
            "integrity_verified": self.verify_integrity()
        }
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, status={self.status}, created_at={self.created_at})>"

# Database indexes for performance
Index('idx_audit_logs_action_status', AuditLog.action, AuditLog.status)
Index('idx_audit_logs_entity', AuditLog.entity_type, AuditLog.entity_id)
Index('idx_audit_logs_user_action', AuditLog.user_id, AuditLog.action)
Index('idx_audit_logs_created_at', AuditLog.created_at)
Index('idx_audit_logs_ip_address', AuditLog.ip_address)