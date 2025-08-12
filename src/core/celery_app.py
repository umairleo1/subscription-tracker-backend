from celery import Celery
from src.core.config import settings

celery_app = Celery(
    "subscription_tracker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.email_processing", "app.tasks.notifications"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_routes={
        "app.tasks.email_processing.*": {"queue": "email_processing"},
        "app.tasks.notifications.*": {"queue": "notifications"},
    },
    beat_schedule={
        "process-emails": {
            "task": "app.tasks.email_processing.process_all_accounts",
            "schedule": 300.0,  # Every 5 minutes
        },
        "send-notifications": {
            "task": "app.tasks.notifications.send_scheduled_notifications",
            "schedule": 60.0,  # Every minute
        },
        "generate-renewal-reminders": {
            "task": "app.tasks.notifications.schedule_renewal_reminders",
            "schedule": 3600.0,  # Every hour
        },
    },
)