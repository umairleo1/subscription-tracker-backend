from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from src.database.database import get_db
from src.utils.auth import get_current_active_user
from src.domain.entities.user import User
from src.domain.entities.subscription import SubscriptionStatus
from src.presentation.responses.subscription import (
    SubscriptionCreate, 
    SubscriptionUpdate, 
    SubscriptionResponse, 
    SubscriptionSummary,
    SubscriptionInsight
)
from src.domain.services.subscription_service import SubscriptionService

router = APIRouter(tags=["subscriptions"])

@router.post("/", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    subscription: SubscriptionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    return service.create_subscription(current_user.id, subscription)

@router.get("/", response_model=List[SubscriptionResponse])
async def get_subscriptions(
    status_filter: Optional[SubscriptionStatus] = Query(None, alias="status"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    return service.get_user_subscriptions(current_user.id, status_filter)

@router.get("/summary", response_model=SubscriptionSummary)
async def get_subscription_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    return service.get_subscription_summary(current_user.id)

@router.get("/insights", response_model=List[SubscriptionInsight])
async def get_insights(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    return service.get_insights(current_user.id)

@router.get("/upcoming-renewals", response_model=List[SubscriptionResponse])
async def get_upcoming_renewals(
    days: int = Query(7, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    return service.get_upcoming_renewals(current_user.id, days)

@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    subscription = service.get_subscription(subscription_id, current_user.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    return subscription

@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    updates: SubscriptionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    subscription = service.update_subscription(subscription_id, current_user.id, updates)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    return subscription

@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    subscription = service.cancel_subscription(subscription_id, current_user.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    return subscription

@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    if not service.delete_subscription(subscription_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

@router.post("/{subscription_id}/usage", status_code=status.HTTP_204_NO_CONTENT)
async def mark_usage_detected(
    subscription_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    service = SubscriptionService(db)
    if not service.mark_usage_detected(subscription_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )