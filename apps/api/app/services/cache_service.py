import logging

logger = logging.getLogger(__name__)

# In-memory store: session_id -> { cache_key -> cache_value }
_session_cache = {}

def get_cached_val(session_id: str, key: str):
    """Retrieve a cached value for a specific session."""
    session_store = _session_cache.get(session_id)
    if session_store and key in session_store:
        logger.info(f"Cache Hit for session {session_id}, key: {key}")
        return session_store[key]
    return None

def set_cached_val(session_id: str, key: str, value):
    """Set a cached value for a specific session."""
    session_store = _session_cache.setdefault(session_id, {})
    session_store[key] = value
    logger.info(f"Cache Set for session {session_id}, key: {key}")

def invalidate_cache(session_id: str):
    """Clear all cached values for a session. Call this when the dataset changes."""
    if session_id in _session_cache:
        _session_cache.pop(session_id)
        logger.info(f"Cache Invalidated for session {session_id}")
