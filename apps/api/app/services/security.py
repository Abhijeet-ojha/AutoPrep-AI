import os
import re
import html
import logging

logger = logging.getLogger(__name__)

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal, directory inclusion,
    and remove characters that are invalid on common filesystems.
    """
    # Remove directory paths
    base = os.path.basename(filename)
    # Remove directory navigation sequences
    base = base.replace("../", "").replace("..\\", "").replace("..", "")
    # Keep only alphanumeric, dot, underscore, hyphen
    sanitized = re.sub(r'[^a-zA-Z0-9_\-\.]', '', base)
    if not sanitized:
        sanitized = "unnamed_file"
    return sanitized

def sanitize_prompt(prompt: str, max_chars: int = 4000) -> str:
    """
    Clean prompt inputs against HTML/script injection, trim whitespace,
    and enforce a maximum payload limit.
    """
    if not prompt:
        return ""
    
    # 1. Truncate payload size
    if len(prompt) > max_chars:
        logger.warning(f"SecuritySanitizer: Prompt length {len(prompt)} exceeded maximum {max_chars}. Truncating.")
        prompt = prompt[:max_chars]
        
    # 2. Escape HTML / strip scripts
    cleaned = re.sub(r'<script.*?>.*?</script>', '', prompt, flags=re.IGNORECASE | re.DOTALL)
    cleaned = html.escape(cleaned)
    # Revert basic safe markdown chars like quotes
    cleaned = cleaned.replace("&quot;", '"').replace("&#x27;", "'").replace("&amp;", "&")
    return cleaned.strip()

def validate_payload_size(data_bytes: bytes, max_size_mb: float = 10.0) -> bool:
    """Enforce request content payload limits."""
    max_bytes = max_size_mb * 1024 * 1024
    return len(data_bytes) <= max_bytes
