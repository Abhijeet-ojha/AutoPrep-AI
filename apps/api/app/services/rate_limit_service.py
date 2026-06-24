"""Rate limiting service for API endpoint protection."""

import time

# In-memory storage mapping client_id -> list of float timestamps of upload attempts
_upload_attempts: dict[str, list[float]] = {}


def track_upload_attempt(client_id: str) -> None:
    """
    Record an upload attempt for a given client identifier.
    
    Args:
        client_id: Unique client identifier (e.g. client IP)
    """
    current_time = time.time()
    if client_id not in _upload_attempts:
        _upload_attempts[client_id] = []
    _upload_attempts[client_id].append(current_time)


def is_rate_limited(client_id: str, limit: int = 20, window: int = 3600) -> bool:
    """
    Check if a client has exceeded the rate limit.
    
    Args:
        client_id: Unique client identifier (e.g. client IP)
        limit: Max upload actions allowed in window
        window: Window duration in seconds
        
    Returns:
        True if rate limited, False otherwise
    """
    current_time = time.time()
    if client_id not in _upload_attempts:
        return False
    
    # Filter attempts that fall within the current sliding window
    attempts = [t for t in _upload_attempts[client_id] if current_time - t < window]
    _upload_attempts[client_id] = attempts
    
    return len(attempts) >= limit
