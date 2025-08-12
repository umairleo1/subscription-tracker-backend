"""
API v1 router - Main router for version 1 of the API
"""
from fastapi import APIRouter
from src.api.v1.endpoints import auth, users, subscriptions, analytics, monitoring, tokens

api_v1_router = APIRouter()

# Include all endpoint routers
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
api_v1_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions"])
api_v1_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_v1_router.include_router(monitoring.router, prefix="/monitoring", tags=["Monitoring"])
api_v1_router.include_router(tokens.router, prefix="/tokens", tags=["Token Management"])

@api_v1_router.get("/health")
async def health_check():
    """API health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}