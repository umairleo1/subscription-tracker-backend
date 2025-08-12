from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from decimal import Decimal

from src.domain.entities.subscription import Subscription, SubscriptionStatus, BillingCycle
from src.domain.entities.user import User
from src.presentation.responses.subscription import SubscriptionCreate, SubscriptionUpdate, SubscriptionSummary, SubscriptionInsight

class SubscriptionService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_subscription(self, user_id: int, subscription: SubscriptionCreate) -> Subscription:
        db_subscription = Subscription(
            user_id=user_id,
            **subscription.dict()
        )
        self.db.add(db_subscription)
        self.db.commit()
        self.db.refresh(db_subscription)
        return db_subscription
    
    def get_subscription(self, subscription_id: int, user_id: int) -> Optional[Subscription]:
        return self.db.query(Subscription).filter(
            and_(
                Subscription.id == subscription_id,
                Subscription.user_id == user_id
            )
        ).first()
    
    def get_user_subscriptions(self, user_id: int, status: Optional[SubscriptionStatus] = None) -> List[Subscription]:
        query = self.db.query(Subscription).filter(Subscription.user_id == user_id)
        if status:
            query = query.filter(Subscription.status == status)
        return query.order_by(Subscription.created_at.desc()).all()
    
    def update_subscription(self, subscription_id: int, user_id: int, updates: SubscriptionUpdate) -> Optional[Subscription]:
        subscription = self.get_subscription(subscription_id, user_id)
        if not subscription:
            return None
        
        update_data = updates.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(subscription, field, value)
        
        self.db.commit()
        self.db.refresh(subscription)
        return subscription
    
    def delete_subscription(self, subscription_id: int, user_id: int) -> bool:
        subscription = self.get_subscription(subscription_id, user_id)
        if not subscription:
            return False
        
        self.db.delete(subscription)
        self.db.commit()
        return True
    
    def cancel_subscription(self, subscription_id: int, user_id: int) -> Optional[Subscription]:
        subscription = self.get_subscription(subscription_id, user_id)
        if not subscription:
            return None
        
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_date = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(subscription)
        return subscription
    
    def get_subscription_summary(self, user_id: int) -> SubscriptionSummary:
        subscriptions = self.get_user_subscriptions(user_id)
        
        monthly_cost = Decimal('0.00')
        annual_cost = Decimal('0.00')
        status_counts = {status: 0 for status in SubscriptionStatus}
        category_counts = {}
        
        for sub in subscriptions:
            status_counts[sub.status] += 1
            
            if sub.status == SubscriptionStatus.ACTIVE:
                if sub.billing_cycle == BillingCycle.MONTHLY:
                    monthly_cost += sub.cost
                    annual_cost += sub.cost * 12
                elif sub.billing_cycle == BillingCycle.ANNUALLY:
                    annual_cost += sub.cost
                    monthly_cost += sub.cost / 12
                elif sub.billing_cycle == BillingCycle.QUARTERLY:
                    annual_cost += sub.cost * 4
                    monthly_cost += sub.cost / 3
        
        upcoming_renewals = self.get_upcoming_renewals(user_id, days=30)
        
        return SubscriptionSummary(
            total_monthly_cost=monthly_cost,
            total_annual_cost=annual_cost,
            active_subscriptions=status_counts[SubscriptionStatus.ACTIVE],
            trial_subscriptions=status_counts[SubscriptionStatus.TRIAL],
            cancelled_subscriptions=status_counts[SubscriptionStatus.CANCELLED],
            subscriptions_by_category=category_counts,
            upcoming_renewals=upcoming_renewals
        )
    
    def get_upcoming_renewals(self, user_id: int, days: int = 7) -> List[Subscription]:
        end_date = datetime.utcnow() + timedelta(days=days)
        return self.db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
                Subscription.next_billing_date <= end_date,
                Subscription.next_billing_date >= datetime.utcnow()
            )
        ).order_by(Subscription.next_billing_date.asc()).all()
    
    def get_insights(self, user_id: int) -> List[SubscriptionInsight]:
        insights = []
        subscriptions = self.get_user_subscriptions(user_id, SubscriptionStatus.ACTIVE)
        
        # Find unused subscriptions (no usage detected in 90 days)
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        for sub in subscriptions:
            if sub.usage_last_detected and sub.usage_last_detected < ninety_days_ago:
                insights.append(SubscriptionInsight(
                    type="unused",
                    subscription_id=sub.id,
                    title=f"{sub.service_name} appears unused",
                    description=f"No usage detected for 90+ days. Last used: {sub.usage_last_detected.strftime('%Y-%m-%d') if sub.usage_last_detected else 'Never'}",
                    potential_savings=sub.cost * 12 if sub.billing_cycle == BillingCycle.MONTHLY else sub.cost,
                    action_required=True,
                    priority="high"
                ))
        
        # Find trials ending soon
        seven_days_from_now = datetime.utcnow() + timedelta(days=7)
        trial_subs = self.db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.TRIAL,
                Subscription.trial_end_date <= seven_days_from_now,
                Subscription.trial_end_date >= datetime.utcnow()
            )
        ).all()
        
        for sub in trial_subs:
            days_left = (sub.trial_end_date - datetime.utcnow()).days
            insights.append(SubscriptionInsight(
                type="trial_ending",
                subscription_id=sub.id,
                title=f"{sub.service_name} trial ending soon",
                description=f"Trial ends in {days_left} days. Consider cancelling if not needed.",
                potential_savings=sub.cost * 12 if sub.billing_cycle == BillingCycle.MONTHLY else sub.cost,
                action_required=True,
                priority="high" if days_left <= 3 else "medium"
            ))
        
        # Find potential duplicates (same service name)
        service_groups = {}
        for sub in subscriptions:
            service_name = sub.service_name.lower()
            if service_name not in service_groups:
                service_groups[service_name] = []
            service_groups[service_name].append(sub)
        
        for service_name, subs in service_groups.items():
            if len(subs) > 1:
                total_cost = sum(sub.cost for sub in subs)
                insights.append(SubscriptionInsight(
                    type="duplicate",
                    subscription_id=subs[0].id,
                    title=f"Multiple {service_name} subscriptions detected",
                    description=f"Found {len(subs)} subscriptions for {service_name}. Total cost: ${total_cost}/month",
                    potential_savings=total_cost - min(sub.cost for sub in subs),
                    action_required=True,
                    priority="medium"
                ))
        
        return insights
    
    def mark_usage_detected(self, subscription_id: int, user_id: int) -> bool:
        subscription = self.get_subscription(subscription_id, user_id)
        if not subscription:
            return False
        
        subscription.usage_last_detected = datetime.utcnow()
        subscription.last_login_detected = datetime.utcnow()
        self.db.commit()
        return True