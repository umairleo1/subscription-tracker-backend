from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from src.domain.entities.notification import Notification, NotificationType, NotificationChannel, NotificationStatus
from src.domain.entities.subscription import Subscription, SubscriptionStatus
from src.domain.entities.user import User
from src.presentation.responses.notification import NotificationCreate

class NotificationService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_notification(self, notification: NotificationCreate) -> Notification:
        db_notification = Notification(**notification.dict())
        self.db.add(db_notification)
        self.db.commit()
        self.db.refresh(db_notification)
        return db_notification
    
    def get_user_notifications(self, user_id: int, limit: int = 50) -> List[Notification]:
        return self.db.query(Notification).filter(
            Notification.user_id == user_id
        ).order_by(Notification.created_at.desc()).limit(limit).all()
    
    def mark_notification_sent(self, notification_id: int) -> bool:
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id
        ).first()
        
        if not notification:
            return False
        
        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.utcnow()
        self.db.commit()
        return True
    
    def mark_notification_failed(self, notification_id: int, error_msg: str = "") -> bool:
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id
        ).first()
        
        if not notification:
            return False
        
        notification.status = NotificationStatus.FAILED
        notification.retry_count += 1
        # Store error in metadata if needed
        self.db.commit()
        return True
    
    def get_pending_notifications(self, limit: int = 100) -> List[Notification]:
        return self.db.query(Notification).filter(
            Notification.status == NotificationStatus.PENDING,
            Notification.scheduled_for <= datetime.utcnow()
        ).limit(limit).all()
    
    def schedule_renewal_reminders(self) -> int:
        # Find subscriptions with upcoming renewals
        upcoming_renewals = self.db.query(Subscription).join(User).filter(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
            Subscription.next_billing_date.isnot(None),
            Subscription.next_billing_date > datetime.utcnow(),
            Subscription.next_billing_date <= datetime.utcnow() + timedelta(days=7),
            Subscription.renewal_reminder_sent == False
        ).all()
        
        notifications_created = 0
        
        for subscription in upcoming_renewals:
            # Calculate reminder time (3 days before renewal)
            reminder_time = subscription.next_billing_date - timedelta(days=3)
            
            if reminder_time > datetime.utcnow():
                notification = NotificationCreate(
                    user_id=subscription.user_id,
                    subscription_id=subscription.id,
                    type=NotificationType.RENEWAL_REMINDER,
                    channel=NotificationChannel.EMAIL,
                    title=f"{subscription.service_name} renewal reminder",
                    message=f"Your {subscription.service_name} subscription (${subscription.cost}) will renew on {subscription.next_billing_date.strftime('%Y-%m-%d')}",
                    action_url=f"/subscriptions/{subscription.id}",
                    scheduled_for=reminder_time
                )
                
                self.create_notification(notification)
                
                # Mark as reminder sent
                subscription.renewal_reminder_sent = True
                notifications_created += 1
        
        self.db.commit()
        return notifications_created
    
    def schedule_trial_ending_alerts(self) -> int:
        # Find trials ending soon
        ending_trials = self.db.query(Subscription).join(User).filter(
            Subscription.status == SubscriptionStatus.TRIAL,
            Subscription.trial_end_date.isnot(None),
            Subscription.trial_end_date > datetime.utcnow(),
            Subscription.trial_end_date <= datetime.utcnow() + timedelta(days=7)
        ).all()
        
        notifications_created = 0
        
        for subscription in ending_trials:
            days_left = (subscription.trial_end_date - datetime.utcnow()).days
            
            # Send notifications at 7, 3, and 1 day before trial ends
            reminder_days = [7, 3, 1]
            
            for reminder_day in reminder_days:
                if days_left <= reminder_day:
                    reminder_time = subscription.trial_end_date - timedelta(days=reminder_day)
                    
                    if reminder_time > datetime.utcnow() - timedelta(hours=1):  # Don't schedule past reminders
                        notification = NotificationCreate(
                            user_id=subscription.user_id,
                            subscription_id=subscription.id,
                            type=NotificationType.TRIAL_ENDING,
                            channel=NotificationChannel.EMAIL,
                            title=f"{subscription.service_name} trial ending soon",
                            message=f"Your {subscription.service_name} trial ends in {days_left} days. Cancel now to avoid charges of ${subscription.cost}.",
                            action_url=f"/subscriptions/{subscription.id}",
                            scheduled_for=reminder_time
                        )
                        
                        self.create_notification(notification)
                        notifications_created += 1
        
        self.db.commit()
        return notifications_created
    
    def schedule_usage_warnings(self) -> int:
        # Find subscriptions with no recent usage
        inactive_threshold = datetime.utcnow() - timedelta(days=90)
        
        inactive_subscriptions = self.db.query(Subscription).join(User).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.usage_last_detected < inactive_threshold
        ).all()
        
        notifications_created = 0
        
        for subscription in inactive_subscriptions:
            # Check if we've already sent a usage warning recently
            recent_warning = self.db.query(Notification).filter(
                Notification.user_id == subscription.user_id,
                Notification.subscription_id == subscription.id,
                Notification.type == NotificationType.USAGE_WARNING,
                Notification.created_at > datetime.utcnow() - timedelta(days=30)
            ).first()
            
            if not recent_warning:
                notification = NotificationCreate(
                    user_id=subscription.user_id,
                    subscription_id=subscription.id,
                    type=NotificationType.USAGE_WARNING,
                    channel=NotificationChannel.EMAIL,
                    title=f"Haven't used {subscription.service_name} lately",
                    message=f"You haven't used {subscription.service_name} in over 90 days. Consider cancelling to save ${subscription.cost}/month.",
                    action_url=f"/subscriptions/{subscription.id}",
                    scheduled_for=datetime.utcnow()
                )
                
                self.create_notification(notification)
                notifications_created += 1
        
        self.db.commit()
        return notifications_created
    
    def schedule_duplicate_alerts(self, user_id: int) -> int:
        # Find potential duplicate subscriptions for a user
        user_subscriptions = self.db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).all()
        
        # Group by service name (case insensitive)
        service_groups = {}
        for sub in user_subscriptions:
            service_key = sub.service_name.lower()
            if service_key not in service_groups:
                service_groups[service_key] = []
            service_groups[service_key].append(sub)
        
        notifications_created = 0
        
        for service_name, subscriptions in service_groups.items():
            if len(subscriptions) > 1:
                # Check if we've already alerted about these duplicates
                recent_alert = self.db.query(Notification).filter(
                    Notification.user_id == user_id,
                    Notification.type == NotificationType.DUPLICATE_DETECTED,
                    Notification.message.contains(service_name),
                    Notification.created_at > datetime.utcnow() - timedelta(days=7)
                ).first()
                
                if not recent_alert:
                    total_cost = sum(sub.cost for sub in subscriptions)
                    
                    notification = NotificationCreate(
                        user_id=user_id,
                        subscription_id=subscriptions[0].id,
                        type=NotificationType.DUPLICATE_DETECTED,
                        channel=NotificationChannel.IN_APP,
                        title=f"Duplicate {service_name.title()} subscriptions detected",
                        message=f"You have {len(subscriptions)} active subscriptions for {service_name.title()}, costing ${total_cost} total. Consider consolidating.",
                        action_url=f"/subscriptions?filter={service_name}",
                        scheduled_for=datetime.utcnow()
                    )
                    
                    self.create_notification(notification)
                    notifications_created += 1
        
        self.db.commit()
        return notifications_created
    
    def run_scheduled_notifications(self) -> Dict[str, int]:
        results = {
            "renewal_reminders": self.schedule_renewal_reminders(),
            "trial_alerts": self.schedule_trial_ending_alerts(),
            "usage_warnings": self.schedule_usage_warnings()
        }
        
        return results
    
    def dismiss_notification(self, notification_id: int, user_id: int) -> bool:
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        
        if not notification:
            return False
        
        notification.status = NotificationStatus.DISMISSED
        self.db.commit()
        return True