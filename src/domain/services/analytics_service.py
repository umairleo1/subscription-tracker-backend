from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_, or_
import sqlalchemy
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from src.domain.entities.subscription import Subscription, SubscriptionStatus, BillingCycle
from src.domain.entities.user import User
from src.domain.entities.notification import Notification, NotificationType

class AnalyticsService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_spending_analytics(self, user_id: int) -> Dict:
        subscriptions = self.db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).all()
        
        monthly_total = Decimal('0.00')
        annual_total = Decimal('0.00')
        category_breakdown = {}
        service_breakdown = []
        
        for sub in subscriptions:
            # Normalize to monthly cost
            if sub.billing_cycle == BillingCycle.MONTHLY:
                monthly_cost = sub.cost
                annual_cost = sub.cost * 12
            elif sub.billing_cycle == BillingCycle.ANNUALLY:
                monthly_cost = sub.cost / 12
                annual_cost = sub.cost
            elif sub.billing_cycle == BillingCycle.QUARTERLY:
                monthly_cost = sub.cost / 3
                annual_cost = sub.cost * 4
            else:
                monthly_cost = sub.cost
                annual_cost = sub.cost * 12
            
            monthly_total += monthly_cost
            annual_total += annual_cost
            
            # Service breakdown
            service_breakdown.append({
                'service_name': sub.service_name,
                'monthly_cost': float(monthly_cost),
                'annual_cost': float(annual_cost),
                'billing_cycle': sub.billing_cycle.value,
                'category': getattr(sub.service, 'category', 'Other') if sub.service else 'Other'
            })
            
            # Category breakdown
            category = getattr(sub.service, 'category', 'Other') if sub.service else 'Other'
            if category not in category_breakdown:
                category_breakdown[category] = {'monthly': 0, 'annual': 0, 'count': 0}
            
            category_breakdown[category]['monthly'] += float(monthly_cost)
            category_breakdown[category]['annual'] += float(annual_cost)
            category_breakdown[category]['count'] += 1
        
        return {
            'total_monthly': float(monthly_total),
            'total_annual': float(annual_total),
            'service_breakdown': service_breakdown,
            'category_breakdown': category_breakdown,
            'subscription_count': len(subscriptions)
        }
    
    def get_spending_trends(self, user_id: int, months: int = 12) -> Dict:
        # Get historical data for spending trends
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)
        
        # Monthly spending over time
        monthly_data = []
        current_date = start_date
        
        while current_date <= end_date:
            month_start = current_date.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            # Get subscriptions active during this month
            active_subs = self.db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.created_at <= month_end,
                # Either still active or cancelled after this month
                or_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.cancelled_date >= month_start
                )
            ).all()
            
            monthly_cost = Decimal('0.00')
            for sub in active_subs:
                if sub.billing_cycle == BillingCycle.MONTHLY:
                    monthly_cost += sub.cost
                elif sub.billing_cycle == BillingCycle.ANNUALLY:
                    monthly_cost += sub.cost / 12
                elif sub.billing_cycle == BillingCycle.QUARTERLY:
                    monthly_cost += sub.cost / 3
                else:
                    monthly_cost += sub.cost
            
            monthly_data.append({
                'month': month_start.strftime('%Y-%m'),
                'spending': float(monthly_cost),
                'subscription_count': len(active_subs)
            })
            
            current_date = (current_date + timedelta(days=32)).replace(day=1)
        
        return {
            'monthly_trends': monthly_data,
            'trend_analysis': self._analyze_trends(monthly_data)
        }
    
    def _analyze_trends(self, monthly_data: List[Dict]) -> Dict:
        if len(monthly_data) < 2:
            return {'trend': 'insufficient_data'}
        
        recent_spending = [item['spending'] for item in monthly_data[-3:]]
        older_spending = [item['spending'] for item in monthly_data[-6:-3]]
        
        if not older_spending:
            return {'trend': 'insufficient_data'}
        
        recent_avg = sum(recent_spending) / len(recent_spending)
        older_avg = sum(older_spending) / len(older_spending)
        
        if recent_avg > older_avg * 1.1:
            trend = 'increasing'
        elif recent_avg < older_avg * 0.9:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'recent_average': recent_avg,
            'previous_average': older_avg,
            'change_percentage': ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        }
    
    def get_usage_analytics(self, user_id: int) -> Dict:
        subscriptions = self.db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).all()
        
        usage_stats = {
            'high_usage': 0,
            'medium_usage': 0,
            'low_usage': 0,
            'no_usage': 0,
            'usage_breakdown': []
        }
        
        now = datetime.utcnow()
        
        for sub in subscriptions:
            days_since_usage = None
            usage_level = 'unknown'
            
            if sub.usage_last_detected:
                days_since_usage = (now - sub.usage_last_detected).days
                
                if days_since_usage <= 7:
                    usage_level = 'high'
                    usage_stats['high_usage'] += 1
                elif days_since_usage <= 30:
                    usage_level = 'medium'
                    usage_stats['medium_usage'] += 1
                elif days_since_usage <= 90:
                    usage_level = 'low'
                    usage_stats['low_usage'] += 1
                else:
                    usage_level = 'none'
                    usage_stats['no_usage'] += 1
            else:
                usage_level = 'none'
                usage_stats['no_usage'] += 1
            
            usage_stats['usage_breakdown'].append({
                'service_name': sub.service_name,
                'usage_level': usage_level,
                'days_since_usage': days_since_usage,
                'last_usage': sub.usage_last_detected.isoformat() if sub.usage_last_detected else None,
                'monthly_cost': float(sub.cost) if sub.billing_cycle == BillingCycle.MONTHLY else float(sub.cost / 12)
            })
        
        return usage_stats
    
    def get_cancellation_savings(self, user_id: int) -> Dict:
        # Calculate potential savings from cancellable subscriptions
        unused_subs = self.db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            or_(
                Subscription.usage_last_detected < datetime.utcnow() - timedelta(days=90),
                Subscription.usage_last_detected.is_(None)
            )
        ).all()
        
        potential_monthly_savings = Decimal('0.00')
        potential_annual_savings = Decimal('0.00')
        recommendations = []
        
        for sub in unused_subs:
            if sub.billing_cycle == BillingCycle.MONTHLY:
                monthly_saving = sub.cost
                annual_saving = sub.cost * 12
            elif sub.billing_cycle == BillingCycle.ANNUALLY:
                monthly_saving = sub.cost / 12
                annual_saving = sub.cost
            elif sub.billing_cycle == BillingCycle.QUARTERLY:
                monthly_saving = sub.cost / 3
                annual_saving = sub.cost * 4
            else:
                monthly_saving = sub.cost
                annual_saving = sub.cost * 12
            
            potential_monthly_savings += monthly_saving
            potential_annual_savings += annual_saving
            
            last_usage_days = None
            if sub.usage_last_detected:
                last_usage_days = (datetime.utcnow() - sub.usage_last_detected).days
            
            recommendations.append({
                'subscription_id': sub.id,
                'service_name': sub.service_name,
                'monthly_cost': float(monthly_saving),
                'annual_cost': float(annual_saving),
                'days_unused': last_usage_days,
                'difficulty': sub.cancellation_difficulty.value if sub.cancellation_difficulty else 'unknown',
                'cancellation_url': sub.cancellation_url
            })
        
        return {
            'potential_monthly_savings': float(potential_monthly_savings),
            'potential_annual_savings': float(potential_annual_savings),
            'unused_subscriptions_count': len(unused_subs),
            'recommendations': recommendations
        }
    
    def get_notification_analytics(self, user_id: int) -> Dict:
        # Get notification statistics
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        notifications = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.created_at >= thirty_days_ago
        ).all()
        
        stats = {
            'total_notifications': len(notifications),
            'by_type': {},
            'by_status': {},
            'response_rate': 0
        }
        
        for notification in notifications:
            # Count by type
            notif_type = notification.type.value
            if notif_type not in stats['by_type']:
                stats['by_type'][notif_type] = 0
            stats['by_type'][notif_type] += 1
            
            # Count by status
            status = notification.status.value
            if status not in stats['by_status']:
                stats['by_status'][status] = 0
            stats['by_status'][status] += 1
        
        # Calculate response rate (dismissed vs total)
        dismissed_count = stats['by_status'].get('dismissed', 0)
        if len(notifications) > 0:
            stats['response_rate'] = (dismissed_count / len(notifications)) * 100
        
        return stats
    
    def get_comprehensive_report(self, user_id: int) -> Dict:
        return {
            'spending': self.get_spending_analytics(user_id),
            'trends': self.get_spending_trends(user_id, 6),
            'usage': self.get_usage_analytics(user_id),
            'savings_potential': self.get_cancellation_savings(user_id),
            'notifications': self.get_notification_analytics(user_id),
            'generated_at': datetime.utcnow().isoformat()
        }