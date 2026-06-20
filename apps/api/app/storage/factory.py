"""Storage backend factory."""

from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorageBackend


def get_storage_backend() -> StorageBackend:
    """
    Get configured storage backend.
    
    Returns:
        Storage backend instance
    """
    backend = settings.storage_backend.lower()
    
    if backend == "local":
        return LocalStorageBackend()
    elif backend == "s3":
        # TODO: Implement S3 backend
        raise NotImplementedError("S3 backend not yet implemented")
    elif backend == "gcs":
        # TODO: Implement GCS backend
        raise NotImplementedError("GCS backend not yet implemented")
    elif backend == "azure":
        # TODO: Implement Azure backend
        raise NotImplementedError("Azure backend not yet implemented")
    else:
        raise ValueError(f"Unknown storage backend: {backend}")


# Global instance
storage = get_storage_backend()
