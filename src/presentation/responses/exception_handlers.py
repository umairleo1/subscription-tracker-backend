"""
Exception handlers for the application
Professional error handling and responses
"""
import logging
from typing import Union

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.encoders import jsonable_encoder

from src.core.exceptions import BaseAPIException
from src.presentation.responses.response import error_response, ErrorCodes

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """Setup all exception handlers for the application"""
    
    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        """Handle custom API exceptions"""
        logger.error(f"API Exception: {exc.message} - Details: {exc.details}")
        
        response = error_response(
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details,
            validation_errors=getattr(exc, 'validation_errors', None)
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(response.model_dump())
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle FastAPI HTTP exceptions"""
        logger.error(f"HTTP Exception {exc.status_code}: {exc.detail}")
        
        response = error_response(
            message=str(exc.detail),
            error_code=ErrorCodes.HTTP_ERROR,
            details={"status_code": exc.status_code}
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(response.model_dump())
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors"""
        logger.error(f"Validation Error: {exc.errors()}")
        
        validation_errors = []
        for error in exc.errors():
            validation_errors.append({
                "field": ".".join(str(x) for x in error["loc"][1:]),  # Skip 'body'
                "message": error["msg"],
                "type": error["type"],
                "input": error.get("input")
            })
        
        response = error_response(
            message="Request validation failed",
            error_code=ErrorCodes.VALIDATION_ERROR,
            validation_errors=validation_errors
        )
        
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(response.model_dump())
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""
        logger.exception(f"Unexpected error: {str(exc)}")
        
        response = error_response(
            message="An unexpected error occurred",
            error_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            details={"error": str(exc)} if app.debug else {}
        )
        
        return JSONResponse(
            status_code=500,
            content=jsonable_encoder(response.model_dump())
        )