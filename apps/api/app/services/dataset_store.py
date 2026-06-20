from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import uuid4

import pandas as pd


@dataclass
class DatasetVersion:
    version: int
    timestamp: datetime
    action: str
    details: dict[str, Any]
    dataframe: pd.DataFrame


@dataclass
class DatasetState:
    dataset_id: str
    file_name: str
    file_size_bytes: int
    created_at: datetime
    current_df: pd.DataFrame
    versions: list[DatasetVersion] = field(default_factory=list)


class InMemoryDatasetStore:
    def __init__(self) -> None:
        self._items: dict[str, DatasetState] = {}
        self._lock = Lock()

    def create(self, file_name: str, file_size_bytes: int, df: pd.DataFrame) -> DatasetState:
        with self._lock:
            dataset_id = str(uuid4())
            state = DatasetState(
                dataset_id=dataset_id,
                file_name=file_name,
                file_size_bytes=file_size_bytes,
                created_at=datetime.utcnow(),
                current_df=df.copy(),
            )
            state.versions.append(
                DatasetVersion(
                    version=1,
                    timestamp=datetime.utcnow(),
                    action="ingestion",
                    details={"rows": int(df.shape[0]), "columns": int(df.shape[1])},
                    dataframe=df.copy(),
                )
            )
            self._items[dataset_id] = state
            return state

    def get(self, dataset_id: str) -> DatasetState:
        state = self._items.get(dataset_id)
        if state is None:
            raise KeyError(f"Dataset {dataset_id} not found")
        return state

    def add_version(self, dataset_id: str, action: str, details: dict[str, Any], df: pd.DataFrame) -> DatasetVersion:
        with self._lock:
            state = self.get(dataset_id)
            version = len(state.versions) + 1
            entry = DatasetVersion(
                version=version,
                timestamp=datetime.utcnow(),
                action=action,
                details=details,
                dataframe=df.copy(),
            )
            state.current_df = df.copy()
            state.versions.append(entry)
            return entry

    def rollback(self, dataset_id: str, version: int) -> DatasetVersion:
        with self._lock:
            state = self.get(dataset_id)
            match = next((v for v in state.versions if v.version == version), None)
            if match is None:
                raise KeyError(f"Version {version} not found")
            state.current_df = match.dataframe.copy()
            rollback_entry = DatasetVersion(
                version=len(state.versions) + 1,
                timestamp=datetime.utcnow(),
                action="rollback",
                details={"rollback_to": version},
                dataframe=match.dataframe.copy(),
            )
            state.versions.append(rollback_entry)
            return rollback_entry


dataset_store = InMemoryDatasetStore()