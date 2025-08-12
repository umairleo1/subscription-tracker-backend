"""
Background token refresh automation tasks
Handles OAuth token lifecycle management and automatic refreshing
"""
from celery import Celery
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import httpx
import logging

from src.database.database import SessionLocal
from src.domain.entities import User, LinkedAccount, TokenStatus
from src.core.security.encryption import decrypt_oauth_tokens, encrypt_oauth_tokens
from src.core.config.settings import get_settings
from src.core.tasks.celery_app import celery_app
from src.domain.entities.audit_log import AuditLog, AuditAction, AuditStatus

logger = logging.getLogger(__name__)
settings = get_settings()

@celery_app.task(bind=True, name="src.core.tasks.token_refresh.refresh_expiring_tokens")
def refresh_expiring_tokens(self):
    """
    Periodically refresh OAuth tokens that are expiring within the next hour
    """
    try:
        db = SessionLocal()
        
        # Find accounts with tokens expiring in next hour and have refresh tokens
        expiry_threshold = datetime.now(timezone.utc) + timedelta(hours=1)
        
        expiring_accounts = db.query(LinkedAccount).filter(
            and_(
                LinkedAccount.is_active == True,
                LinkedAccount.expires_at <= expiry_threshold,
                LinkedAccount.refresh_token_encrypted.is_not(None),
                LinkedAccount.needs_reauth == False,
                or_(
                    LinkedAccount.token_status == TokenStatus.ACTIVE.value,
                    LinkedAccount.token_status == TokenStatus.EXPIRED.value
                )
            )
        ).all()
        
        logger.info(f"Found {len(expiring_accounts)} accounts with expiring tokens")
        
        refresh_results = {
            "success": 0,
            "failed": 0,
            "revoked": 0,
            "errors": []
        }
        
        for account in expiring_accounts:
            try:
                # Attempt to refresh token
                success = _refresh_account_token(account, db)
                if success:
                    refresh_results["success"] += 1
                    logger.info(f"Successfully refreshed token for account {account.email}")
                else:
                    refresh_results["failed"] += 1
                    
            except TokenRevokedException:
                # Handle revoked tokens
                account.mark_needs_reauth("Token revoked by user or Google")
                refresh_results["revoked"] += 1
                logger.warning(f"Token revoked for account {account.email}")
                
            except Exception as e:
                refresh_results["failed"] += 1
                error_msg = f"Failed to refresh token for {account.email}: {str(e)}"
                refresh_results["errors"].append(error_msg)
                logger.error(error_msg)
                
                # Mark account as needing reauth after multiple failures
                account.mark_needs_reauth(f"Token refresh failed: {str(e)}")
        
        db.commit()
        db.close()
        
        # Log audit event
        _create_audit_log(
            action=AuditAction.TOKEN_REFRESH_BATCH,
            details={
                "total_accounts": len(expiring_accounts),
                "results": refresh_results
            },
            status=AuditStatus.SUCCESS if refresh_results["failed"] == 0 else AuditStatus.PARTIAL_SUCCESS
        )
        
        logger.info(f"Token refresh batch completed: {refresh_results}")
        return refresh_results
        
    except Exception as e:
        logger.error(f"Token refresh batch failed: {str(e)}")
        _create_audit_log(
            action=AuditAction.TOKEN_REFRESH_BATCH,
            details={"error": str(e)},
            status=AuditStatus.FAILURE
        )
        raise self.retry(countdown=60, max_retries=3)

@celery_app.task(bind=True, name="src.core.tasks.token_refresh.refresh_single_token")
def refresh_single_token(self, account_id: int):
    """
    Refresh a single account's OAuth token
    """
    try:
        db = SessionLocal()
        
        account = db.query(LinkedAccount).filter(LinkedAccount.id == account_id).first()
        if not account:
            logger.error(f"Account {account_id} not found")
            return {"success": False, "error": "Account not found"}
        
        success = _refresh_account_token(account, db)
        
        db.commit()
        db.close()
        
        result = {"success": success, "account_email": account.email}
        logger.info(f"Single token refresh for {account.email}: {'success' if success else 'failed'}")
        
        return result
        
    except TokenRevokedException:
        logger.warning(f"Token revoked for account {account_id}")
        return {"success": False, "error": "Token revoked", "needs_reauth": True}
        
    except Exception as e:
        logger.error(f"Single token refresh failed for account {account_id}: {str(e)}")
        raise self.retry(countdown=30, max_retries=2)

