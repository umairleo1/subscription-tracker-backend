"""
User management API endpoints
Handles primary user creation, linked account management, and token lifecycle
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List
from datetime import datetime, timezone
import logging

from src.database.database import get_db
from src.domain.entities import User, LinkedAccount, TokenStatus
from src.presentation.responses.user import (
    CreateUserRequest, CreateUserResponse, LinkAccountRequest, LinkAccountResponse,
    UpdateTokenRequest, TokenUpdateResponse, UserResponse, SaveUserRequest, 
    GoogleOAuthProfile, GoogleOAuthTokens, LinkedAccountResponse
)
from src.domain.services.google_auth_service import GoogleAuthService
from src.core.exceptions import (
    ValidationException,
    ResourceNotFoundException,
    ResourceConflictException
)
from src.presentation.responses.response import APIResponse, ResponseStatus
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
    Create or upsert a user from Google OAuth authentication
    
    This endpoint handles both new user creation and linking additional Google accounts.
    It has complete functionality from the auth service including account limits and validation.
    
    **Flow:**
    1. If Google account doesn't exist: Create new user or link to existing user
    2. If Google account exists: Update tokens and profile information
    3. Enforce business rules (primary account uniqueness, account limits)
    
    **Request Body:**
    - **profile**: Google OAuth profile (id, email, name, picture)
    - **tokens**: Google OAuth tokens (access_token, refresh_token, etc.)
    - **is_primary**: Whether this should be the primary account (for new users)
    """
    try:
        auth_service = GoogleAuthService(db)
        
        # Create a compatible request object for the auth service
        # Convert dict to structured models
        profile_data = GoogleOAuthProfile(**request.profile)
        tokens_data = GoogleOAuthTokens(**request.tokens)
        
        save_request = SaveUserRequest(
            profile=profile_data,
            tokens=tokens_data,
            is_primary=request.is_primary
        )
        
        # Validate request data
        if not save_request.profile.id:
            raise ValidationException("Google user ID is required")
        
        if not save_request.profile.email:
            raise ValidationException("Google email is required")
        
        if not save_request.tokens.access_token:
            raise ValidationException("Google access token is required")
        
        # Check account limits for existing users (only when adding secondary accounts)
        if not save_request.is_primary:
            existing_user = auth_service.get_user_by_email(save_request.profile.email)
            if existing_user:
                auth_service.validate_account_limits(existing_user.id, max_accounts=5)
        
        # Save or update user and Google account using auth service
        user, account_created, is_new_user = auth_service.save_user_from_oauth(save_request)
        
        # Prepare response
        user_response = UserResponse(**user.to_dict())
        response_data = CreateUserResponse(
            user=user_response,
            is_new_user=is_new_user,
            account_created=account_created
        )
        
        # Determine success message
        if is_new_user:
            message = "New user created and Google account linked successfully"
        elif account_created:
            message = "Additional Google account linked successfully"
        else:
            message = "User profile and tokens updated successfully"
        
        logger.info(f"User {'created' if is_new_user else 'updated'}: {user.email}")
        
        return APIResponse(
            status=ResponseStatus.SUCCESS,
            data=response_data,
            message=message
        )
        
    except (ValidationException, ResourceConflictException) as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create/upsert user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/upsert user: {str(e)}"
        )

@router.get("/me", response_model=APIResponse[UserResponse])
async def get_current_user(
    include_inactive: bool = Query(False, description="Include inactive linked accounts"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> APIResponse[UserResponse]:
    """
    Get current authenticated user's data with all linked accounts and token statuses
    
    This is a convenience endpoint for frontends that need current user information.
    Equivalent to GET /{user_id} but uses the authenticated user's ID automatically.
    """
    # Filter accounts based on include_inactive parameter
    if not include_inactive:
        # Only return active accounts
        current_user.linked_accounts = [acc for acc in current_user.linked_accounts if acc.is_active]
    
    user_response = UserResponse(**current_user.to_dict())
    
    return APIResponse(
        status=ResponseStatus.SUCCESS,
        data=user_response,
        message="Current user data retrieved successfully"
    )

@router.get("/{user_id}", response_model=APIResponse[UserResponse])
async def get_user_with_accounts(
    user_id: str,
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
        status=ResponseStatus.SUCCESS,
        data=user_response,
        message="User data retrieved successfully"
    )

@router.post("/{user_id}/linked-accounts", response_model=APIResponse[LinkAccountResponse], status_code=status.HTTP_201_CREATED)
async def link_secondary_account(
    user_id: str,
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
            status=ResponseStatus.SUCCESS,
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
    user_id: str,
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> APIResponse[dict]:
    """
    Unlink a secondary Google account (prevents unlinking the primary account)
    
    Uses the same GoogleAuthService as the auth endpoint for consistency.
    """
    # Authorization check
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own linked accounts"
        )
    
    try:
        auth_service = GoogleAuthService(db)
        
        # Validate account_id format (convert to string for auth service)
        account_id_str = str(account_id)
        
        # Find the Google account to get details
        google_account = db.query(LinkedAccount).filter(LinkedAccount.id == account_id).first()
        
        if not google_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Linked account not found"
            )
        
        # Verify ownership
        if google_account.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Linked account not found"
            )
        
        account_email = google_account.email
        was_primary = google_account.is_primary
        
        # Use GoogleAuthService for consistent unlinking logic
        success = auth_service.unlink_google_account(account_id_str, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unlink Google account"
            )
        
        # Get updated user data
        user = auth_service.get_user_with_accounts(user_id)
        
        response_data = {
            "unlinked_account": {
                "id": account_id_str,
                "email": account_email,
                "was_primary": was_primary
            },
            "user": user.to_dict(include_accounts=True) if user else None
        }
        
        logger.info(f"Unlinked secondary account {account_email} from user {current_user.email}")
        
        return APIResponse(
            status=ResponseStatus.SUCCESS,
            data=response_data,
            message="Account unlinked successfully"
        )
        
    except HTTPException:
        raise
    except (ValidationException, ResourceNotFoundException) as e:
        logger.error(f"Service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
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
    user_id: str,
    account_id: str,
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
            status=ResponseStatus.SUCCESS,
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
    user_id: str,
    account_id: str,
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
            status=ResponseStatus.SUCCESS,
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