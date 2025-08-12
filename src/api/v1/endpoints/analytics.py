from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict

from src.database.database import get_db
from src.utils.auth import get_current_active_user
from src.domain.entities.user import User
from src.domain.services.analytics_service import AnalyticsService

router = APIRouter(tags=["analytics"])

@router.get("/spending", response_model=Dict)
async def get_spending_analytics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = AnalyticsService(db)
    return service.get_spending_analytics(current_user.id)

@router.get("/trends", response_model=Dict)
async def get_spending_trends(
    months: int = Query(12, ge=3, le=24),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = AnalyticsService(db)
    return service.get_spending_trends(current_user.id, months)

@router.get("/usage", response_model=Dict)
async def get_usage_analytics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = AnalyticsService(db)
    return service.get_usage_analytics(current_user.id)

@router.get("/savings", response_model=Dict)
async def get_potential_savings(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = AnalyticsService(db)
    return service.get_cancellation_savings(current_user.id)

@router.get("/notifications", response_model=Dict)
async def get_notification_analytics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = AnalyticsService(db)
    return service.get_notification_analytics(current_user.id)

@router.get("/report", response_model=Dict)
async def get_comprehensive_report(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = AnalyticsService(db)
    return service.get_comprehensive_report(current_user.id)