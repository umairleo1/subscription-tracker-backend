from sqlalchemy.orm import Session
from typing import Optional, Tuple
from datetime import datetime, timezone

from src.domain.entities.user import User
from src.domain.entities.linked_account import LinkedAccount
from src.presentation.responses.auth import SaveUserRequest, GoogleOAuthProfile, GoogleOAuthTokens
from src.core.exceptions import (
    BaseAPIException,
    ResourceConflictException,
    ValidationException,
    ResourceNotFoundException
)
from src.presentation.responses.response import ErrorCodes
from src.core.security.encryption import encrypt_oauth_tokens

class GoogleAuthService:
    """Service for handling Google OAuth authentication and account management"""
    
    def __init__(self, db: Session):
        self.db = db
        
    def save_user_from_oauth(self, request: SaveUserRequest) -> Tuple[User, bool, bool]:
        """
        Save or update user from Google OAuth data
        
        Returns:
            Tuple[User, account_created, is_new_user]
        """
        profile = request.profile
        tokens = request.tokens
        
        # Check if this Google account already exists
        existing_google_account = self.db.query(LinkedAccount).filter(
            LinkedAccount.google_id == profile.id
        ).first()
        
        if existing_google_account:
            # Update existing account
            user = existing_google_account.user
            self._update_google_account(existing_google_account, profile, tokens)
            self._update_user_login_time(user)
            self.db.commit()
            return user, False, False
            
        # Check if user exists by email (primary account email)
        existing_user = self.db.query(User).filter(User.email == profile.email).first()
        
        if existing_user:
            # Add this as a secondary account
            if request.is_primary:
                raise ResourceConflictException(
                    f"User with email {profile.email} already exists. Cannot create another primary account."
                )
            
            # Create secondary Google account
            google_account = self._create_google_account(
                user=existing_user,
                profile=profile,
                tokens=tokens,
                is_primary=False
            )
            self._update_user_login_time(existing_user)
            self.db.commit()
            return existing_user, True, False
        
        # Create new user with primary Google account
        user = self._create_user_from_profile(profile)
        google_account = self._create_google_account(
            user=user,
            profile=profile,
            tokens=tokens,
            is_primary=True
        )
        self.db.commit()
        return user, True, True
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        return self.db.query(User).filter(User.email == email).first()
    
    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID"""
        google_account = self.db.query(LinkedAccount).filter(
            LinkedAccount.google_id == google_id
        ).first()
        return google_account.user if google_account else None
    
    def unlink_google_account(self, account_id, user_id) -> bool:
        """
        Unlink a Google account from user's profile
        
        Args:
            account_id: ID of the Google account to unlink
            user_id: ID of the user (for security)
            
        Returns:
            bool: True if successfully unlinked
            
        Raises:
            ResourceNotFoundException: If account not found
            ValidationException: If trying to unlink primary account
        """
        google_account = self.db.query(LinkedAccount).filter(
            LinkedAccount.id == account_id,
            LinkedAccount.user_id == user_id
        ).first()
        
        if not google_account:
            raise ResourceNotFoundException("Google account", str(account_id))
        
        if google_account.is_primary:
            raise ValidationException(
                "Cannot unlink primary Google account. Primary account is required to maintain user identity."
            )
        
        # Check if user has other accounts
        total_accounts = self.db.query(LinkedAccount).filter(
            LinkedAccount.user_id == user_id
        ).count()
        
        if total_accounts <= 1:
            raise ValidationException(
                "Cannot unlink the only Google account. Users must have at least one linked account."
            )
        
        # Delete the account
        self.db.delete(google_account)
        self.db.commit()
        return True
    
    def get_user_with_accounts(self, user_id) -> Optional[User]:
        """Get user with all linked Google accounts"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def _create_user_from_profile(self, profile: GoogleOAuthProfile) -> User:
        """Create new user from Google profile"""
        user = User(
            email=profile.email,
            name=profile.name,
            picture=profile.image,
            last_login_at=datetime.now(timezone.utc)
        )
        self.db.add(user)
        self.db.flush()  # Get the ID without committing
        return user
    
    def _create_google_account(
        self,
        user: User,
        profile: GoogleOAuthProfile,
        tokens: GoogleOAuthTokens,
        is_primary: bool = False
    ) -> LinkedAccount:
        """Create Google account record"""
        
        # Convert expires_at timestamp to datetime
        expires_at = None
        if tokens.expires_at:
            expires_at = datetime.fromtimestamp(tokens.expires_at, tz=timezone.utc)
        
        # Encrypt tokens
        encrypted_tokens = encrypt_oauth_tokens(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            id_token=tokens.id_token
        )
        
        google_account = LinkedAccount(
            user_id=user.id,
            google_id=profile.id,
            email=profile.email,
            name=profile.name,
            picture=profile.image,
            is_primary=is_primary,
            access_token_encrypted=encrypted_tokens["access_token_encrypted"],
            refresh_token_encrypted=encrypted_tokens["refresh_token_encrypted"],
            id_token_encrypted=encrypted_tokens["id_token_encrypted"],
            expires_at=expires_at,
            token_type=tokens.token_type,
            scope=tokens.scope,
            last_used_at=datetime.now(timezone.utc)
        )
        
        self.db.add(google_account)
        self.db.flush()
        return google_account
    
    def _update_google_account(
        self,
        google_account: LinkedAccount,
        profile: GoogleOAuthProfile,
        tokens: GoogleOAuthTokens
    ):
        """Update existing Google account with new data"""
        
        # Update profile information
        google_account.email = profile.email
        google_account.name = profile.name
        google_account.picture = profile.image
        
        # Encrypt and update tokens
        encrypted_tokens = encrypt_oauth_tokens(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            id_token=tokens.id_token
        )
        
        google_account.access_token_encrypted = encrypted_tokens["access_token_encrypted"]
        if tokens.refresh_token:
            google_account.refresh_token_encrypted = encrypted_tokens["refresh_token_encrypted"]
        if tokens.id_token:
            google_account.id_token_encrypted = encrypted_tokens["id_token_encrypted"]
        
        # Update token expiration
        if tokens.expires_at:
            google_account.expires_at = datetime.fromtimestamp(
                tokens.expires_at, tz=timezone.utc
            )
        
        google_account.token_type = tokens.token_type
        google_account.scope = tokens.scope
        google_account.last_used_at = datetime.now(timezone.utc)
    
    def _update_user_login_time(self, user: User):
        """Update user's last login time"""
        user.last_login_at = datetime.now(timezone.utc)
    
    def validate_account_limits(self, user_id, max_accounts: int = 5) -> bool:
        """
        Validate that user hasn't exceeded account limits
        
        Args:
            user_id: User ID to check
            max_accounts: Maximum allowed accounts (default 5)
            
        Returns:
            bool: True if within limits
            
        Raises:
            BaseAPIException: If limits exceeded
        """
        current_count = self.db.query(LinkedAccount).filter(
            LinkedAccount.user_id == user_id
        ).count()
        
        if current_count >= max_accounts:
            raise BaseAPIException(
                message=f"Maximum number of Google accounts ({max_accounts}) reached",
                error_code=ErrorCodes.QUOTA_EXCEEDED,
                details={
                    "current_count": current_count,
                    "max_allowed": max_accounts
                }
            )
        
        return True