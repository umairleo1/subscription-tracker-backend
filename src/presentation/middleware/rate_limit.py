"""
Rate limiting middleware
Professional rate limiting with Redis support
"""
import time
from typing import Dict, Callable
from collections import defaultdict, deque

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window"""
    
    def __init__(self):
        self.clients: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, client_id: str, requests_per_minute: int) -> bool:
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        client_requests = self.clients[client_id]
        while client_requests and client_requests[0] < minute_ago:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) < requests_per_minute:
            client_requests.append(now)
            return True
        
        return False
    
    def get_reset_time(self, client_id: str) -> int:
        if not self.clients[client_id]:
            return int(time.time() + 60)
        return int(self.clients[client_id][0] + 60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with configurable limits"""
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.limiter = InMemoryRateLimiter()
    
    def get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # In production, use authenticated user ID or IP + User-Agent
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        user_agent = request.headers.get("User-Agent", "")
        return f"{client_ip}:{hash(user_agent) % 10000}"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_id = self.get_client_id(request)
        
        if not self.limiter.is_allowed(client_id, self.requests_per_minute):
            reset_time = self.limiter.get_reset_time(client_id)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(max(1, reset_time - int(time.time())))
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = max(0, self.requests_per_minute - len(self.limiter.clients[client_id]))
        reset_time = self.limiter.get_reset_time(client_id)
        
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response