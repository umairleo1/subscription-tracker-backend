"""
Professional OAuth token refresh background tasks
Handles automatic token refresh, retry logic, and error handling
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from celery import current_task
from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_, or_

from src.infrastructure.celery_app import celery_app
from src.database.database import engine
from src.domain.entities.linked_account import LinkedAccount, TokenStatus
from src.domain.entities.user import User
from src.core.security.encryption import decrypt_oauth_tokens, encrypt_oauth_tokens
from src.core.exceptions import BaseAPIException
from src.core.config.settings import get_settings

logger = logging.getLogger(__name__)

# Create database session for background tasks
SessionLocal = sessionmaker(bind=engine)

class TokenRefreshService:
    """Professional service for handling OAuth token refresh operations"""
    
    def __init__(self):
        self.session = SessionLocal()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        self.session.close()
    
    def refresh_google_token(self, account_id: str) -> Dict[str, Any]:
        """
        Refresh OAuth token for a specific Google account
        
        Args:
            account_id: UUID of the linked account
            
        Returns:
            Dict with refresh status and details
        """
        try:
            # Use SELECT FOR UPDATE to prevent concurrent processing of same account
            from sqlalchemy import text
            account = self.session.query(LinkedAccount).filter(
                LinkedAccount.id == account_id
            ).with_for_update().first()
            
            if not account:
                raise ValueError(f"Account {account_id} not found")
            
            # Check if token was recently refreshed (within last 2 minutes) to prevent duplicate processing
            from datetime import datetime, timezone, timedelta
            recent_refresh_threshold = datetime.now(timezone.utc) - timedelta(minutes=2)
            if (account.last_token_refresh and 
                account.last_token_refresh > recent_refresh_threshold and 
                account.token_status == TokenStatus.ACTIVE.value):
                logger.info(f"Skipping token refresh for account {account_id} - recently refreshed")
                return {
                    'success': True,
                    'account_id': account_id,
                    'message': 'Token recently refreshed, skipping',
                    'skipped': True,
                    'expires_at': account.expires_at.isoformat() if account.expires_at else None
                }
            
            # Safety checks - only refresh tokens for eligible accounts
            if not account.is_active:
                logger.info(f"Skipping token refresh for inactive account {account_id}")
                return {
                    'success': False,
                    'error': 'Account is inactive',
                    'skipped': True
                }
            
            if account.needs_reauth:
                logger.info(f"Skipping token refresh for account {account_id} - already needs reauth")
                return {
                    'success': False,
                    'error': 'Account already needs re-authentication',
                    'skipped': True
                }
            
            if account.token_status != TokenStatus.ACTIVE.value:
                logger.info(f"Skipping token refresh for account {account_id} - token status: {account.token_status}")
                return {
                    'success': False,
                    'error': f'Token status not active: {account.token_status}',
                    'skipped': True
                }
            
            # Decrypt current tokens
            decrypted_tokens = decrypt_oauth_tokens(
                refresh_token_encrypted=account.refresh_token_encrypted
            )
            
            if not decrypted_tokens.get('refresh_token'):
                logger.warning(f"No refresh token available for account {account_id}")
                account.mark_needs_reauth("No refresh token available")
                self.session.commit()
                return {
                    'success': False,
                    'error': 'No refresh token available',
                    'requires_reauth': True
                }
            
            # Simulate Google OAuth token refresh
            # In production, you'd call Google's token refresh endpoint
            new_token_data = self._call_google_token_refresh(
                decrypted_tokens['refresh_token']
            )
            
            if new_token_data['success']:
                # Encrypt and store new tokens
                encrypted_tokens = encrypt_oauth_tokens(
                    access_token=new_token_data['access_token'],
                    refresh_token=new_token_data.get('refresh_token'),  # May be None
                    id_token=new_token_data.get('id_token')
                )
                
                # Update account
                account.access_token_encrypted = encrypted_tokens['access_token_encrypted']
                if encrypted_tokens['refresh_token_encrypted']:
                    account.refresh_token_encrypted = encrypted_tokens['refresh_token_encrypted']
                if encrypted_tokens['id_token_encrypted']:
                    account.id_token_encrypted = encrypted_tokens['id_token_encrypted']
                
                # Update token metadata
                expires_at = None
                if new_token_data.get('expires_in'):
                    expires_at = datetime.now(timezone.utc) + timedelta(
                        seconds=new_token_data['expires_in']
                    )
                
                account.update_token_info(expires_at=expires_at)
                account.last_used_at = datetime.now(timezone.utc)
                
                self.session.commit()
                
                logger.info(f"Successfully refreshed token for account {account_id}")
                return {
                    'success': True,
                    'account_id': account_id,
                    'user_email': account.email,
                    'expires_at': expires_at.isoformat() if expires_at else None
                }
            else:
                # Refresh failed - mark for re-auth
                error_msg = new_token_data.get('error', 'Token refresh failed')
                account.mark_needs_reauth(error_msg)
                self.session.commit()
                
                logger.error(f"Token refresh failed for account {account_id}: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'requires_reauth': True
                }
                
        except Exception as e:
            self.session.rollback()
            logger.exception(f"Error refreshing token for account {account_id}")
            raise
    
    def _call_google_token_refresh(self, refresh_token: str) -> Dict[str, Any]:
        """
        Call Google's token refresh endpoint
        In production, this would make actual HTTP requests to Google
        """
        try:
            # Simulate successful token refresh for development
            # In production, replace with actual Google OAuth call:
            #
            # import requests
            # response = requests.post('https://oauth2.googleapis.com/token', data={
            #     'client_id': settings.GOOGLE_CLIENT_ID,
            #     'client_secret': settings.GOOGLE_CLIENT_SECRET,
            #     'refresh_token': refresh_token,
            #     'grant_type': 'refresh_token'
            # })
            # 
            # if response.status_code == 200:
            #     return response.json()
            # else:
            #     return {'success': False, 'error': 'Token refresh failed'}
            
            # Always make actual Google API calls for ALL tokens
            logger.info("Making actual Google token refresh API call")
            import requests
            
            settings = get_settings()
            response = requests.post('https://oauth2.googleapis.com/token', data={
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                return {
                    'success': True,
                    'access_token': token_data.get('access_token'),
                    'expires_in': token_data.get('expires_in', 3600),
                    'token_type': token_data.get('token_type', 'Bearer')
                }
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('error_description', f'HTTP {response.status_code}')
                logger.error(f"Google token refresh failed: {error_msg}")
                return {
                    'success': False,
                    'error': f'Google API error: {error_msg}'
                }
            
        except ImportError as e:
            logger.error(f"Missing requests library: {str(e)}")
            return {
                'success': False,
                'error': 'Missing requests library for Google API calls'
            }
        except Exception as e:
            if 'requests' in str(e):
                logger.error(f"Google token refresh network error: {str(e)}")
                return {
                    'success': False,
                    'error': f'Network error calling Google API: {str(e)}'
                }
            else:
                logger.error(f"Google token refresh API call failed: {str(e)}")
                return {
                    'success': False,
                    'error': f'API call failed: {str(e)}'
                }
    
    def find_accounts_needing_refresh(self) -> List[LinkedAccount]:
        """
        Find all accounts that need token refresh
        Only includes accounts that:
        - Are active
        - Don't need manual re-authentication
        - Have valid refresh tokens
        - Have active token status
        - Are expiring soon (within 10 minutes)
        """
        refresh_threshold = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        return self.session.query(LinkedAccount).filter(
            and_(
                LinkedAccount.is_active == True,
                LinkedAccount.needs_reauth == False,
                LinkedAccount.refresh_token_encrypted.isnot(None),
                LinkedAccount.token_status == TokenStatus.ACTIVE.value,
                LinkedAccount.expires_at <= refresh_threshold
            )
        ).all()

@celery_app.task(
    bind=True, 
    name='src.infrastructure.tasks.token_refresh.refresh_oauth_token',
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    acks_late=True,
    reject_on_worker_lost=True
)
def refresh_oauth_token(self, account_id: str) -> Dict[str, Any]:
    """
    Background task to refresh OAuth token for a specific account
    
    Args:
        account_id: UUID string of the linked account
        
    Returns:
        Dict with task result status
    """
    task_id = current_task.request.id
    logger.info(f"Starting token refresh task {task_id} for account {account_id}")
    
    try:
        with TokenRefreshService() as service:
            result = service.refresh_google_token(account_id)
            
            # Update task state
            if result['success']:
                current_task.update_state(
                    state='SUCCESS',
                    meta={
                        'account_id': account_id,
                        'status': 'Token refreshed successfully',
                        'expires_at': result.get('expires_at')
                    }
                )
            else:
                current_task.update_state(
                    state='FAILURE',
                    meta={
                        'account_id': account_id,
                        'error': result['error'],
                        'requires_reauth': result.get('requires_reauth', False)
                    }
                )
            
            return result
            
    except Exception as exc:
        logger.exception(f"Token refresh task {task_id} failed for account {account_id}")
        
        # Enhanced retry logic with exponential backoff
        retry_count = self.request.retries
        countdown = min(60 * (2 ** retry_count), 600)  # Exponential backoff, max 10 minutes
        
        # Don't retry certain permanent errors
        if any(error_type in str(exc).lower() for error_type in [
            'invalid_grant', 'invalid_client', 'account not found'
        ]):
            logger.error(f"Permanent error for account {account_id}, not retrying: {exc}")
            current_task.update_state(
                state='FAILURE',
                meta={
                    'account_id': account_id,
                    'error': str(exc),
                    'permanent_error': True
                }
            )
            return {'success': False, 'error': str(exc), 'permanent_error': True}
        
        try:
            raise self.retry(exc=exc, countdown=countdown, max_retries=3)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for token refresh task {task_id}")
            current_task.update_state(
                state='FAILURE',
                meta={
                    'account_id': account_id,
                    'error': str(exc),
                    'max_retries_exceeded': True
                }
            )
            return {'success': False, 'error': str(exc), 'max_retries_exceeded': True}

@celery_app.task(name='src.infrastructure.tasks.token_refresh.refresh_all_expired_tokens')
def refresh_all_expired_tokens() -> Dict[str, Any]:
    """
    Periodic task to refresh all expired OAuth tokens
    Runs every 5 minutes via Celery Beat
    """
    logger.info("Starting bulk token refresh task")
    
    try:
        with TokenRefreshService() as service:
            accounts_needing_refresh = service.find_accounts_needing_refresh()
            
            if not accounts_needing_refresh:
                logger.info("No accounts need token refresh")
                return {
                    'success': True,
                    'accounts_processed': 0,
                    'message': 'No tokens needed refresh'
                }
            
            # Queue individual refresh tasks with uniqueness check
            task_results = []
            for account in accounts_needing_refresh:
                # Use account ID as task ID to prevent duplicates
                task_id = f"refresh_token_{account.id}"
                try:
                    task = refresh_oauth_token.apply_async(
                        args=[str(account.id)],
                        task_id=task_id,
                        retry=True
                    )
                    task_results.append({
                        'account_id': str(account.id),
                        'user_email': account.email,
                        'task_id': task.id
                    })
                except Exception as e:
                    # Task might already exist, log and continue
                    if "ALREADY_RECEIVED" in str(e) or "Duplicate" in str(e):
                        logger.info(f"Task already queued for account {account.id}, skipping")
                        continue
                    else:
                        logger.error(f"Failed to queue task for account {account.id}: {e}")
                        continue
            
            logger.info(f"Queued {len(task_results)} token refresh tasks")
            
            return {
                'success': True,
                'accounts_processed': len(task_results),
                'tasks_queued': task_results
            }
            
    except Exception as e:
        logger.exception("Bulk token refresh task failed")
        return {
            'success': False,
            'error': str(e)
        }

@celery_app.task(name='src.infrastructure.tasks.token_refresh.cleanup_failed_refresh_attempts')
def cleanup_failed_refresh_attempts() -> Dict[str, Any]:
    """
    Cleanup task to handle accounts with persistent refresh failures
    Runs hourly to mark accounts needing manual re-authentication
    """
    logger.info("Starting token refresh cleanup task")
    
    try:
        with TokenRefreshService() as service:
            # Find accounts that have been failing refresh for more than 24 hours
            threshold_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            failed_accounts = service.session.query(LinkedAccount).filter(
                and_(
                    LinkedAccount.token_status == TokenStatus.NEEDS_REAUTH.value,
                    LinkedAccount.updated_at <= threshold_time,
                    LinkedAccount.is_active == True
                )
            ).all()
            
            cleanup_count = 0
            for account in failed_accounts:
                # Mark account as needing manual attention
                account.last_auth_error = "Automatic token refresh failed - requires manual re-authentication"
                account.updated_at = datetime.now(timezone.utc)
                cleanup_count += 1
            
            service.session.commit()
            
            logger.info(f"Cleaned up {cleanup_count} failed token refresh attempts")
            
            return {
                'success': True,
                'accounts_cleaned': cleanup_count
            }
            
    except Exception as e:
        logger.exception("Token cleanup task failed")
        return {
            'success': False,
            'error': str(e)
        }