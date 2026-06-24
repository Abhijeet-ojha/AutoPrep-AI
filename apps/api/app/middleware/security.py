"""Security middleware and utilities."""

import logging
import re
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

# File upload restrictions
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".json"}
MAX_FILE_SIZE = settings.max_upload_size_mb * 1024 * 1024  # Convert MB to bytes

# Rate limiting (simple in-memory)
request_counts: dict[str, list[float]] = {}


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for validation and rate limiting."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Add security headers
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response


def validate_file_upload(filename: str, file_size: int) -> None:
    """
    Validate file upload for security.
    
    Args:
        filename: Name of uploaded file
        file_size: Size in bytes
    
    Raises:
        HTTPException: If validation fails
    """
    # Check extension
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB"
        )
    
    # Check for suspicious filenames
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )


def sanitize_user_input(text: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        text: User input text
    
    Returns:
        Sanitized text
    """
    # Remove any potential SQL injection patterns (basic)
    text = re.sub(r"('|(--)|(/\*)|(\*/)|(\bSELECT\b)|(\bDROP\b)|(\bINSERT\b)|(\bUPDATE\b)|(\bDELETE\b))", "", text, flags=re.IGNORECASE)
    
    # Limit length
    max_length = 10000
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()


def sanitize_dataset_content(text: str) -> str:
    """
    Sanitize dataset content before sending to Gemini to prevent prompt injection.
    
    Args:
        text: Dataset content or metadata
    
    Returns:
        Sanitized text safe for AI prompts
    """
    # Truncate to prevent token overflow
    max_length = 5000
    if len(text) > max_length:
        text = text[:max_length] + "... (truncated)"
    
    # Remove potential prompt injection patterns
    injection_patterns = [
        r"ignore previous instructions",
        r"disregard all",
        r"forget everything",
        r"new instructions",
        r"system prompt",
    ]
    
    for pattern in injection_patterns:
        text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
    
    return text


def check_rate_limit(client_id: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
    """
    Simple in-memory rate limiting.
    
    Args:
        client_id: Client identifier (IP, user ID, etc.)
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
    
    Returns:
        True if allowed, False if rate limited
    """
    import time
    
    current_time = time.time()
    
    if client_id not in request_counts:
        request_counts[client_id] = []
    
    # Remove old requests outside window
    request_counts[client_id] = [
        req_time for req_time in request_counts[client_id]
        if current_time - req_time < window_seconds
    ]
    
    # Check limit
    if len(request_counts[client_id]) >= max_requests:
        return False
    
    # Add current request
    request_counts[client_id].append(current_time)
    return True
