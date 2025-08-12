import time
import uuid
import json
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging requests and responses with timing and request ID
    """
    
    def __init__(self, app, log_requests: bool = True, log_responses: bool = True):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        
        if self.log_requests:
            await self._log_request(request, request_id)
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Add request ID and timing to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log response
        if self.log_responses:
            self._log_response(request, response, request_id, process_time)
        
        return response
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request details"""
        # Extract relevant headers (excluding sensitive ones)
        headers = dict(request.headers)
        sensitive_headers = ['authorization', 'cookie', 'x-api-key']
        filtered_headers = {
            k: v if k.lower() not in sensitive_headers else '[REDACTED]'
            for k, v in headers.items()
        }
        
        # Get content length from headers instead of reading body
        content_length = request.headers.get("content-length", "0")
        
        logger.info(
            f"REQUEST: {request.method} {request.url}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": filtered_headers,
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "content_length": content_length,
                "has_body": request.method in ["POST", "PUT", "PATCH"]
            }
        )
    
    def _log_response(self, request: Request, response: StarletteResponse, request_id: str, process_time: float):
        """Log response details"""
        logger.info(
            f"RESPONSE: {response.status_code} for {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time": round(process_time, 4),
                "response_size": response.headers.get("content-length"),
                "content_type": response.headers.get("content-type")
            }
        )

class CORSMiddleware:
    """
    Enhanced CORS middleware with better error handling
    """
    
    def __init__(
        self,
        allow_origins: list = None,
        allow_methods: list = None,
        allow_headers: list = None,
        allow_credentials: bool = True,
        expose_headers: list = None,
        max_age: int = 600
    ):
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        self.allow_headers = allow_headers or ["*"]
        self.allow_credentials = allow_credentials
        self.expose_headers = expose_headers or ["X-Request-ID", "X-Process-Time"]
        self.max_age = max_age

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware
    Note: For production, use Redis or similar for distributed rate limiting
    """
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = {}
        self.window_size = 60  # 1 minute in seconds
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old entries
        self._cleanup_old_entries(current_time)
        
        # Check rate limit
        if self._is_rate_limited(client_ip, current_time):
            from src.core.exceptions import RateLimitException
            raise RateLimitException("Too many requests. Please try again later.")
        
        # Record this request
        self._record_request(client_ip, current_time)
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = max(0, self.requests_per_minute - len(self.requests.get(client_ip, [])))
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.window_size))
        
        return response
    
    def _cleanup_old_entries(self, current_time: float):
        """Remove entries older than the window size"""
        for client_ip in list(self.requests.keys()):
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if current_time - req_time < self.window_size
            ]
            if not self.requests[client_ip]:
                del self.requests[client_ip]
    
    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """Check if client has exceeded rate limit"""
        if client_ip not in self.requests:
            return False
        
        recent_requests = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < self.window_size
        ]
        
        return len(recent_requests) >= self.requests_per_minute
    
    def _record_request(self, client_ip: str, current_time: float):
        """Record a request timestamp for the client"""
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        self.requests[client_ip].append(current_time)