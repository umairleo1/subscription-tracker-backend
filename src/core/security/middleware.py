"""
Security middleware for the application
Professional security headers and protections
"""
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware that adds security headers"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Add request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        security_headers = {
            "X-Request-ID": request_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()"
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response