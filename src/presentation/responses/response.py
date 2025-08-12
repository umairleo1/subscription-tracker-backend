from typing import Optional, Any, List, Dict, Union, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class ResponseStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"

class ValidationError(BaseModel):
    field: str
    message: str
    code: str = "validation_error"

class APIError(BaseModel):
    code: str = Field(..., description="Error code for programmatic handling")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    validation_errors: Optional[List[ValidationError]] = Field(None, description="Field validation errors")

class PaginationMeta(BaseModel):
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

T = TypeVar('T')

class APIResponse(BaseModel, Generic[T]):
    """
    Standardized API response wrapper
    """
    status: ResponseStatus = Field(..., description="Response status")
    message: str = Field(..., description="Response message")
    data: Optional[T] = Field(None, description="Response data")
    error: Optional[APIError] = Field(None, description="Error information")
    meta: Optional[Dict[str, Any]] = Field(None, description="Response metadata")
    pagination: Optional[PaginationMeta] = Field(None, description="Pagination information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

    def dict(self, **kwargs):
        """Override dict method to properly serialize datetime objects"""
        data = super().dict(**kwargs)
        # Convert datetime objects to ISO format strings
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat() + 'Z' if obj.tzinfo is None else obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            return obj
        
        return convert_datetime(data)

class SuccessResponse(APIResponse):
    """Success response wrapper"""
    status: ResponseStatus = ResponseStatus.SUCCESS
    
    def __init__(self, data: Any = None, message: str = "Success", meta: Dict[str, Any] = None, **kwargs):
        super().__init__(
            status=ResponseStatus.SUCCESS,
            message=message,
            data=data,
            meta=meta,
            **kwargs
        )

class ErrorResponse(APIResponse):
    """Error response wrapper"""
    status: ResponseStatus = ResponseStatus.ERROR
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "GENERIC_ERROR",
        details: Dict[str, Any] = None,
        validation_errors: List[ValidationError] = None,
        **kwargs
    ):
        error = APIError(
            code=error_code,
            message=message,
            details=details,
            validation_errors=validation_errors
        )
        super().__init__(
            status=ResponseStatus.ERROR,
            message=message,
            error=error,
            **kwargs
        )

class PaginatedResponse(SuccessResponse):
    """Paginated response wrapper"""
    
    def __init__(
        self,
        data: List[Any],
        page: int,
        per_page: int,
        total: int,
        message: str = "Success",
        **kwargs
    ):
        total_pages = (total + per_page - 1) // per_page
        pagination = PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        super().__init__(
            data=data,
            message=message,
            pagination=pagination,
            **kwargs
        )

# Commonly used error codes
class ErrorCodes:
    # Authentication & Authorization
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    
    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
    
    # Resource Management
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    
    # HTTP Errors
    HTTP_ERROR = "HTTP_ERROR"
    
    # Business Logic
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    
    # External Services
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    OAUTH_ERROR = "OAUTH_ERROR"
    EMAIL_SERVICE_ERROR = "EMAIL_SERVICE_ERROR"
    
    # System Errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    
    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"

# Response helper functions
def success_response(data: Any = None, message: str = "Operation completed successfully") -> APIResponse:
    """Create a standardized success response"""
    return SuccessResponse(data=data, message=message)

def error_response(
    message: str, 
    error_code: str = ErrorCodes.INTERNAL_SERVER_ERROR,
    details: Dict[str, Any] = None,
    validation_errors: List[ValidationError] = None
) -> APIResponse:
    """Create a standardized error response"""
    return ErrorResponse(message=message, error_code=error_code, details=details, validation_errors=validation_errors)

def paginated_response(
    data: List[Any],
    page: int,
    per_page: int,
    total: int,
    message: str = "Data retrieved successfully"
) -> APIResponse:
    """Create a standardized paginated response"""
    return PaginatedResponse(data=data, page=page, per_page=per_page, total=total, message=message)

def validation_error_response(validation_errors: List[ValidationError]) -> APIResponse:
    """Create a standardized validation error response"""
    return ErrorResponse(
        message="Validation failed",
        error_code=ErrorCodes.VALIDATION_ERROR,
        validation_errors=validation_errors
    )