from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.presentation.responses.auth import SaveUserRequest, SaveUserResponse
from src.presentation.responses.response import success_response, ErrorCodes
from src.domain.services.google_auth_service import GoogleAuthService
from src.core.exceptions import (
    BaseAPIException,
    ValidationException,
    ResourceNotFoundException,
    ResourceConflictException
)

router = APIRouter()

@router.post("/save-user", response_model=dict)
async def save_user(
    user_data: SaveUserRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Save or update user from Google OAuth authentication
    
    This endpoint receives Google OAuth profile and tokens from NextAuth.js frontend.
    It handles both new user creation and linking additional Google accounts.
    
    **Flow:**
    1. If Google account doesn't exist: Create new user or link to existing user
    2. If Google account exists: Update tokens and profile information
    3. Enforce business rules (primary account uniqueness, account limits)
    
    **Request Body:**
    - **profile**: Google OAuth profile (id, email, name, image)
    - **tokens**: Google OAuth tokens (access_token, refresh_token, etc.)
    - **is_primary**: Whether this should be the primary account (for new users)
    """
    try:
        auth_service = GoogleAuthService(db)
        
        # Validate request data
        if not user_data.profile.id:
            raise ValidationException("Google user ID is required")
        
        if not user_data.profile.email:
            raise ValidationException("Google email is required")
        
        if not user_data.tokens.access_token:
            raise ValidationException("Google access token is required")
        
        # Check account limits for existing users (only when adding secondary accounts)
        if not user_data.is_primary:
            existing_user = auth_service.get_user_by_email(user_data.profile.email)
            if existing_user:
                auth_service.validate_account_limits(existing_user.id, max_accounts=5)
        
        # Save or update user and Google account
        user, account_created, is_new_user = auth_service.save_user_from_oauth(user_data)
        
        # Prepare response data
        response_data = SaveUserResponse(
            user=user.to_dict(include_accounts=True),
            account_created=account_created,
            is_new_user=is_new_user
        )
        
        # Determine success message
        if is_new_user:
            message = "New user created and Google account linked successfully"
        elif account_created:
            message = "Additional Google account linked successfully"
        else:
            message = "User profile and tokens updated successfully"
        
        response = success_response(
            data=response_data.model_dump(),
            message=message
        )
        return jsonable_encoder(response.model_dump())
        
    except (ValidationException, ResourceConflictException, BaseAPIException):
        raise
    except Exception as e:
        raise BaseAPIException(
            message="Failed to save user data",
            error_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            details={"error": str(e)}
        )

@router.delete("/accounts/{account_id}", response_model=dict)
async def unlink_google_account(
    account_id: str,
    request: Request,
    db: Session = Depends(get_db)
    # Note: In production, you'd authenticate the user here
    # For now, we'll pass user_id in request body or as parameter
):
    """
    Unlink a Google account from user's profile
    
    Removes a secondary Google account. Primary accounts cannot be unlinked
    to maintain user identity and system integrity.
    
    **Security Rules:**
    - Cannot unlink primary Google account
    - User must have at least one Google account
    - Only account owner can unlink their accounts
    
    **Path Parameters:**
    - **account_id**: ID of the Google account to unlink
    """
    try:
        # TODO: In production, get user_id from authenticated session
        # For now, we need to find the user by account_id
        auth_service = GoogleAuthService(db)
        
        # Validate account_id (UUID format)
        import uuid
        try:
            uuid.UUID(account_id)
        except ValueError:
            raise ValidationException("Invalid account ID format")
        
        # Find the Google account to get user_id
        from src.domain.entities.linked_account import LinkedAccount
        google_account = db.query(LinkedAccount).filter(LinkedAccount.id == account_id).first()
        
        if not google_account:
            raise ResourceNotFoundException("Google account", str(account_id))
        
        user_id = google_account.user_id
        account_email = google_account.email
        was_primary = google_account.is_primary
        
        # Perform the unlink
        success = auth_service.unlink_google_account(account_id, user_id)
        
        if not success:
            raise BaseAPIException(
                message="Failed to unlink Google account",
                error_code=ErrorCodes.DATABASE_ERROR
            )
        
        # Get updated user data
        user = auth_service.get_user_with_accounts(user_id)
        
        response_data = {
            "unlinked_account": {
                "id": account_id,
                "email": account_email,
                "was_primary": was_primary
            },
            "user": user.to_dict(include_accounts=True) if user else None
        }
        
        response = success_response(
            data=response_data,
            message="Google account unlinked successfully"
        )
        return jsonable_encoder(response.model_dump())
        
    except (ValidationException, ResourceNotFoundException, BaseAPIException):
        raise
    except Exception as e:
        raise BaseAPIException(
            message="Failed to unlink Google account",
            error_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            details={"error": str(e)}
        )