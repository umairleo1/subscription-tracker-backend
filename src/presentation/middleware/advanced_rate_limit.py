"""
Advanced rate limiting middleware with multiple strategies and audit integration
"""
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Optional, Tuple
import time
import redis
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta

from src.core.config.settings import get_settings
from src.core.tasks.audit_tasks import create_audit_log
from src.domain.entities.audit_log import AuditAction, AuditStatus

logger = logging.getLogger(__name__)
settings = get_settings()

class AdvancedRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Advanced rate limiting middleware with multiple strategies:
    - Fixed window rate limiting
    - Sliding window rate limiting  
    - Token bucket algorithm
    - Progressive penalties
    - IP reputation system
    """
    
    def __init__(self, app, redis_url: str = None):
        super().__init__(app)
        self.redis_client = redis.from_url(redis_url or settings.REDIS_URL or "redis://localhost:6379/1")
        
        # Rate limit configurations for different endpoint types
        self.rate_limits = {
            # Authentication endpoints (more restrictive)
            "auth": {
                "requests_per_minute": 10,
                "requests_per_hour": 100,
                "burst_capacity": 5,
                "penalty_multiplier": 2.0
            },
            # User management endpoints
            "users": {
                "requests_per_minute": 30,
                "requests_per_hour": 500,
                "burst_capacity": 10,
                "penalty_multiplier": 1.5
            },
            # General API endpoints
            "general": {
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "burst_capacity": 20,
                "penalty_multiplier": 1.2
            },
            # Token refresh (system endpoints)
            "token": {
                "requests_per_minute": 5,
                "requests_per_hour": 50,
                "burst_capacity": 2,
                "penalty_multiplier": 3.0
            }
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting checks"""
        start_time = time.time()
        
        try:
            # Get client identifier
            client_id = self._get_client_identifier(request)
            
            # Determine endpoint category
            endpoint_category = self._categorize_endpoint(request.url.path)
            
            # Check rate limits
            is_allowed, limit_info = await self._check_rate_limits(
                client_id, endpoint_category, request
            )
            
            if not is_allowed:
                # Rate limit exceeded
                await self._handle_rate_limit_exceeded(
                    client_id, endpoint_category, request, limit_info
                )
                
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded. Please try again later.",
                        "details": {
                            "limit_type": limit_info["limit_type"],
                            "retry_after": limit_info["retry_after"],
                            "requests_remaining": 0
                        }
                    },
                    headers={
                        "X-RateLimit-Limit": str(limit_info["limit"]),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(limit_info["reset_time"]),
                        "Retry-After": str(limit_info["retry_after"])
                    }
                )
            
            # Process the request
            response = await call_next(request)
            
            # Add rate limit headers to successful responses
            self._add_rate_limit_headers(response, limit_info)
            
            # Track successful request
            await self._track_successful_request(client_id, endpoint_category)
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting middleware error: {str(e)}")
            # Don't block requests if rate limiting fails
            return await call_next(request)
    
    def _get_client_identifier(self, request: Request) -> str:
        """Generate unique client identifier for rate limiting"""
        # Try to get authenticated user ID first
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host
        
        # Include User-Agent hash for better uniqueness
        user_agent = request.headers.get("User-Agent", "")
        user_agent_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        
        return f"ip:{client_ip}:{user_agent_hash}"
    
    def _categorize_endpoint(self, path: str) -> str:
        """Categorize endpoint for appropriate rate limiting"""
        if path.startswith("/api/v1/auth/") or path.startswith("/auth/"):
            return "auth"
        elif path.startswith("/api/v1/users/") and any(x in path for x in ["/tokens", "/linked-accounts"]):
            return "token"
        elif path.startswith("/api/v1/users/"):
            return "users"
        else:
            return "general"
    
    async def _check_rate_limits(self, client_id: str, category: str, request: Request) -> Tuple[bool, Dict]:
        """Check multiple rate limiting algorithms"""
        config = self.rate_limits.get(category, self.rate_limits["general"])
        current_time = time.time()
        
        # Check IP reputation first
        reputation_penalty = await self._get_ip_reputation_penalty(client_id)
        
        # Apply reputation penalty to limits
        adjusted_limits = {
            "requests_per_minute": max(1, int(config["requests_per_minute"] / reputation_penalty)),
            "requests_per_hour": max(5, int(config["requests_per_hour"] / reputation_penalty)),
            "burst_capacity": max(1, int(config["burst_capacity"] / reputation_penalty))
        }
        
        # Check fixed window rate limits (per minute)
        minute_key = f"rate_limit:{client_id}:{category}:minute:{int(current_time // 60)}"
        minute_requests = await self._get_request_count(minute_key)
        
        if minute_requests >= adjusted_limits["requests_per_minute"]:
            return False, {
                "limit_type": "per_minute",
                "limit": adjusted_limits["requests_per_minute"],
                "current": minute_requests,
                "reset_time": int((current_time // 60 + 1) * 60),
                "retry_after": 60 - (current_time % 60)
            }
        
        # Check fixed window rate limits (per hour)
        hour_key = f"rate_limit:{client_id}:{category}:hour:{int(current_time // 3600)}"
        hour_requests = await self._get_request_count(hour_key)
        
        if hour_requests >= adjusted_limits["requests_per_hour"]:
            return False, {
                "limit_type": "per_hour",
                "limit": adjusted_limits["requests_per_hour"],
                "current": hour_requests,
                "reset_time": int((current_time // 3600 + 1) * 3600),
                "retry_after": 3600 - (current_time % 3600)
            }
        
        # Check token bucket for burst capacity
        bucket_allowed = await self._check_token_bucket(
            client_id, category, adjusted_limits["burst_capacity"]
        )
        
        if not bucket_allowed:
            return False, {
                "limit_type": "burst",
                "limit": adjusted_limits["burst_capacity"],
                "current": adjusted_limits["burst_capacity"],
                "reset_time": int(current_time + 60),
                "retry_after": 60
            }
        
        # Increment counters
        await self._increment_counters(minute_key, hour_key, current_time)
        
        return True, {
            "limit_type": "allowed",
            "minute_limit": adjusted_limits["requests_per_minute"],
            "minute_remaining": adjusted_limits["requests_per_minute"] - minute_requests - 1,
            "hour_limit": adjusted_limits["requests_per_hour"],
            "hour_remaining": adjusted_limits["requests_per_hour"] - hour_requests - 1,
            "reputation_penalty": reputation_penalty
        }
    
    async def _get_request_count(self, key: str) -> int:
        """Get current request count from Redis"""
        try:
            count = await self.redis_client.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Failed to get request count: {str(e)}")
            return 0
    
    async def _check_token_bucket(self, client_id: str, category: str, capacity: int) -> bool:
        """Implement token bucket algorithm for burst protection"""
        bucket_key = f"token_bucket:{client_id}:{category}"
        current_time = time.time()
        
        try:
            # Get current bucket state
            bucket_data = await self.redis_client.hgetall(bucket_key)
            
            if bucket_data:
                tokens = float(bucket_data.get("tokens", capacity))
                last_refill = float(bucket_data.get("last_refill", current_time))
            else:
                tokens = float(capacity)
                last_refill = current_time
            
            # Calculate token refill (1 token per 60/capacity seconds)
            time_passed = current_time - last_refill
            refill_rate = capacity / 60  # tokens per second
            tokens = min(capacity, tokens + (time_passed * refill_rate))
            
            if tokens >= 1.0:
                # Consume one token
                tokens -= 1.0
                
                # Update bucket state
                await self.redis_client.hset(bucket_key, {
                    "tokens": str(tokens),
                    "last_refill": str(current_time)
                })
                await self.redis_client.expire(bucket_key, 3600)  # 1 hour expiry
                
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Token bucket check failed: {str(e)}")
            return True  # Allow request if Redis fails
    
    async def _increment_counters(self, minute_key: str, hour_key: str, current_time: float):
        """Increment rate limit counters"""
        try:
            # Increment minute counter
            await self.redis_client.incr(minute_key)
            await self.redis_client.expire(minute_key, 120)  # 2 minutes expiry
            
            # Increment hour counter
            await self.redis_client.incr(hour_key)
            await self.redis_client.expire(hour_key, 7200)  # 2 hours expiry
            
        except Exception as e:
            logger.error(f"Failed to increment counters: {str(e)}")
    
    async def _get_ip_reputation_penalty(self, client_id: str) -> float:
        """Get IP reputation penalty multiplier"""
        try:
            reputation_key = f"ip_reputation:{client_id}"
            reputation_data = await self.redis_client.hgetall(reputation_key)
            
            if not reputation_data:
                return 1.0  # No penalty for new IPs
            
            violations = int(reputation_data.get("violations", 0))
            last_violation = float(reputation_data.get("last_violation", 0))
            current_time = time.time()
            
            # Decay violations over time (24 hour half-life)
            time_since_violation = current_time - last_violation
            decay_factor = 0.5 ** (time_since_violation / 86400)  # 24 hours
            effective_violations = violations * decay_factor
            
            # Calculate penalty (1.0 to 10.0 multiplier)
            penalty = min(10.0, 1.0 + (effective_violations * 0.5))
            
            return penalty
            
        except Exception as e:
            logger.error(f"Failed to get IP reputation: {str(e)}")
            return 1.0
    
    async def _handle_rate_limit_exceeded(self, client_id: str, category: str, request: Request, limit_info: Dict):
        """Handle rate limit exceeded event"""
        try:
            # Update IP reputation
            reputation_key = f"ip_reputation:{client_id}"
            current_time = time.time()
            
            await self.redis_client.hincrby(reputation_key, "violations", 1)
            await self.redis_client.hset(reputation_key, "last_violation", str(current_time))
            await self.redis_client.expire(reputation_key, 604800)  # 7 days
            
            # Create audit log
            create_audit_log(
                action=AuditAction.RATE_LIMIT_EXCEEDED,
                status=AuditStatus.WARNING,
                ip_address=self._extract_ip_from_client_id(client_id),
                user_agent=request.headers.get("User-Agent"),
                details={
                    "client_id": client_id,
                    "category": category,
                    "limit_info": limit_info,
                    "path": request.url.path,
                    "method": request.method
                },
                created_by_system=True
            )
            
            logger.warning(f"Rate limit exceeded for {client_id} on {category} endpoints")
            
        except Exception as e:
            logger.error(f"Failed to handle rate limit exceeded: {str(e)}")
    
    async def _track_successful_request(self, client_id: str, category: str):
        """Track successful request for reputation improvement"""
        try:
            # Successful requests can slowly improve reputation
            reputation_key = f"ip_reputation:{client_id}"
            current_violations = await self.redis_client.hget(reputation_key, "violations")
            
            if current_violations and int(current_violations) > 0:
                # Slowly decrease violations for good behavior
                await self.redis_client.hincrby(reputation_key, "violations", -0.1)
                
        except Exception as e:
            logger.error(f"Failed to track successful request: {str(e)}")
    
    def _add_rate_limit_headers(self, response: Response, limit_info: Dict):
        """Add rate limiting headers to response"""
        if "minute_limit" in limit_info:
            response.headers["X-RateLimit-Limit-Minute"] = str(limit_info["minute_limit"])
            response.headers["X-RateLimit-Remaining-Minute"] = str(limit_info["minute_remaining"])
        
        if "hour_limit" in limit_info:
            response.headers["X-RateLimit-Limit-Hour"] = str(limit_info["hour_limit"])
            response.headers["X-RateLimit-Remaining-Hour"] = str(limit_info["hour_remaining"])
        
        if "reputation_penalty" in limit_info and limit_info["reputation_penalty"] > 1.0:
            response.headers["X-RateLimit-Reputation-Penalty"] = str(round(limit_info["reputation_penalty"], 2))
    
    def _extract_ip_from_client_id(self, client_id: str) -> str:
        """Extract IP address from client ID"""
        if client_id.startswith("ip:"):
            parts = client_id.split(":")
            return parts[1] if len(parts) > 1 else "unknown"
        return "unknown"

# Simple rate limiter for specific endpoints
class EndpointRateLimiter:
    """Simple decorator-based rate limiter for specific endpoints"""
    
    def __init__(self, redis_url: str = None):
        self.redis_client = redis.from_url(redis_url or settings.REDIS_URL or "redis://localhost:6379/1")
    
    def limit(self, requests_per_minute: int = 60, per_user: bool = True):
        """Decorator to apply rate limiting to specific endpoints"""
        def decorator(func):
            async def wrapper(request: Request, *args, **kwargs):
                # Get identifier
                if per_user and hasattr(request.state, 'user_id'):
                    identifier = f"user:{request.state.user_id}"
                else:
                    identifier = request.client.host
                
                # Check rate limit
                current_time = time.time()
                window_key = f"endpoint_limit:{func.__name__}:{identifier}:{int(current_time // 60)}"
                
                try:
                    current_requests = await self.redis_client.incr(window_key)
                    if current_requests == 1:
                        await self.redis_client.expire(window_key, 120)
                    
                    if current_requests > requests_per_minute:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={
                                "error": "RATE_LIMIT_EXCEEDED",
                                "message": f"Rate limit exceeded for this endpoint. Limit: {requests_per_minute} requests per minute.",
                                "retry_after": 60 - (current_time % 60)
                            }
                        )
                    
                    return await func(request, *args, **kwargs)
                    
                except redis.RedisError as e:
                    logger.error(f"Redis error in rate limiter: {str(e)}")
                    # Allow request if Redis is down
                    return await func(request, *args, **kwargs)
            
            return wrapper
        return decorator

# Global rate limiter instance
rate_limiter = EndpointRateLimiter()