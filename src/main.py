"""
Main application entry point for Subscription Tracker API
Professional FastAPI application with comprehensive structure
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_v1_router
from src.core.config.settings import get_settings
from src.core.logging.setup import setup_logging
from src.core.security.middleware import SecurityMiddleware
from src.presentation.middleware.logging import RequestLoggingMiddleware
from src.presentation.middleware.rate_limit import RateLimitMiddleware
from src.presentation.responses.exception_handlers import setup_exception_handlers

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Get application settings
settings = get_settings()

def create_application() -> FastAPI:
    """
    Application factory pattern for creating FastAPI instance
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.PROJECT_VERSION,
        docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
    )
    
    # Setup exception handlers
    setup_exception_handlers(app)
    
    # Add middleware (order matters - last added is executed first)
    # CORS middleware MUST be added last to execute first
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(
        RequestLoggingMiddleware, 
        log_requests=settings.LOG_REQUESTS, 
        log_responses=settings.LOG_RESPONSES
    )
    app.add_middleware(
        RateLimitMiddleware, 
        requests_per_minute=settings.RATE_LIMIT_PER_MINUTE
    )
    
    # CORS middleware - added last to execute first
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID", 
            "X-Process-Time", 
            "X-RateLimit-Limit", 
            "X-RateLimit-Remaining"
        ],
    )
    
    # Include API routers
    app.include_router(api_v1_router, prefix="/api/v1")
    
    return app

# Create application instance
app = create_application()

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info(f"Shutting down {settings.PROJECT_NAME}")

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
    )