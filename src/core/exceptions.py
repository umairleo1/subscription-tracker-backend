from typing import Dict, Any, List, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError as PydanticValidationError
from jose import JWTError
import logging
import traceback
import uuid
from datetime import datetime

from src.presentation.responses.response import (
    APIResponse, ErrorResponse, ValidationError, ErrorCodes
)

logger = logging.getLogger(__name__)

class BaseAPIException(Exception):
    """Base exception class for API errors"""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Dict[str, Any] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

class ValidationException(BaseAPIException):
    """Exception for validation errors"""
    
    def __init__(self, message: str = "Validation failed", validation_errors: List[ValidationError] = None):
        self.validation_errors = validation_errors or []
        super().__init__(
            message=message,
            error_code=ErrorCodes.VALIDATION_ERROR,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

class AuthenticationException(BaseAPIException):
    """Exception for authentication errors"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code=ErrorCodes.UNAUTHORIZED,
            status_code=status.HTTP_401_UNAUTHORIZED
        )

class AuthorizationException(BaseAPIException):
    """Exception for authorization errors"""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code=ErrorCodes.FORBIDDEN,
            status_code=status.HTTP_403_FORBIDDEN
        )

class ResourceNotFoundException(BaseAPIException):
    """Exception for resource not found"""
    
    def __init__(self, resource: str = "Resource", resource_id: str = None):
        message = f"{resource} not found"
        if resource_id:
            message += f" (ID: {resource_id})"
        
        super().__init__(
            message=message,
            error_code=ErrorCodes.RESOURCE_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "resource_id": resource_id}
        )

class ResourceConflictException(BaseAPIException):
    """Exception for resource conflicts"""
    
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message=message,
            error_code=ErrorCodes.RESOURCE_CONFLICT,
            status_code=status.HTTP_409_CONFLICT
        )

class ExternalServiceException(BaseAPIException):
    """Exception for external service errors"""
    
    def __init__(self, service: str, message: str = "External service error"):
        super().__init__(
            message=f"{service}: {message}",
            error_code=ErrorCodes.EXTERNAL_SERVICE_ERROR,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"service": service}
        )

class RateLimitException(BaseAPIException):
    """Exception for rate limiting"""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            error_code=ErrorCodes.RATE_LIMIT_EXCEEDED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )

def create_exception_handlers(app):
    """Add all exception handlers to the FastAPI app"""
    
    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        """Handle custom API exceptions"""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        logger.error(
            f"API Exception: {exc.error_code} - {exc.message}",
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
                "error_code": exc.error_code,
                "details": exc.details
            }
        )
        
        response = ErrorResponse(
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            request_id=request_id
        )
        
        if isinstance(exc, ValidationException):
            response.error.validation_errors = exc.validation_errors
        
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(response.dict())
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle FastAPI HTTP exceptions"""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        # Map HTTP status codes to error codes
        error_code_mapping = {
            400: ErrorCodes.INVALID_INPUT,
            401: ErrorCodes.UNAUTHORIZED,
            403: ErrorCodes.FORBIDDEN,
            404: ErrorCodes.RESOURCE_NOT_FOUND,
            409: ErrorCodes.RESOURCE_CONFLICT,
            422: ErrorCodes.VALIDATION_ERROR,
            429: ErrorCodes.RATE_LIMIT_EXCEEDED,
            500: ErrorCodes.INTERNAL_SERVER_ERROR,
        }
        
        error_code = error_code_mapping.get(exc.status_code, ErrorCodes.INTERNAL_SERVER_ERROR)
        
        logger.warning(
            f"HTTP Exception: {exc.status_code} - {exc.detail}",
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
                "status_code": exc.status_code
            }
        )
        
        response = ErrorResponse(
            message=str(exc.detail),
            error_code=error_code,
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(response.dict())
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle FastAPI request validation errors"""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        validation_errors = []
        for error in exc.errors():
            field = ".".join([str(loc) for loc in error["loc"]])
            validation_errors.append(ValidationError(
                field=field,
                message=error["msg"],
                code=error["type"]
            ))
        
        logger.warning(
            f"Validation Error: {len(validation_errors)} field(s) failed validation",
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
                "validation_errors": [ve.dict() for ve in validation_errors]
            }
        )
        
        response = ErrorResponse(
            message="Validation failed",
            error_code=ErrorCodes.VALIDATION_ERROR,
            validation_errors=validation_errors,
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder(response.dict())
        )
    
    @app.exception_handler(SQLAlchemyError)
    async def database_exception_handler(request: Request, exc: SQLAlchemyError):
        """Handle database errors"""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        logger.error(
            f"Database Error: {str(exc)}",
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
                "exception": str(exc)
            }
        )
        
        # Handle specific database errors
        if isinstance(exc, IntegrityError):
            message = "Data integrity constraint violated"
            error_code = ErrorCodes.RESOURCE_CONFLICT
            status_code = status.HTTP_409_CONFLICT
        else:
            message = "Database operation failed"
            error_code = ErrorCodes.DATABASE_ERROR
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        response = ErrorResponse(
            message=message,
            error_code=error_code,
            details={"database_error": str(exc)} if app.debug else None,
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(response.dict())
        )
    
    @app.exception_handler(JWTError)
    async def jwt_exception_handler(request: Request, exc: JWTError):
        """Handle JWT errors"""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        logger.warning(
            f"JWT Error: {str(exc)}",
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method
            }
        )
        
        response = ErrorResponse(
            message="Invalid or expired token",
            error_code=ErrorCodes.TOKEN_INVALID,
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=jsonable_encoder(response.dict())
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions"""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        logger.error(
            f"Unhandled Exception: {str(exc)}",
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method,
                "traceback": traceback.format_exc()
            }
        )
        
        response = ErrorResponse(
            message="An unexpected error occurred",
            error_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            details={"error": str(exc)} if app.debug else None,
            request_id=request_id
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(response.dict())
        )