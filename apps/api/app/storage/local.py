"""Local filesystem storage backend."""

import os
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage implementation."""
    
    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path or settings.storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_full_path(self, key: str) -> Path:
        """Get full filesystem path for key."""
        # Prevent directory traversal
        if ".." in key:
            raise ValueError(f"Directory traversal detected in key: {key}")
            
        safe_key = key.lstrip("/")
        full_path = self.base_path / safe_key
        
        # Ensure path is within base_path
        try:
            full_path.resolve().relative_to(self.base_path.resolve())
        except ValueError:
            raise ValueError(f"Invalid key: {key}")
        
        return full_path
    
    def save(self, key: str, content: bytes | BinaryIO) -> str:
        """Save content to local filesystem."""
        path = self._get_full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            with open(path, "wb") as f:
                f.write(content.read())
        
        return str(path.relative_to(self.base_path).as_posix())
    
    def load(self, key: str) -> bytes:
        """Load content from local filesystem."""
        path = self._get_full_path(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")
        return path.read_bytes()
    
    def delete(self, key: str) -> bool:
        """Delete content from local filesystem."""
        path = self._get_full_path(key)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def exists(self, key: str) -> bool:
        """Check if content exists in local filesystem."""
        path = self._get_full_path(key)
        return path.exists()
