from __future__ import annotations

import io
import os
import shutil
import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from uuid import uuid4
from app.core.config import settings
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)


class DatasetState:
    def __init__(
        self,
        dataset_id: str,
        file_name: str,
        file_size_bytes: int,
        created_at: datetime,
        expires_at: datetime,
        metadata: dict[str, Any],
        file_path: str,
    ):
        self.dataset_id = dataset_id
        self.file_name = file_name
        self.file_size_bytes = file_size_bytes
        self.created_at = created_at
        self.expires_at = expires_at
        self.metadata = metadata
        self.file_path = file_path


class InMemoryDatasetStore:
    def __init__(self) -> None:
        self._storage_backend = LocalStorageBackend(
            base_path=os.path.join(settings.storage_path, "temp")
        )
        self.active_sessions: dict[str, DatasetState] = {}

    def create(
        self,
        file_name: str,
        file_size_bytes: int,
        df: pd.DataFrame,
        metadata: dict[str, Any],
    ) -> DatasetState:
        dataset_id = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=settings.session_expiration_minutes)
        
        # Ensure temporary CSV is saved
        file_path = f"{dataset_id}/cleaned.csv"
        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        self._storage_backend.save(file_path, csv_buffer.getvalue())

        state = DatasetState(
            dataset_id=dataset_id,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            metadata=metadata,
            file_path=file_path
        )
        self.active_sessions[dataset_id] = state
        return state

    def get(self, dataset_id: str) -> DatasetState:
        self.cleanup_expired()
        
        state = self.active_sessions.get(dataset_id)
        if state is None:
            raise KeyError(f"Dataset session {dataset_id} not found or has expired")
        return state

    def delete(self, dataset_id: str) -> None:
        """Evict session and physically remove temp files."""
        state = self.active_sessions.pop(dataset_id, None)
        if state:
            session_dir = os.path.join(settings.storage_path, "temp", dataset_id)
            if os.path.exists(session_dir):
                try:
                    shutil.rmtree(session_dir)
                    logger.info(f"Deleted temp directory: {session_dir}")
                except Exception as e:
                    logger.error(f"Failed to delete temp directory {session_dir}: {e}")

    def cleanup_expired(self) -> None:
        """Delete active sessions that have passed their expiration date."""
        now = datetime.utcnow()
        expired_ids = [
            sid for sid, state in self.active_sessions.items()
            if state.expires_at < now
        ]
        for sid in expired_ids:
            logger.info(f"Session {sid} has expired. Cleaning up.")
            self.delete(sid)


dataset_store = InMemoryDatasetStore()