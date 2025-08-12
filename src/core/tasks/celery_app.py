"""
Celery application configuration for background tasks
"""
from celery import Celery
from src.core.config.settings import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Create Celery app instance
celery_app = Celery(
    "subscription_tracker",
    broker=settings.CELERY_BROKER_URL or "redis://localhost:6379/0",
    backend=settings.CELERY_RESULT_BACKEND or "redis://localhost:6379/0",
    include=[
        "src.core.tasks.token_refresh",
        "src.core.tasks.audit_tasks",
        "src.core.tasks.monitoring"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task execution
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task routing
    task_routes={
        "src.core.tasks.token_refresh.*": {"queue": "token_refresh"},
        "src.core.tasks.audit_tasks.*": {"queue": "audit"},
        "src.core.tasks.monitoring.*": {"queue": "monitoring"},
    },
    
    # Task retry configuration
    task_default_retry_delay=60,  # 60 seconds
    task_max_retries=3,
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,  # 10 minutes
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "refresh-expiring-tokens": {
            "task": "src.core.tasks.token_refresh.refresh_expiring_tokens",
            "schedule": 300.0,  # Every 5 minutes
        },
        "detect-revoked-tokens": {
            "task": "src.core.tasks.token_refresh.detect_revoked_tokens", 
            "schedule": 900.0,  # Every 15 minutes
        },
        "cleanup-expired-tokens": {
            "task": "src.core.tasks.token_refresh.cleanup_expired_tokens",
            "schedule": 3600.0,  # Every hour
        },
        "generate-audit-reports": {
            "task": "src.core.tasks.audit_tasks.generate_daily_audit_report",
            "schedule": 86400.0,  # Daily
        },
    },
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
)

# Configure logging for Celery
celery_app.conf.worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
celery_app.conf.worker_task_log_format = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

logger.info("Celery app configured successfully")