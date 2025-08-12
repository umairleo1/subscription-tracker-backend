"""
Professional token management API endpoints
Provides token status, refresh triggers, and monitoring capabilities
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import Optional

from src.database.database import get_db
from src.domain.services.token_service import TokenService
from src.presentation.responses.response import success_response, error_response
from src.core.exceptions import BaseAPIException, ValidationException
from src.utils.auth import get_current_active_user
from src.domain.entities.user import User

router = APIRouter(tags=["Token Management"])

@router.get("/status/{account_id}")
async def get_token_status(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get comprehensive token status for a specific linked account
    
    **Path Parameters:**
    - **account_id**: UUID of the linked account
    
    **Returns:**
    - Token expiration status
    - Refresh availability  
    - Last refresh attempt
    - Error details if any
    """
    try:
        token_service = TokenService(db)
        status = token_service.get_token_status(account_id)
        
        response = success_response(
            data=status,
            message="Token status retrieved successfully"
        )
        return jsonable_encoder(response.model_dump())
        
    except (ValidationException, BaseAPIException) as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get token status: {str(e)}"
        )

@router.post("/refresh/{account_id}")
async def refresh_account_token(
    account_id: str,
    force_refresh: bool = Query(False, description="Force refresh even if token is valid"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Trigger token refresh for a specific account
    
    **Path Parameters:**
    - **account_id**: UUID of the linked account
    
    **Query Parameters:**
    - **force_refresh**: Force refresh even if token appears valid
    
    **Returns:**
    - Refresh task information
    - Estimated completion time
    - Task ID for monitoring
    """
    try:
        token_service = TokenService(db)
        result = token_service.check_and_refresh_token(account_id, force_refresh)
        
        if result.get('requires_reauth'):
            response = error_response(
                message=result['message'],
                error_code="TOKEN_REQUIRES_REAUTH",
                details=result
            )
            return jsonable_encoder(response.model_dump())
        
        response = success_response(
            data=result,
            message=result['message']
        )
        return jsonable_encoder(response.model_dump())
        
    except (ValidationException, BaseAPIException) as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}"
        )

@router.get("/user/summary")
async def get_user_token_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get token status summary for all user's linked accounts
    
    **Returns:**
    - Count of active, expired, and problematic tokens
    - Individual account status details  
    - Overall token health summary
    """
    try:
        token_service = TokenService(db)
        summary = token_service.get_user_token_summary(str(current_user.id))
        
        response = success_response(
            data=summary,
            message="User token summary retrieved successfully"
        )
        return jsonable_encoder(response.model_dump())
        
    except (ValidationException, BaseAPIException) as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user token summary: {str(e)}"
        )

@router.post("/user/refresh-all")
async def refresh_all_user_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Trigger refresh for all user's tokens that need refreshing
    
    **Returns:**
    - List of refresh tasks queued
    - Task IDs for monitoring progress
    - Estimated completion times
    """
    try:
        token_service = TokenService(db)
        result = token_service.refresh_all_user_tokens(str(current_user.id))
        
        message = f"Queued {result['refresh_tasks_queued']} token refresh tasks"
        if result['refresh_tasks_queued'] == 0:
            message = "No tokens needed refreshing"
        
        response = success_response(
            data=result,
            message=message
        )
        return jsonable_encoder(response.model_dump())
        
    except (ValidationException, BaseAPIException) as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh user tokens: {str(e)}"
        )

@router.get("/task/{task_id}/status")
async def get_refresh_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Check the status of a token refresh background task
    
    **Path Parameters:**
    - **task_id**: Celery task ID returned from refresh request
    
    **Returns:**
    - Task completion status
    - Result data if completed
    - Error information if failed
    """
    try:
        from src.infrastructure.celery_app import celery_app
        
        # Get task result
        task_result = celery_app.AsyncResult(task_id)
        
        result_data = {
            'task_id': task_id,
            'status': task_result.status,
            'ready': task_result.ready(),
            'successful': task_result.successful() if task_result.ready() else None
        }
        
        if task_result.ready():
            if task_result.successful():
                result_data['result'] = task_result.result
                message = "Task completed successfully"
            else:
                result_data['error'] = str(task_result.result)
                message = "Task failed"
        else:
            result_data['info'] = task_result.info or {}
            message = "Task is still running"
        
        response = success_response(
            data=result_data,
            message=message
        )
        return jsonable_encoder(response.model_dump())
        
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )