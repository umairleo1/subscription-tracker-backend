"""
User management API endpoints
Handles primary user creation, linked account management, and token lifecycle
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone
import logging

from src.database.database import get_db
from src.domain.entities import User, LinkedAccount, TokenStatus
from src.presentation.responses.user import (
    CreateUserRequest, CreateUserResponse, LinkAccountRequest, LinkAccountResponse,
    UpdateTokenRequest, TokenUpdateResponse, UserResponse
)
from src.presentation.responses.response import APIResponse
from src.core.security.encryption import encrypt_oauth_tokens
from src.utils.auth import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["User Management"])

@router.post("/", response_model=APIResponse[CreateUserResponse], status_code=status.HTTP_201_CREATED)
async def create_or_upsert_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db)
) -> APIResponse[CreateUserResponse]:
    """
    Create or upsert a primary user on first sign-in via NextAuth.js Google OAuth
    
    This endpoint handles the initial user registration when they sign in with Google for the first time.
    It creates both a User record and their primary LinkedAccount with encrypted OAuth tokens.
    """
    try:
        # Extract profile and token data
        profile = request.profile
        tokens = request.tokens
        
        # Validate required profile fields
        google_id = profile.get("id")
        email = profile.get("email")
        if not google_id or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile must include 'id' and 'email' fields"
            )
        
        # Check if user already exists (by email for primary account)
        existing_user = db.query(User).filter(User.email == email).first()
        is_new_user = existing_user is None
        
        if existing_user:
            # Update existing user's last login
            existing_user.last_login_at = datetime.now(timezone.utc)
            user = existing_user
            
            # Check if primary account exists and update tokens
            primary_account = user.primary_account
            if primary_account:
                # Encrypt and update tokens
                encrypted_tokens = encrypt_oauth_tokens(
                    access_token=tokens.get("access_token"),
                    refresh_token=tokens.get("refresh_token"),
                    id_token=tokens.get("id_token")
                )
                
                primary_account.access_token_encrypted = encrypted_tokens["access_token_encrypted"]
                primary_account.refresh_token_encrypted = encrypted_tokens["refresh_token_encrypted"]
                primary_account.id_token_encrypted = encrypted_tokens["id_token_encrypted"]
                primary_account.expires_at = datetime.fromtimestamp(tokens.get("expires_at", 0), tz=timezone.utc)
                primary_account.token_type = tokens.get("token_type", "Bearer")
                primary_account.scope = tokens.get("scope")
                primary_account.token_status = TokenStatus.ACTIVE.value
                primary_account.needs_reauth = False
                primary_account.last_used_at = datetime.now(timezone.utc)
                
                # Update profile info in case it changed
                primary_account.name = profile.get("name")
                primary_account.picture = profile.get("picture")
                
                account_created = False
            else:
                # Create primary account if it doesn't exist (shouldn't happen but handle it)
                account_created = True
                primary_account = _create_linked_account(
                    user=user,
                    profile=profile,
                    tokens=tokens,
                    is_primary=True
                )
                db.add(primary_account)
        else:
            # Create new user
            user = User(
                email=email,
                name=profile.get("name"),
                picture=profile.get("picture"),
                last_login_at=datetime.now(timezone.utc)
            )
            db.add(user)
            db.flush()  # Get user.id
            
            # Create primary linked account
            primary_account = _create_linked_account(
                user=user,
                profile=profile,
                tokens=tokens,
                is_primary=True
            )
            db.add(primary_account)
            account_created = True
        
        db.commit()
        db.refresh(user)
        
        # Prepare response
        user_response = UserResponse(**user.to_dict())
        response_data = CreateUserResponse(
            user=user_response,
            is_new_user=is_new_user,
            account_created=account_created
        )
        
        logger.info(f"User {'created' if is_new_user else 'updated'}: {email}")
        
        return APIResponse(
            success=True,
            data=response_data,
            message=f"User {'created' if is_new_user else 'updated'} successfully"
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create/upsert user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/upsert user: {str(e)}"
        )

@router.get("/{user_id}", response_model=APIResponse[UserResponse])
async def get_user_with_accounts(
    user_id: int,
    include_inactive: bool = Query(False, description="Include inactive linked accounts"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> APIResponse[UserResponse]:
    """
    Retrieve primary user data along with all linked secondary accounts and their token statuses
    """
    # Authorization: users can only access their own data
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own user data"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Filter accounts based on include_inactive parameter
    if not include_inactive:
        # Only return active accounts
        user.linked_accounts = [acc for acc in user.linked_accounts if acc.is_active]
    
    user_response = UserResponse(**user.to_dict())
    
    return APIResponse(
        success=True,
        data=user_response,
        message="User data retrieved successfully"
    )

@router.post("/{user_id}/linked-accounts", response_model=APIResponse[LinkAccountResponse], status_code=status.HTTP_201_CREATED)
async def link_secondary_account(
    user_id: int,
    request: LinkAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> APIResponse[LinkAccountResponse]:
    """
    Link a new secondary Google account to an existing user
    """
    # Authorization check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own linked accounts"
        )
    
    try:
        profile = request.profile
        tokens = request.tokens
        
        google_id = profile.get("id")
        email = profile.get("email")
        
        if not google_id or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile must include 'id' and 'email' fields"
            )
        
        # Check if this Google account is already linked anywhere
        existing_account = db.query(LinkedAccount).filter(
            LinkedAccount.google_id == google_id
        ).first()
        
        if existing_account:
            if existing_account.user_id == user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This Google account is already linked to your account"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This Google account is already linked to another user"
                )
        
        # Check account limits (max 5 total accounts)
        account_count = db.query(LinkedAccount).filter(
            LinkedAccount.user_id == user_id,
            LinkedAccount.is_active == True
        ).count()
        
        if account_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Maximum of 5 Google accounts can be linked. Please remove an account first."
            )
        
        # Create new linked account (secondary)
        linked_account = _create_linked_account(
            user=current_user,
            profile=profile,
            tokens=tokens,
            is_primary=False
        )
        
        db.add(linked_account)
        db.commit()
        db.refresh(linked_account)
        db.refresh(current_user)
        
        # Prepare response
        user_response = UserResponse(**current_user.to_dict())
        linked_account_response = LinkedAccountResponse(**linked_account.to_dict())
        
        response_data = LinkAccountResponse(
            user=user_response,
            linked_account=linked_account_response,
            is_new_account=True
        )
        
        logger.info(f"Linked secondary account {email} to user {current_user.email}")
        
        return APIResponse(
            success=True,
            data=response_data,
            message="Account linked successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to link account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link account: {str(e)}"
        )

@router.delete("/{user_id}/linked-accounts/{account_id}", response_model=APIResponse[dict])
async def unlink_secondary_account(
    user_id: int,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> APIResponse[dict]:
    """
    Unlink a secondary Google account (prevents unlinking the primary account)
    """
    # Authorization check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own linked accounts"
        )
    
    # Find the account to unlink
    account = db.query(LinkedAccount).filter(
        and_(
            LinkedAccount.id == account_id,
            LinkedAccount.user_id == user_id
        )
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked account not found"
        )
    
    # Prevent unlinking primary account
    if account.is_primary:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot unlink the primary account. You must have at least one linked account."
        )
    
    try:
        # Soft delete - mark as inactive
        account.is_active = False
        account.token_status = TokenStatus.REVOKED.value
        account.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        
        logger.info(f"Unlinked secondary account {account.email} from user {current_user.email}")
        
        return APIResponse(
            success=True,
            data={"account_id": account_id, "status": "unlinked"},
            message="Account unlinked successfully"
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to unlink account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlink account: {str(e)}"
        )

@router.patch("/{user_id}/linked-accounts/{account_id}/tokens", response_model=APIResponse[TokenUpdateResponse])
async def update_account_tokens(
    user_id: int,
    account_id: int,
    request: UpdateTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> APIResponse[TokenUpdateResponse]:
    """
    Update stored tokens and expiry timestamps after a successful token refresh
    """
    # Authorization check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own linked accounts"
        )
    
    # Find the account
    account = db.query(LinkedAccount).filter(
        and_(
            LinkedAccount.id == account_id,
            LinkedAccount.user_id == user_id
        )
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked account not found"
        )
    
    try:
        # Encrypt new tokens
        encrypted_tokens = encrypt_oauth_tokens(
            access_token=request.access_token,
            refresh_token=request.refresh_token
        )
        
        # Update token information
        account.access_token_encrypted = encrypted_tokens["access_token_encrypted"]
        if request.refresh_token:
            account.refresh_token_encrypted = encrypted_tokens["refresh_token_encrypted"]
        
        account.expires_at = datetime.fromtimestamp(request.expires_at, tz=timezone.utc)
        account.token_type = request.token_type
        account.update_token_info(account.expires_at)
        
        db.commit()
        db.refresh(account)
        
        response_data = TokenUpdateResponse(
            account_id=account_id,
            token_status=account.token_status,
            expires_at=account.expires_at,
            last_token_refresh=account.last_token_refresh,
            message="Tokens updated successfully"
        )
        
        logger.info(f"Updated tokens for account {account.email}")
        
        return APIResponse(
            success=True,
            data=response_data,
            message="Tokens updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update tokens: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tokens: {str(e)}"
        )

@router.patch("/{user_id}/linked-accounts/{account_id}/reauth", response_model=APIResponse[dict])
async def mark_account_reauth_complete(
    user_id: int,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> APIResponse[dict]:
    """
    Mark linked account as re-authenticated after user completes OAuth re-consent
    """
    # Authorization check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own linked accounts"
        )
    
    # Find the account
    account = db.query(LinkedAccount).filter(
        and_(
            LinkedAccount.id == account_id,
            LinkedAccount.user_id == user_id
        )
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked account not found"
        )
    
    try:
        account.mark_reauth_complete()
        db.commit()
        
        logger.info(f"Marked account {account.email} as re-authenticated")
        
        return APIResponse(
            success=True,
            data={"account_id": account_id, "status": "reauth_complete"},
            message="Account marked as re-authenticated"
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to mark reauth complete: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark reauth complete: {str(e)}"
        )

def _create_linked_account(user: User, profile: dict, tokens: dict, is_primary: bool = False) -> LinkedAccount:
    """
    Helper function to create a LinkedAccount with encrypted tokens
    """
    # Encrypt OAuth tokens
    encrypted_tokens = encrypt_oauth_tokens(
        access_token=tokens.get("access_token"),
        refresh_token=tokens.get("refresh_token"),
        id_token=tokens.get("id_token")
    )
    
    expires_at = None
    if tokens.get("expires_at"):
        expires_at = datetime.fromtimestamp(tokens.get("expires_at"), tz=timezone.utc)
    
    return LinkedAccount(
        user_id=user.id,
        google_id=profile.get("id"),
        email=profile.get("email"),
        name=profile.get("name"),
        picture=profile.get("picture"),
        is_primary=is_primary,
        access_token_encrypted=encrypted_tokens["access_token_encrypted"],
        refresh_token_encrypted=encrypted_tokens["refresh_token_encrypted"],
        id_token_encrypted=encrypted_tokens["id_token_encrypted"],
        expires_at=expires_at,
        token_type=tokens.get("token_type", "Bearer"),
        scope=tokens.get("scope"),
        token_status=TokenStatus.ACTIVE.value,
        needs_reauth=False,
        last_used_at=datetime.now(timezone.utc)
    )