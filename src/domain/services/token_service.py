"""
Professional token management service
Handles token validation, refresh triggers, and background task coordination
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from src.domain.entities.linked_account import LinkedAccount, TokenStatus
from src.infrastructure.tasks.token_refresh import refresh_oauth_token
from src.core.exceptions import BaseAPIException, ValidationException
from src.presentation.responses.response import ErrorCodes

logger = logging.getLogger(__name__)

class TokenService:
    """Professional service for OAuth token management and refresh coordination"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_and_refresh_token(self, account_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Check if token needs refresh and trigger background refresh if needed
        
        Args:
            account_id: UUID of the linked account
            force_refresh: Force refresh even if not expired
            
        Returns:
            Dict with token status and refresh task info
        """
        try:
            account = self.db.query(LinkedAccount).filter(
                LinkedAccount.id == account_id
            ).first()
            
            if not account:
                raise ValidationException(f"Account {account_id} not found")
            
            # Check if account is active
            if not account.is_active:
                return {
                    'status': 'inactive',
                    'message': 'Account is inactive',
                    'requires_reauth': True
                }
            
            # Check if account already needs re-auth
            if account.needs_reauth:
                return {
                    'status': 'needs_reauth',
                    'message': 'Account requires manual re-authentication',
                    'requires_reauth': True,
                    'error': account.last_auth_error
                }
            
            # Check token expiration
            token_valid = self._is_token_valid(account)
            requires_refresh = self._requires_refresh(account) or force_refresh
            
            if not requires_refresh and token_valid:
                return {
                    'status': 'valid',
                    'message': 'Token is valid and does not need refresh',
                    'expires_at': account.expires_at.isoformat() if account.expires_at else None
                }
            
            # Check if refresh token is available
            if not account.refresh_token_encrypted:
                logger.warning(f"No refresh token for account {account_id}")
                account.mark_needs_reauth("No refresh token available")
                self.db.commit()
                
                return {
                    'status': 'no_refresh_token',
                    'message': 'No refresh token available - requires re-authentication',
                    'requires_reauth': True
                }
            
            # Trigger background refresh
            task = refresh_oauth_token.delay(account_id)
            
            logger.info(f"Queued token refresh task {task.id} for account {account_id}")
            
            return {
                'status': 'refresh_queued',
                'message': 'Token refresh queued in background',
                'task_id': task.id,
                'expires_at': account.expires_at.isoformat() if account.expires_at else None,
                'estimated_completion': '1-2 minutes'
            }
            
        except Exception as e:
            logger.exception(f"Error checking token for account {account_id}")
            raise BaseAPIException(
                message=f"Token check failed: {str(e)}",
                error_code=ErrorCodes.INTERNAL_SERVER_ERROR
            )
    
    def _is_token_valid(self, account: LinkedAccount) -> bool:
        """Check if the current access token is still valid"""
        if not account.expires_at:
            return True  # No expiration info, assume valid
        
        now = datetime.now(timezone.utc)
        # Add 5-minute buffer
        return account.expires_at > (now + timedelta(minutes=5))
    
    def _requires_refresh(self, account: LinkedAccount) -> bool:
        """Check if token should be refreshed proactively"""
        if not account.expires_at:
            return False
        
        now = datetime.now(timezone.utc)
        # Refresh if expiring within 10 minutes
        return account.expires_at <= (now + timedelta(minutes=10))
    
    def get_token_status(self, account_id: str) -> Dict[str, Any]:
        """
        Get comprehensive token status for an account
        
        Args:
            account_id: UUID of the linked account
            
        Returns:
            Dict with detailed token status information
        """
        try:
            account = self.db.query(LinkedAccount).filter(
                LinkedAccount.id == account_id
            ).first()
            
            if not account:
                raise ValidationException(f"Account {account_id} not found")
            
            now = datetime.now(timezone.utc)
            
            # Calculate time until expiration
            time_until_expiry = None
            if account.expires_at:
                time_until_expiry = (account.expires_at - now).total_seconds()
            
            return {
                'account_id': account_id,
                'user_email': account.email,
                'is_active': account.is_active,
                'token_status': account.token_status,
                'needs_reauth': account.needs_reauth,
                'expires_at': account.expires_at.isoformat() if account.expires_at else None,
                'is_expired': account.is_token_expired,
                'requires_refresh': account.requires_refresh,
                'time_until_expiry_seconds': int(time_until_expiry) if time_until_expiry else None,
                'last_token_refresh': account.last_token_refresh.isoformat() if account.last_token_refresh else None,
                'refresh_count': account.token_refresh_count,
                'last_auth_error': account.last_auth_error,
                'has_refresh_token': bool(account.refresh_token_encrypted)
            }
            
        except Exception as e:
            logger.exception(f"Error getting token status for account {account_id}")
            raise BaseAPIException(
                message=f"Token status check failed: {str(e)}",
                error_code=ErrorCodes.INTERNAL_SERVER_ERROR
            )
    
    def get_user_token_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get token status summary for all user's linked accounts
        
        Args:
            user_id: UUID of the user
            
        Returns:
            Dict with summary of all account token statuses
        """
        try:
            accounts = self.db.query(LinkedAccount).filter(
                LinkedAccount.user_id == user_id,
                LinkedAccount.is_active == True
            ).all()
            
            summary = {
                'user_id': user_id,
                'total_accounts': len(accounts),
                'active_tokens': 0,
                'expired_tokens': 0,
                'needs_reauth': 0,
                'accounts': []
            }
            
            for account in accounts:
                status = self.get_token_status(str(account.id))
                summary['accounts'].append(status)
                
                if account.needs_reauth:
                    summary['needs_reauth'] += 1
                elif account.is_token_expired:
                    summary['expired_tokens'] += 1
                else:
                    summary['active_tokens'] += 1
            
            return summary
            
        except Exception as e:
            logger.exception(f"Error getting user token summary for user {user_id}")
            raise BaseAPIException(
                message=f"User token summary failed: {str(e)}",
                error_code=ErrorCodes.INTERNAL_SERVER_ERROR
            )
    
    def refresh_all_user_tokens(self, user_id: str) -> Dict[str, Any]:
        """
        Trigger refresh for all user's tokens that need it
        
        Args:
            user_id: UUID of the user
            
        Returns:
            Dict with refresh task information
        """
        try:
            accounts = self.db.query(LinkedAccount).filter(
                LinkedAccount.user_id == user_id,
                LinkedAccount.is_active == True,
                LinkedAccount.needs_reauth == False,
                LinkedAccount.refresh_token_encrypted.isnot(None)
            ).all()
            
            refresh_tasks = []
            for account in accounts:
                if self._requires_refresh(account):
                    task = refresh_oauth_token.delay(str(account.id))
                    refresh_tasks.append({
                        'account_id': str(account.id),
                        'email': account.email,
                        'task_id': task.id
                    })
            
            return {
                'user_id': user_id,
                'refresh_tasks_queued': len(refresh_tasks),
                'tasks': refresh_tasks
            }
            
        except Exception as e:
            logger.exception(f"Error refreshing user tokens for user {user_id}")
            raise BaseAPIException(
                message=f"User token refresh failed: {str(e)}",
                error_code=ErrorCodes.INTERNAL_SERVER_ERROR
            )