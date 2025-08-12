from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from src.domain.entities.subscription import SubscriptionStatus, BillingCycle, CancellationDifficulty

class SubscriptionBase(BaseModel):
    service_name: str
    cost: Decimal
    currency: str = "USD"
    billing_cycle: BillingCycle
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE

class SubscriptionCreate(SubscriptionBase):
    connected_account_id: int
    next_billing_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    subscription_start_date: Optional[datetime] = None
    manual_override: bool = True

class SubscriptionUpdate(BaseModel):
    service_name: Optional[str] = None
    cost: Optional[Decimal] = None
    currency: Optional[str] = None
    billing_cycle: Optional[BillingCycle] = None
    status: Optional[SubscriptionStatus] = None
    next_billing_date: Optional[datetime] = None
    cancellation_url: Optional[str] = None
    cancellation_difficulty: Optional[CancellationDifficulty] = None
    cancellation_notes: Optional[str] = None

class SubscriptionResponse(SubscriptionBase):
    id: int
    user_id: int
    connected_account_id: int
    service_id: Optional[int] = None
    next_billing_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    subscription_start_date: Optional[datetime] = None
    cancelled_date: Optional[datetime] = None
    usage_last_detected: Optional[datetime] = None
    usage_frequency: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    manual_override: bool
    parsing_method: Optional[str] = None
    cancellation_difficulty: Optional[CancellationDifficulty] = None
    cancellation_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SubscriptionSummary(BaseModel):
    total_monthly_cost: Decimal
    total_annual_cost: Decimal
    active_subscriptions: int
    trial_subscriptions: int
    cancelled_subscriptions: int
    subscriptions_by_category: dict
    upcoming_renewals: List[SubscriptionResponse]

class SubscriptionInsight(BaseModel):
    type: str  # unused, duplicate, price_increase, trial_ending
    subscription_id: int
    title: str
    description: str
    potential_savings: Optional[Decimal] = None
    action_required: bool
    priority: str  # high, medium, low