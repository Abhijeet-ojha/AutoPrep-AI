"""Base storage interface."""

from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def save(self, key: str, content: bytes | BinaryIO) -> str:
        """
        Save content to storage.
        
        Args:
            key: Storage key/path
            content: File content
        
        Returns:
            Storage path/URL
        """
        pass
    
    @abstractmethod
    def load(self, key: str) -> bytes:
        """
        Load content from storage.
        
        Args:
            key: Storage key/path
        
        Returns:
            File content
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete content from storage.
        
        Args:
            key: Storage key/path
        
        Returns:
            True if deleted, False otherwise
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if content exists.
        
        Args:
            key: Storage key/path
        
        Returns:
            True if exists, False otherwise
        """
        pass