@celery_app.task(name="src.core.tasks.token_refresh.detect_revoked_tokens")
def detect_revoked_tokens():
    """
    Detect tokens that have been revoked by testing them against Google's tokeninfo endpoint
    """
    try:
        db = SessionLocal()
        
        # Get active accounts that haven't been checked recently
        check_threshold = datetime.now(timezone.utc) - timedelta(hours=6)
        
        accounts_to_check = db.query(LinkedAccount).filter(
            and_(
                LinkedAccount.is_active == True,
                LinkedAccount.token_status == TokenStatus.ACTIVE.value,
                LinkedAccount.needs_reauth == False,
                or_(
                    LinkedAccount.last_used_at.is_(None),
                    LinkedAccount.last_used_at <= check_threshold
                )
            )
        ).limit(50).all()  # Limit to avoid rate limiting
        
        revoked_count = 0
        checked_count = 0
        
        for account in accounts_to_check:
            try:
                if _check_token_validity(account):
                    account.last_used_at = datetime.now(timezone.utc)
                    checked_count += 1
                else:
                    # Token is invalid/revoked
                    account.mark_needs_reauth("Token validation failed - likely revoked")
                    revoked_count += 1
                    logger.warning(f"Detected revoked token for account {account.email}")
                    
            except Exception as e:
                logger.error(f"Failed to check token validity for {account.email}: {str(e)}")
        
        db.commit()
        db.close()
        
        result = {"checked": checked_count, "revoked": revoked_count}
        logger.info(f"Token revocation check completed: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Token revocation detection failed: {str(e)}")
        return {"error": str(e)}

