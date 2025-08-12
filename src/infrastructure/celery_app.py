"""
Celery application configuration for background task processing
Professional setup with Redis broker and PostgreSQL result backend
"""
from celery import Celery
from src.core.config.settings import get_settings

settings = get_settings()

# Initialize Celery app
celery_app = Celery(
    "subscription_tracker",
    broker=settings.CELERY_BROKER_URL or "redis://localhost:6379/1",
    backend=settings.CELERY_RESULT_BACKEND or "redis://localhost:6379/2",
    include=["src.infrastructure.tasks.token_refresh"]
)

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        'src.infrastructure.tasks.token_refresh.refresh_oauth_token': {'queue': 'token_refresh'},
        'src.infrastructure.tasks.token_refresh.refresh_all_expired_tokens': {'queue': 'token_refresh'},
    },
    
    # Task execution settings
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    result_expires=3600,  # Results expire after 1 hour
    task_track_started=True,
    task_ignore_result=False,
    
    # Worker settings for better concurrency control
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    task_acks_late=True,          # Acknowledge after task completion
    worker_disable_rate_limits=False,
    task_reject_on_worker_lost=True,  # Reject tasks if worker dies
    
    # Retry settings
    task_default_retry_delay=60,  # 60 seconds
    task_max_retries=3,
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'refresh-expired-tokens': {
            'task': 'src.infrastructure.tasks.token_refresh.refresh_all_expired_tokens',
            'schedule': 300.0,  # Run every 5 minutes
            'options': {'queue': 'token_refresh'}
        },
        'cleanup-old-tokens': {
            'task': 'src.infrastructure.tasks.token_refresh.cleanup_failed_refresh_attempts',
            'schedule': 3600.0,  # Run every hour
            'options': {'queue': 'token_refresh'}
        },
    },
)

# Import tasks to register them
from src.infrastructure.tasks import token_refresh

if __name__ == '__main__':
    celery_app.start()