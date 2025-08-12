from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict
from datetime import datetime
import psutil
import os

from src.database.database import get_db

router = APIRouter(tags=["monitoring"])

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "subscription-tracker-api",
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Database connectivity check
    try:
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
    
    # System metrics
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        health_status["checks"]["system"] = {
            "status": "healthy",
            "metrics": {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_usage_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            }
        }
        
        # Mark as unhealthy if resources are critically low
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
            health_status["status"] = "degraded"
            health_status["checks"]["system"]["status"] = "degraded"
            health_status["checks"]["system"]["message"] = "High resource utilization"
            
    except Exception as e:
        health_status["checks"]["system"] = {
            "status": "unknown",
            "message": f"Could not get system metrics: {str(e)}"
        }
    
    return health_status

@router.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    metrics = {}
    
    try:
        # User metrics
        user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        active_users = db.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true")).scalar()
        
        metrics["users"] = {
            "total_users": user_count,
            "active_users": active_users
        }
        
        # Subscription metrics
        total_subscriptions = db.execute(text("SELECT COUNT(*) FROM subscriptions")).scalar()
        active_subscriptions = db.execute(text("SELECT COUNT(*) FROM subscriptions WHERE status = 'active'")).scalar()
        trial_subscriptions = db.execute(text("SELECT COUNT(*) FROM subscriptions WHERE status = 'trial'")).scalar()
        
        metrics["subscriptions"] = {
            "total_subscriptions": total_subscriptions,
            "active_subscriptions": active_subscriptions,
            "trial_subscriptions": trial_subscriptions
        }
        
        # Email processing metrics
        total_emails = db.execute(text("SELECT COUNT(*) FROM email_processing_logs")).scalar()
        successful_processing = db.execute(text("SELECT COUNT(*) FROM email_processing_logs WHERE status = 'completed'")).scalar()
        failed_processing = db.execute(text("SELECT COUNT(*) FROM email_processing_logs WHERE status = 'failed'")).scalar()
        
        metrics["email_processing"] = {
            "total_emails_processed": total_emails,
            "successful_processing": successful_processing,
            "failed_processing": failed_processing,
            "success_rate": round((successful_processing / total_emails * 100), 2) if total_emails > 0 else 0
        }
        
        # Notification metrics
        total_notifications = db.execute(text("SELECT COUNT(*) FROM notifications")).scalar()
        sent_notifications = db.execute(text("SELECT COUNT(*) FROM notifications WHERE status = 'sent'")).scalar()
        pending_notifications = db.execute(text("SELECT COUNT(*) FROM notifications WHERE status = 'pending'")).scalar()
        
        metrics["notifications"] = {
            "total_notifications": total_notifications,
            "sent_notifications": sent_notifications,
            "pending_notifications": pending_notifications
        }
        
        # Connected accounts metrics
        total_accounts = db.execute(text("SELECT COUNT(*) FROM connected_accounts")).scalar()
        google_accounts = db.execute(text("SELECT COUNT(*) FROM connected_accounts WHERE provider = 'google'")).scalar()
        
        metrics["connected_accounts"] = {
            "total_connected_accounts": total_accounts,
            "google_accounts": google_accounts
        }
        
    except Exception as e:
        metrics["error"] = f"Could not fetch metrics: {str(e)}"
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": metrics
    }

@router.get("/stats/processing")
async def get_processing_stats(db: Session = Depends(get_db)):
    try:
        # Recent processing statistics (last 7 days)
        stats = db.execute(text("""
            SELECT 
                DATE(created_at) as processing_date,
                COUNT(*) as total_processed,
                AVG(processing_time_ms) as avg_processing_time,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                AVG(subscriptions_found) as avg_subscriptions_found
            FROM email_processing_logs 
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY processing_date DESC
        """)).fetchall()
        
        daily_stats = []
        for row in stats:
            daily_stats.append({
                "date": str(row[0]),
                "total_processed": row[1],
                "avg_processing_time_ms": float(row[2]) if row[2] else 0,
                "successful": row[3],
                "failed": row[4],
                "success_rate": (row[3] / row[1] * 100) if row[1] > 0 else 0,
                "avg_subscriptions_found": float(row[5]) if row[5] else 0
            })
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "daily_processing_stats": daily_stats
        }
        
    except Exception as e:
        return {
            "error": f"Could not fetch processing stats: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/stats/financial")
async def get_financial_stats(db: Session = Depends(get_db)):
    try:
        # Financial overview across all users
        stats = db.execute(text("""
            SELECT 
                COUNT(DISTINCT user_id) as users_with_subscriptions,
                COUNT(*) as total_active_subscriptions,
                SUM(CASE WHEN billing_cycle = 'monthly' THEN cost ELSE cost/12 END) as total_monthly_spending,
                AVG(CASE WHEN billing_cycle = 'monthly' THEN cost ELSE cost/12 END) as avg_monthly_per_subscription,
                COUNT(CASE WHEN billing_cycle = 'monthly' THEN 1 END) as monthly_subscriptions,
                COUNT(CASE WHEN billing_cycle = 'annually' THEN 1 END) as annual_subscriptions
            FROM subscriptions 
            WHERE status = 'active'
        """)).fetchone()
        
        # Top services by subscriber count
        top_services = db.execute(text("""
            SELECT 
                service_name,
                COUNT(*) as subscriber_count,
                AVG(cost) as avg_cost
            FROM subscriptions 
            WHERE status = 'active'
            GROUP BY service_name
            ORDER BY subscriber_count DESC
            LIMIT 10
        """)).fetchall()
        
        top_services_data = []
        for row in top_services:
            top_services_data.append({
                "service_name": row[0],
                "subscriber_count": row[1],
                "avg_cost": float(row[2]) if row[2] else 0
            })
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform_stats": {
                "users_with_subscriptions": stats[0] if stats[0] else 0,
                "total_active_subscriptions": stats[1] if stats[1] else 0,
                "total_monthly_spending": float(stats[2]) if stats[2] else 0,
                "avg_monthly_per_subscription": float(stats[3]) if stats[3] else 0,
                "monthly_subscriptions": stats[4] if stats[4] else 0,
                "annual_subscriptions": stats[5] if stats[5] else 0
            },
            "top_services": top_services_data
        }
        
    except Exception as e:
        return {
            "error": f"Could not fetch financial stats: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }