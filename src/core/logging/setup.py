"""
Logging configuration and setup
Professional logging with structured output
"""
import logging
import logging.config
import sys
from pathlib import Path
from typing import Dict, Any

from src.core.config.settings import get_settings

def get_logging_config() -> Dict[str, Any]:
    """
    Get logging configuration dictionary
    """
    settings = get_settings()
    
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "{asctime} | {name} | {levelname} | {message}",
                "style": "{",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "{levelname} | {name} | {message}",
                "style": "{"
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "detailed",
                "stream": sys.stdout
            },
        },
        "loggers": {
            "src": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False
            }
        },
        "root": {
            "level": settings.LOG_LEVEL,
            "handlers": ["console"]
        }
    }
    
    # Add file handler if log file is specified
    if settings.LOG_FILE:
        log_dir = Path(settings.LOG_FILE).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": settings.LOG_LEVEL,
            "formatter": "detailed",
            "filename": settings.LOG_FILE,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5
        }
        
        # Add file handler to all loggers
        for logger_config in config["loggers"].values():
            logger_config["handlers"].append("file")
        config["root"]["handlers"].append("file")
    
    return config

def setup_logging():
    """
    Setup application logging configuration
    """
    config = get_logging_config()
    logging.config.dictConfig(config)
    
    # Log startup info
    logger = logging.getLogger(__name__)
    settings = get_settings()
    logger.info(f"Logging initialized - Level: {settings.LOG_LEVEL}")
    
    if settings.LOG_FILE:
        logger.info(f"Log file: {settings.LOG_FILE}")