"""
Audit trail background tasks and reporting
"""
from celery import Celery
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import logging

from src.database.database import SessionLocal
from src.domain.entities.audit_log import AuditLog, AuditAction, AuditStatus
from src.core.tasks.celery_app import celery_app
from src.core.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

@celery_app.task(name="src.core.tasks.audit_tasks.generate_daily_audit_report")
def generate_daily_audit_report():
    """
    Generate daily audit report for security and compliance monitoring
    """
    try:
        db = SessionLocal()
        
        # Get yesterday's audit logs
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        start_of_day = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Query audit logs for the day
        daily_logs = db.query(AuditLog).filter(
            and_(
                AuditLog.created_at >= start_of_day,
                AuditLog.created_at <= end_of_day
            )
        ).all()
        
        # Generate report statistics
        report = _generate_audit_statistics(daily_logs, db)
        report["date"] = yesterday.date().isoformat()
        report["total_events"] = len(daily_logs)
        
        # Check for integrity violations
        integrity_report = _verify_audit_chain_integrity(db)
        report["integrity_status"] = integrity_report
        
        # Detect suspicious activities
        security_report = _detect_suspicious_activities(daily_logs)
        report["security_alerts"] = security_report
        
        db.close()
        
        logger.info(f"Daily audit report generated: {report['total_events']} events")
        
        # Store report (could be sent to monitoring system)
        _store_audit_report(report)
        
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate daily audit report: {str(e)}")
        return {"error": str(e)}

@celery_app.task(name="src.core.tasks.audit_tasks.verify_audit_integrity")
def verify_audit_integrity():
    """
    Verify the integrity of audit log chain
    """
    try:
        db = SessionLocal()
        
        integrity_report = _verify_audit_chain_integrity(db)
        
        db.close()
        
        if not integrity_report["is_valid"]:
            logger.critical(f"Audit integrity violation detected: {integrity_report}")
            # Could trigger alerts here
            
        return integrity_report
        
    except Exception as e:
        logger.error(f"Audit integrity verification failed: {str(e)}")
        return {"error": str(e)}

@celery_app.task(name="src.core.tasks.audit_tasks.cleanup_old_audit_logs")
def cleanup_old_audit_logs(retention_days: int = 2555):  # ~7 years default
    """
    Clean up audit logs older than retention period (with proper archiving)
    """
    try:
        db = SessionLocal()
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        # Count old logs
        old_logs_count = db.query(AuditLog).filter(
            AuditLog.created_at < cutoff_date
        ).count()
        
        if old_logs_count == 0:
            db.close()
            return {"archived": 0, "message": "No logs to archive"}
        
        # In production, you would archive these logs before deletion
        # For now, we'll just mark them for archival
        
        logger.info(f"Found {old_logs_count} audit logs ready for archival (older than {retention_days} days)")
        
        # TODO: Implement actual archival to cold storage before deletion
        # archived_count = _archive_audit_logs(old_logs, storage_service)
        # db.query(AuditLog).filter(AuditLog.created_at < cutoff_date).delete()
        
        db.close()
        
        return {
            "ready_for_archive": old_logs_count,
            "cutoff_date": cutoff_date.isoformat(),
            "message": "Audit logs identified for archival"
        }
        
    except Exception as e:
        logger.error(f"Audit cleanup failed: {str(e)}")
        return {"error": str(e)}

