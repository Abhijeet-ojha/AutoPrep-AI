"""Logging and observability middleware."""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging and tracing."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                }
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2),
                },
                exc_info=True,
            )
            raise


class GeminiUsageTracker:
    """Track Gemini API usage for observability."""
    
    def __init__(self):
        self.total_requests = 0
        self.total_tokens = 0
        self.failures = 0
    
    def record_request(self, tokens: int = 0, success: bool = True):
        """Record a Gemini API request."""
        self.total_requests += 1
        self.total_tokens += tokens
        if not success:
            self.failures += 1
        
        logger.info(
            "Gemini API call",
            extra={
                "tokens": tokens,
                "success": success,
                "total_requests": self.total_requests,
                "total_tokens": self.total_tokens,
                "failures": self.failures,
            }
        )
    
    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "failures": self.failures,
            "success_rate": (self.total_requests - self.failures) / max(self.total_requests, 1),
        }


# Global tracker
gemini_tracker = GeminiUsageTracker()
