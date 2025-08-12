"""
Comprehensive error monitoring and alerting system
Integrates with Sentry, Datadog, and custom alerting
"""
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
import logging
import asyncio
import httpx
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum

from src.core.config.settings import get_settings
from src.core.tasks.audit_tasks import create_audit_log
from src.domain.entities.audit_log import AuditAction, AuditStatus

logger = logging.getLogger(__name__)
settings = get_settings()

class AlertSeverity(str, Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertChannel(str, Enum):
    """Alert delivery channels"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    PAGERDUTY = "pagerduty"

class ErrorTracker:
    """
    Centralized error tracking and alerting system
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.error_counts = {}
        self.alert_thresholds = {
            "token_refresh_failures": {"count": 5, "window": 300, "severity": AlertSeverity.HIGH},
            "database_errors": {"count": 3, "window": 120, "severity": AlertSeverity.CRITICAL},
            "authentication_failures": {"count": 10, "window": 300, "severity": AlertSeverity.MEDIUM},
            "rate_limit_violations": {"count": 50, "window": 300, "severity": AlertSeverity.MEDIUM},
            "oauth_token_revocations": {"count": 5, "window": 600, "severity": AlertSeverity.HIGH},
            "system_errors": {"count": 5, "window": 300, "severity": AlertSeverity.HIGH}
        }
        
        self.setup_sentry()
    
    def setup_sentry(self):
        """Initialize Sentry SDK for error tracking"""
        if self.settings.SENTRY_DSN:
            sentry_sdk.init(
                dsn=self.settings.SENTRY_DSN,
                integrations=[
                    FastApiIntegration(auto_enabling_integrations=False),
                    SqlalchemyIntegration(),
                    RedisIntegration(),
                    CeleryIntegration()
                ],
                traces_sample_rate=0.1,  # 10% of transactions
                profiles_sample_rate=0.1,
                environment=self.settings.ENVIRONMENT,
                release=self.settings.PROJECT_VERSION,
                max_breadcrumbs=50,
                attach_stacktrace=True,
                send_default_pii=False,  # Don't send PII
                before_send=self._filter_sentry_events,
            )
            logger.info("Sentry initialized for error tracking")
    
    def _filter_sentry_events(self, event, hint):
        """Filter sensitive data from Sentry events"""
        # Remove sensitive data
        if 'request' in event:
            if 'data' in event['request']:
                request_data = event['request']['data']
                if isinstance(request_data, dict):
                    # Remove sensitive fields
                    sensitive_fields = ['access_token', 'refresh_token', 'id_token', 'password', 'secret']
                    for field in sensitive_fields:
                        if field in request_data:
                            request_data[field] = '[Redacted]'
            
            # Remove sensitive headers
            if 'headers' in event['request']:
                headers = event['request']['headers']
                sensitive_headers = ['authorization', 'x-api-key', 'cookie']
                for header in sensitive_headers:
                    if header.lower() in [h.lower() for h in headers.keys()]:
                        headers[header] = '[Redacted]'
        
        return event
    
    async def track_error(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        user_id: int = None,
        request_id: str = None,
        additional_data: Dict[str, Any] = None
    ):
        """Track an error with comprehensive context"""
        try:
            error_data = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "severity": severity.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "context": context or {},
                "user_id": user_id,
                "request_id": request_id,
                "additional_data": additional_data or {}
            }
            
            # Log error
            logger.error(f"Error tracked: {error_data['error_type']} - {error_data['error_message']}", 
                        exc_info=error, extra=error_data)
            
            # Send to Sentry
            with sentry_sdk.push_scope() as scope:
                if user_id:
                    scope.set_user({"id": user_id})
                if request_id:
                    scope.set_tag("request_id", request_id)
                if context:
                    for key, value in context.items():
                        scope.set_extra(key, value)
                
                scope.set_level(self._severity_to_sentry_level(severity))
                sentry_sdk.capture_exception(error)
            
            # Create audit log
            create_audit_log(
                action=AuditAction.SECURITY_VIOLATION if severity == AlertSeverity.CRITICAL else AuditAction.SYSTEM_STARTUP,
                status=AuditStatus.FAILURE,
                user_id=user_id,
                details=error_data,
                error_message=str(error),
                created_by_system=True
            )
            
            # Check if alert should be triggered
            await self._check_alert_thresholds(error_data)
            
        except Exception as e:
            # Don't let error tracking fail the application
            logger.error(f"Failed to track error: {str(e)}")
    
    def _severity_to_sentry_level(self, severity: AlertSeverity) -> str:
        """Convert AlertSeverity to Sentry level"""
        mapping = {
            AlertSeverity.LOW: "info",
            AlertSeverity.MEDIUM: "warning", 
            AlertSeverity.HIGH: "error",
            AlertSeverity.CRITICAL: "fatal"
        }
        return mapping.get(severity, "error")
    
    async def track_token_refresh_failure(self, account_email: str, error: str, user_id: int = None):
        """Track OAuth token refresh failures"""
        await self.track_error(
            Exception(f"Token refresh failed for {account_email}"),
            context={"account_email": account_email, "error_type": "token_refresh_failure"},
            severity=AlertSeverity.HIGH,
            user_id=user_id,
            additional_data={"error_details": error}
        )
    
    async def track_authentication_failure(self, email: str, ip_address: str, reason: str):
        """Track authentication failures"""
        await self.track_error(
            Exception(f"Authentication failed for {email}"),
            context={"email": email, "ip_address": ip_address, "error_type": "auth_failure"},
            severity=AlertSeverity.MEDIUM,
            additional_data={"failure_reason": reason}
        )
    
    async def track_database_error(self, query: str, error: Exception, user_id: int = None):
        """Track database errors"""
        await self.track_error(
            error,
            context={"query": query[:200] + "..." if len(query) > 200 else query, "error_type": "database_error"},
            severity=AlertSeverity.CRITICAL,
            user_id=user_id
        )
    
    async def track_oauth_revocation(self, account_email: str, user_id: int):
        """Track OAuth token revocations"""
        await self.track_error(
            Exception(f"OAuth token revoked for {account_email}"),
            context={"account_email": account_email, "error_type": "oauth_revocation"},
            severity=AlertSeverity.HIGH,
            user_id=user_id
        )
    
    async def _check_alert_thresholds(self, error_data: Dict[str, Any]):
        """Check if error counts exceed alert thresholds"""
        error_type = error_data.get("context", {}).get("error_type", "system_errors")
        threshold_config = self.alert_thresholds.get(error_type)
        
        if not threshold_config:
            return
        
        # Count recent errors of this type
        current_time = datetime.now(timezone.utc)
        window_start = current_time - timedelta(seconds=threshold_config["window"])
        
        # In production, you'd query your error storage (Redis, database, etc.)
        # For now, we'll use a simple in-memory counter
        error_key = f"{error_type}:{int(current_time.timestamp() // threshold_config['window'])}"
        
        if error_key not in self.error_counts:
            self.error_counts[error_key] = 0
        
        self.error_counts[error_key] += 1
        
        if self.error_counts[error_key] >= threshold_config["count"]:
            await self._trigger_alert(error_type, threshold_config, self.error_counts[error_key])
    
    async def _trigger_alert(self, error_type: str, threshold_config: Dict, error_count: int):
        """Trigger alert when threshold is exceeded"""
        alert_data = {
            "alert_type": error_type,
            "severity": threshold_config["severity"].value,
            "error_count": error_count,
            "threshold": threshold_config["count"],
            "window_seconds": threshold_config["window"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": self.settings.ENVIRONMENT
        }
        
        logger.critical(f"Alert triggered: {error_type} - {error_count} errors in {threshold_config['window']} seconds")
        
        # Send to configured alert channels
        await self._send_alert_notifications(alert_data)
        
        # Create audit log for alert
        create_audit_log(
            action=AuditAction.SECURITY_VIOLATION,
            status=AuditStatus.WARNING,
            details=alert_data,
            created_by_system=True
        )
    
    async def _send_alert_notifications(self, alert_data: Dict[str, Any]):
        """Send alert notifications to configured channels"""
        try:
            # Email alerts
            if self.settings.ALERT_EMAIL_ENABLED:
                await self._send_email_alert(alert_data)
            
            # Webhook alerts
            if self.settings.ALERT_WEBHOOK_URL:
                await self._send_webhook_alert(alert_data)
            
            # PagerDuty for critical alerts
            if alert_data["severity"] == AlertSeverity.CRITICAL.value and self.settings.PAGERDUTY_INTEGRATION_KEY:
                await self._send_pagerduty_alert(alert_data)
                
        except Exception as e:
            logger.error(f"Failed to send alert notifications: {str(e)}")
    
    async def _send_email_alert(self, alert_data: Dict[str, Any]):
        """Send email alert"""
        # Implementation would depend on your email service
        # Could use SendGrid, SES, etc.
        logger.info(f"Email alert would be sent: {alert_data}")
    
    async def _send_webhook_alert(self, alert_data: Dict[str, Any]):
        """Send webhook alert to custom endpoint"""
        if not self.settings.ALERT_WEBHOOK_URL:
            return
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    self.settings.ALERT_WEBHOOK_URL,
                    json=alert_data,
                    timeout=10,
                    headers={"Content-Type": "application/json"}
                )
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {str(e)}")
    
    async def _send_pagerduty_alert(self, alert_data: Dict[str, Any]):
        """Send critical alert to PagerDuty"""
        if not self.settings.PAGERDUTY_INTEGRATION_KEY:
            return
        
        pagerduty_payload = {
            "routing_key": self.settings.PAGERDUTY_INTEGRATION_KEY,
            "event_action": "trigger",
            "payload": {
                "summary": f"{alert_data['alert_type']} - {alert_data['error_count']} errors",
                "severity": alert_data['severity'],
                "source": f"subscription-tracker-{alert_data['environment']}",
                "custom_details": alert_data
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=pagerduty_payload,
                    timeout=10
                )
        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {str(e)}")

# Global error tracker instance
error_tracker = ErrorTracker()

# Convenience functions
async def track_error(error: Exception, context: Dict[str, Any] = None, **kwargs):
    """Convenience function to track errors"""
    await error_tracker.track_error(error, context, **kwargs)

async def track_token_refresh_failure(account_email: str, error: str, user_id: int = None):
    """Track token refresh failures"""
    await error_tracker.track_token_refresh_failure(account_email, error, user_id)

async def track_authentication_failure(email: str, ip_address: str, reason: str):
    """Track authentication failures"""
    await error_tracker.track_authentication_failure(email, ip_address, reason)

async def track_database_error(query: str, error: Exception, user_id: int = None):
    """Track database errors"""
    await error_tracker.track_database_error(query, error, user_id)

async def track_oauth_revocation(account_email: str, user_id: int):
    """Track OAuth revocations"""
    await error_tracker.track_oauth_revocation(account_email, user_id)