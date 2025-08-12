"""
Application configuration settings
Environment-based configuration management
"""
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Project Information
    PROJECT_NAME: str = "Subscription Tracker API"
    PROJECT_DESCRIPTION: str = "Professional backend API for managing subscription tracking across multiple Google accounts"
    PROJECT_VERSION: str = "1.0.0"
    
    # Server Configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://mac:Pakistan%403221@localhost:5432/subscription_tracker"
    DATABASE_ECHO: bool = False
    
    # Database connection pool settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    
    # Security Configuration
    SECRET_KEY: str = "dev-secret-key-change-in-production"  # Override with env var
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    
    # OAuth Token Encryption (MUST be set via environment variable)
    OAUTH_TOKEN_ENCRYPTION_KEY: Optional[str] = "Yrbm4XT5ILHJxlN2ON78rZyTOQOmFHAA_T3kPcS5z1g="
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # CORS Configuration
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001"
    ]
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_REQUESTS: bool = True
    LOG_RESPONSES: bool = True
    LOG_FILE: Optional[str] = None
    
    # Redis Configuration (for caching/sessions)
    REDIS_URL: Optional[str] = None
    
    # Email Configuration (for notifications)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    
    # Celery Configuration (for background tasks)
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    # Error Monitoring & Alerting
    SENTRY_DSN: Optional[str] = None
    ALERT_EMAIL_ENABLED: bool = False
    ALERT_WEBHOOK_URL: Optional[str] = None
    PAGERDUTY_INTEGRATION_KEY: Optional[str] = None
    
    # Monitoring Configuration  
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8001
    DATADOG_API_KEY: Optional[str] = None
    DATADOG_APP_KEY: Optional[str] = None
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        if v not in ["development", "staging", "production"]:
            raise ValueError("ENVIRONMENT must be one of: development, staging, production")
        return v
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        raise ValueError("ALLOWED_ORIGINS must be a comma-separated string or list")
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v, values):
        environment = values.get("ENVIRONMENT", "development")
        if environment == "production" and v == "dev-secret-key-change-in-production":
            raise ValueError("SECRET_KEY must be set to a secure value in production")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v
    
    @validator("OAUTH_TOKEN_ENCRYPTION_KEY")
    def validate_encryption_key(cls, v, values):
        environment = values.get("ENVIRONMENT", "development")
        if environment == "production" and not v:
            raise ValueError("OAUTH_TOKEN_ENCRYPTION_KEY is required in production")
        if v and len(v) < 32:
            raise ValueError("OAUTH_TOKEN_ENCRYPTION_KEY must be at least 32 characters long")
        return v
    
    class Config:
        env_file = ".env.local"
        env_file_encoding = "utf-8"
        case_sensitive = True


class DevelopmentSettings(Settings):
    """Development environment settings"""
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    DATABASE_ECHO: bool = False


class StagingSettings(Settings):
    """Staging environment settings"""
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"


class ProductionSettings(Settings):
    """Production environment settings"""
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_REQUESTS: bool = True  # Keep request logs for monitoring
    LOG_RESPONSES: bool = False
    DATABASE_ECHO: bool = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings based on environment
    """
    import os
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    settings_map = {
        "development": DevelopmentSettings,
        "staging": StagingSettings, 
        "production": ProductionSettings,
    }
    
    settings_class = settings_map.get(environment, DevelopmentSettings)
    return settings_class()