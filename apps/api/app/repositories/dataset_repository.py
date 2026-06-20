"""Dataset repository for database operations."""

from datetime import datetime
from typing import Any
from uuid import uuid4

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import ChatHistory, CleaningLog, Dataset, DatasetVersion, GeneratedReport
from app.storage.factory import storage


class DatasetRepository:
    """Repository for dataset persistence operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_dataset(
        self,
        file_name: str,
        file_size_bytes: int,
        df: pd.DataFrame,
        profile: dict[str, Any] | None = None
    ) -> Dataset:
        """
        Create new dataset record.
        
        Args:
            file_name: Original filename
            file_size_bytes: File size in bytes
            df: DataFrame
            profile: Optional profile data
        
        Returns:
            Created Dataset model
        """
        dataset_id = str(uuid4())
        
        # Save raw data to storage
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        file_path = storage.save(f"datasets/{dataset_id}/raw.csv", csv_bytes)
        
        # Create dataset record
        dataset = Dataset(
            id=dataset_id,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            file_path=file_path,
            rows=int(df.shape[0]),
            columns=int(df.shape[1]),
            profile=profile,
        )
        
        self.db.add(dataset)
        
        # Create initial version
        version = DatasetVersion(
            dataset_id=dataset_id,
            version=1,
            action="ingestion",
            details={"rows": int(df.shape[0]), "columns": int(df.shape[1])},
            file_path=file_path,
            rows=int(df.shape[0]),
            columns=int(df.shape[1]),
        )
        
        self.db.add(version)
        self.db.commit()
        self.db.refresh(dataset)
        
        return dataset

    
    def get_dataset(self, dataset_id: str) -> Dataset | None:
        """Get dataset by ID."""
        return self.db.query(Dataset).filter(Dataset.id == dataset_id).first()
    
    def get_dataset_dataframe(self, dataset: Dataset) -> pd.DataFrame:
        """Load DataFrame from storage."""
        if not dataset.file_path:
            raise ValueError("Dataset has no file path")
        
        csv_bytes = storage.load(dataset.file_path)
        import io
        return pd.read_csv(io.BytesIO(csv_bytes))
    
    def update_dataset_profile(self, dataset_id: str, profile: dict[str, Any]):
        """Update dataset profile."""
        dataset = self.get_dataset(dataset_id)
        if dataset:
            dataset.profile = profile
            dataset.rows = profile['summary']['rows']
            dataset.columns = profile['summary']['columns']
            self.db.commit()
    
    def update_health_score(self, dataset_id: str, health_score: int):
        """Update dataset health score."""
        dataset = self.get_dataset(dataset_id)
        if dataset:
            dataset.health_score = health_score
            self.db.commit()
    
    def update_ml_readiness_score(self, dataset_id: str, ml_readiness_score: int):
        """Update ML readiness score."""
        dataset = self.get_dataset(dataset_id)
        if dataset:
            dataset.ml_readiness_score = ml_readiness_score
            self.db.commit()
    
    def add_version(
        self,
        dataset_id: str,
        action: str,
        details: dict[str, Any],
        df: pd.DataFrame
    ) -> DatasetVersion:
        """
        Add new version to dataset.
        
        Args:
            dataset_id: Dataset ID
            action: Action performed
            details: Action details
            df: Updated DataFrame
        
        Returns:
            Created DatasetVersion
        """
        # Get current version count
        current_version = self.db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id
        ).count()
        
        new_version = current_version + 1
        
        # Save versioned data
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        file_path = storage.save(f"datasets/{dataset_id}/v{new_version}.csv", csv_bytes)
        
        # Create version record
        version = DatasetVersion(
            dataset_id=dataset_id,
            version=new_version,
            action=action,
            details=details,
            file_path=file_path,
            rows=int(df.shape[0]),
            columns=int(df.shape[1]),
        )
        
        self.db.add(version)
        
        # Update dataset file path
        dataset = self.get_dataset(dataset_id)
        if dataset:
            dataset.file_path = file_path
            dataset.rows = int(df.shape[0])
            dataset.columns = int(df.shape[1])
        
        self.db.commit()
        self.db.refresh(version)
        
        return version
    
    def get_versions(self, dataset_id: str) -> list[DatasetVersion]:
        """Get all versions for a dataset."""
        return self.db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id
        ).order_by(DatasetVersion.version).all()
    
    def rollback_to_version(self, dataset_id: str, version: int) -> DatasetVersion:
        """Rollback dataset to a specific version."""
        # Find target version
        target_version = self.db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version == version
        ).first()
        
        if not target_version:
            raise ValueError(f"Version {version} not found")
        
        # Load versioned data
        df = pd.read_csv(storage.load(target_version.file_path))
        
        # Create rollback version
        return self.add_version(
            dataset_id=dataset_id,
            action="rollback",
            details={"rollback_to": version},
            df=df
        )
    
    def add_cleaning_log(
        self,
        dataset_id: str,
        version: int,
        action: str,
        column: str | None,
        details: dict[str, Any],
        affected_rows: int = 0,
        affected_cells: int = 0
    ) -> CleaningLog:
        """Add cleaning log entry."""
        log = CleaningLog(
            dataset_id=dataset_id,
            version=version,
            action=action,
            column=column,
            details=details,
            affected_rows=affected_rows,
            affected_cells=affected_cells,
        )
        
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        
        return log
    
    def get_cleaning_logs(self, dataset_id: str) -> list[CleaningLog]:
        """Get all cleaning logs for a dataset."""
        return self.db.query(CleaningLog).filter(
            CleaningLog.dataset_id == dataset_id
        ).order_by(CleaningLog.created_at).all()
    
    def save_chat_message(
        self,
        dataset_id: str,
        role: str,
        message: str,
        context_snapshot: dict[str, Any] | None = None
    ) -> ChatHistory:
        """Save chat message to history."""
        chat = ChatHistory(
            dataset_id=dataset_id,
            role=role,
            message=message,
            context_snapshot=context_snapshot,
        )
        
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        
        return chat
    
    def get_chat_history(self, dataset_id: str, limit: int = 50) -> list[ChatHistory]:
        """Get chat history for a dataset."""
        return self.db.query(ChatHistory).filter(
            ChatHistory.dataset_id == dataset_id
        ).order_by(ChatHistory.created_at.desc()).limit(limit).all()
    
    def save_report(
        self,
        dataset_id: str,
        report_type: str,
        file_content: bytes,
        summary: str | None = None
    ) -> GeneratedReport:
        """Save generated report."""
        # Save report to storage
        file_path = storage.save(
            f"reports/{dataset_id}/{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{report_type}",
            file_content
        )
        
        report = GeneratedReport(
            dataset_id=dataset_id,
            report_type=report_type,
            file_path=file_path,
            file_size_bytes=len(file_content),
            summary=summary,
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def get_reports(self, dataset_id: str) -> list[GeneratedReport]:
        """Get all reports for a dataset."""
        return self.db.query(GeneratedReport).filter(
            GeneratedReport.dataset_id == dataset_id
        ).order_by(GeneratedReport.created_at.desc()).all()