@celery_app.task(name="src.core.tasks.token_refresh.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """
    Clean up tokens that have been expired for more than 30 days
    """
    try:
        db = SessionLocal()
        
        # Find accounts with tokens expired for more than 30 days
        cleanup_threshold = datetime.now(timezone.utc) - timedelta(days=30)
        
        expired_accounts = db.query(LinkedAccount).filter(
            and_(
                LinkedAccount.token_status == TokenStatus.EXPIRED.value,
                LinkedAccount.updated_at <= cleanup_threshold
            )
        ).all()
        
        cleaned_count = 0
        for account in expired_accounts:
            # Clear the encrypted tokens but keep account record for audit
            account.access_token_encrypted = None
            account.refresh_token_encrypted = None
            account.id_token_encrypted = None
            account.token_status = TokenStatus.REVOKED.value
            account.needs_reauth = True
            cleaned_count += 1
        
        db.commit()
        db.close()
        
        logger.info(f"Cleaned up {cleaned_count} expired token records")
        
        return {"cleaned": cleaned_count}
        
    except Exception as e:
        logger.error(f"Token cleanup failed: {str(e)}")
        return {"error": str(e)}

def _refresh_account_token(account: LinkedAccount, db: Session) -> bool:
    """
    Helper function to refresh a single account's OAuth token
    """
    try:
        # Decrypt current refresh token
        decrypted_tokens = decrypt_oauth_tokens(
            refresh_token_encrypted=account.refresh_token_encrypted
        )
        
        refresh_token = decrypted_tokens.get("refresh_token")
        if not refresh_token:
            logger.warning(f"No refresh token available for account {account.email}")
            account.mark_needs_reauth("No refresh token available")
            return False
        
        # Make refresh request to Google
        refresh_data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data=refresh_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Encrypt and store new tokens
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token", refresh_token)  # Use old if not provided
            
            encrypted_tokens = encrypt_oauth_tokens(
                access_token=new_access_token,
                refresh_token=new_refresh_token
            )
            
            # Update account with new token info
            account.access_token_encrypted = encrypted_tokens["access_token_encrypted"]
            if token_data.get("refresh_token"):
                account.refresh_token_encrypted = encrypted_tokens["refresh_token_encrypted"]
            
            # Calculate new expiry
            expires_in = token_data.get("expires_in", 3600)
            new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            account.update_token_info(new_expires_at)
            
            # Create audit log
            _create_audit_log(
                action=AuditAction.TOKEN_REFRESH,
                entity_type="LinkedAccount",
                entity_id=account.id,
                details={"account_email": account.email},
                status=AuditStatus.SUCCESS
            )
            
            return True
            
        elif response.status_code == 400:
            # Likely revoked or invalid refresh token
            error_data = response.json()
            error_msg = error_data.get("error", "Unknown error")
            
            if error_msg in ["invalid_grant", "unauthorized_client"]:
                raise TokenRevokedException(f"Token revoked: {error_msg}")
            else:
                logger.error(f"Token refresh failed for {account.email}: {error_msg}")
                account.mark_needs_reauth(f"Token refresh error: {error_msg}")
                return False
        else:
            logger.error(f"Token refresh failed for {account.email}: HTTP {response.status_code}")
            return False
            
    except TokenRevokedException:
        raise
    except Exception as e:
        logger.error(f"Token refresh exception for {account.email}: {str(e)}")
        account.mark_needs_reauth(f"Token refresh exception: {str(e)}")
        return False

def _check_token_validity(account: LinkedAccount) -> bool:
    """
    Check if a token is still valid using Google's tokeninfo endpoint
    """
    try:
        # Decrypt access token
        decrypted_tokens = decrypt_oauth_tokens(
            access_token_encrypted=account.access_token_encrypted
        )
        
        access_token = decrypted_tokens.get("access_token")
        if not access_token:
            return False
        
        # Check token with Google's tokeninfo endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}"
            )
        
        if response.status_code == 200:
            token_info = response.json()
            
            # Verify token is for correct client and user
            client_id = token_info.get("aud")
            if client_id != settings.GOOGLE_CLIENT_ID:
                logger.warning(f"Token client_id mismatch for {account.email}")
                return False
            
            # Check expiry
            exp = token_info.get("exp")
            if exp and int(exp) < datetime.now(timezone.utc).timestamp():
                return False
            
            return True
        else:
            # Token is invalid
            return False
            
    except Exception as e:
        logger.error(f"Token validity check failed for {account.email}: {str(e)}")
        return False

class TokenRevokedException(Exception):
    """Exception raised when a token has been revoked"""
    pass

def _create_audit_log(action: AuditAction, details: dict, status: AuditStatus, 
                     entity_type: str = None, entity_id: int = None):
    """Helper to create audit log entries"""
    try:
        db = SessionLocal()
        
        audit_log = AuditLog(
            action=action.value,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            status=status.value,
            created_by_system=True
        )
        
        db.add(audit_log)
        db.commit()
        db.close()
        
    except Exception as e:
        logger.error(f"Failed to create audit log: {str(e)}")

# Task to manually trigger token refresh for a user
@celery_app.task(name="src.core.tasks.token_refresh.refresh_user_tokens")
def refresh_user_tokens(user_id: int):
    """
    Refresh all tokens for a specific user
    """
    try:
        db = SessionLocal()
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "User not found"}
        
        results = []
        for account in user.linked_accounts:
            if account.is_active and account.refresh_token_encrypted:
                success = _refresh_account_token(account, db)
                results.append({
                    "account_id": account.id,
                    "email": account.email,
                    "success": success
                })
        
        db.commit()
        db.close()
        
        logger.info(f"Refreshed tokens for user {user_id}: {len([r for r in results if r['success']])} successful")
        
        return {"success": True, "results": results}
        
    except Exception as e:
        logger.error(f"User token refresh failed for user {user_id}: {str(e)}")
        return {"success": False, "error": str(e)}