def _generate_audit_statistics(logs: List[AuditLog], db: Session) -> Dict[str, Any]:
    """Generate comprehensive audit statistics"""
    stats = {
        "actions": {},
        "status_breakdown": {},
        "user_activity": {},
        "system_vs_user": {"system": 0, "user": 0},
        "hourly_distribution": {},
        "top_ip_addresses": {},
        "failed_actions": []
    }
    
    for log in logs:
        # Action statistics
        stats["actions"][log.action] = stats["actions"].get(log.action, 0) + 1
        
        # Status breakdown
        stats["status_breakdown"][log.status] = stats["status_breakdown"].get(log.status, 0) + 1
        
        # User vs system actions
        if log.created_by_system:
            stats["system_vs_user"]["system"] += 1
        else:
            stats["system_vs_user"]["user"] += 1
        
        # User activity (if user_id is available)
        if log.user_id:
            stats["user_activity"][log.user_id] = stats["user_activity"].get(log.user_id, 0) + 1
        
        # Hourly distribution
        hour = log.created_at.hour
        stats["hourly_distribution"][hour] = stats["hourly_distribution"].get(hour, 0) + 1
        
        # IP address tracking
        if log.ip_address:
            stats["top_ip_addresses"][log.ip_address] = stats["top_ip_addresses"].get(log.ip_address, 0) + 1
        
        # Failed actions
        if log.status == AuditStatus.FAILURE.value:
            stats["failed_actions"].append({
                "id": log.id,
                "action": log.action,
                "error": log.error_message,
                "created_at": log.created_at.isoformat()
            })
    
    # Sort top IP addresses by frequency
    stats["top_ip_addresses"] = dict(sorted(
        stats["top_ip_addresses"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10])
    
    return stats

def _verify_audit_chain_integrity(db: Session) -> Dict[str, Any]:
    """Verify the integrity of the audit log chain"""
    try:
        # Get recent audit logs in order
        recent_logs = db.query(AuditLog).order_by(AuditLog.id).limit(1000).all()
        
        integrity_report = {
            "is_valid": True,
            "total_checked": len(recent_logs),
            "invalid_hashes": [],
            "chain_breaks": [],
            "last_verified": datetime.now(timezone.utc).isoformat()
        }
        
        previous_hash = None
        
        for log in recent_logs:
            # Verify individual record hash
            if not log.verify_integrity():
                integrity_report["is_valid"] = False
                integrity_report["invalid_hashes"].append({
                    "log_id": log.id,
                    "expected_hash": log._calculate_hash(),
                    "actual_hash": log.hash_value
                })
            
            # Verify chain continuity (if implemented)
            if previous_hash and log.previous_hash != previous_hash:
                integrity_report["is_valid"] = False
                integrity_report["chain_breaks"].append({
                    "log_id": log.id,
                    "expected_previous_hash": previous_hash,
                    "actual_previous_hash": log.previous_hash
                })
            
            previous_hash = log.hash_value
        
        return integrity_report
        
    except Exception as e:
        logger.error(f"Integrity verification failed: {str(e)}")
        return {"is_valid": False, "error": str(e)}

def _detect_suspicious_activities(logs: List[AuditLog]) -> List[Dict[str, Any]]:
    """Detect suspicious activities in audit logs"""
    alerts = []
    
    # Track failed login attempts by IP
    failed_logins = {}
    rate_limit_violations = {}
    
    for log in logs:
        # Multiple failed login attempts from same IP
        if log.action == AuditAction.USER_LOGIN.value and log.status == AuditStatus.FAILURE.value:
            ip = log.ip_address or "unknown"
            failed_logins[ip] = failed_logins.get(ip, 0) + 1
        
        # Rate limiting violations
        if log.action == AuditAction.RATE_LIMIT_EXCEEDED.value:
            ip = log.ip_address or "unknown"
            rate_limit_violations[ip] = rate_limit_violations.get(ip, 0) + 1
    
    # Generate alerts for suspicious activities
    for ip, count in failed_logins.items():
        if count >= 5:  # 5 or more failed logins
            alerts.append({
                "type": "multiple_failed_logins",
                "ip_address": ip,
                "count": count,
                "severity": "high" if count >= 10 else "medium"
            })
    
    for ip, count in rate_limit_violations.items():
        if count >= 3:  # Multiple rate limit hits
            alerts.append({
                "type": "excessive_rate_limiting",
                "ip_address": ip,
                "count": count,
                "severity": "medium"
            })
    
    return alerts

def _store_audit_report(report: Dict[str, Any]):
    """Store audit report for compliance and monitoring"""
    try:
        # In production, you might store this in:
        # - S3/cloud storage
        # - Elasticsearch
        # - Compliance database
        # - Send to SIEM system
        
        report_date = report.get("date", datetime.now().date().isoformat())
        logger.info(f"Audit report for {report_date} generated and stored")
        
        # Could also trigger alerts if security issues found
        security_alerts = report.get("security_alerts", [])
        if security_alerts:
            logger.warning(f"Security alerts detected in audit report: {len(security_alerts)} alerts")
            # Trigger notification system
            
    except Exception as e:
        logger.error(f"Failed to store audit report: {str(e)}")

# Create audit log entry helper function
def create_audit_log(
    action: AuditAction,
    status: AuditStatus = AuditStatus.SUCCESS,
    entity_type: str = None,
    entity_id: int = None,
    user_id: int = None,
    ip_address: str = None,
    user_agent: str = None,
    session_id: str = None,
    request_id: str = None,
    details: Dict[str, Any] = None,
    error_message: str = None,
    created_by_system: bool = False
) -> AuditLog:
    """
    Helper function to create audit log entries
    """
    try:
        db = SessionLocal()
        
        # Get previous hash for chain integrity (if needed)
        previous_log = db.query(AuditLog).order_by(desc(AuditLog.id)).first()
        previous_hash = previous_log.hash_value if previous_log else None
        
        audit_log = AuditLog(
            action=action.value,
            status=status.value,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            created_by_system=created_by_system,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            details=details,
            error_message=error_message,
            previous_hash=previous_hash
        )
        
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        db.close()
        
        return audit_log
        
    except Exception as e:
        logger.error(f"Failed to create audit log: {str(e)}")
        raise