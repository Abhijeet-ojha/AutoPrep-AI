"""Database models for persistent storage."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Dataset(Base):
    """Dataset metadata and current state."""
    
    __tablename__ = "datasets"
    
    id = Column(String, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_path = Column(String, nullable=True)  # Path in storage backend
    
    # Metadata
    rows = Column(Integer, nullable=True)
    columns = Column(Integer, nullable=True)
    profile = Column(JSON, nullable=True)
    health_score = Column(Integer, nullable=True)
    ml_readiness_score = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    versions = relationship("DatasetVersion", back_populates="dataset", cascade="all, delete-orphan")
    cleaning_logs = relationship("CleaningLog", back_populates="dataset", cascade="all, delete-orphan")
    reports = relationship("GeneratedReport", back_populates="dataset", cascade="all, delete-orphan")
    chat_history = relationship("ChatHistory", back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(Base):
    """Dataset version snapshots."""
    
    __tablename__ = "dataset_versions"

    
    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    
    # Version metadata
    action = Column(String, nullable=False)  # ingestion, cleaning, rollback
    details = Column(JSON, nullable=True)
    file_path = Column(String, nullable=True)  # Path to versioned data file
    
    # Stats snapshot
    rows = Column(Integer, nullable=True)
    columns = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    dataset = relationship("Dataset", back_populates="versions")


class CleaningLog(Base):
    """Log of cleaning operations performed."""
    
    __tablename__ = "cleaning_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    
    # Operation details
    action = Column(String, nullable=False)
    column = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    
    # Results
    affected_rows = Column(Integer, nullable=True)
    affected_cells = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    dataset = relationship("Dataset", back_populates="cleaning_logs")


class GeneratedReport(Base):
    """Generated reports (HTML, PDF)."""
    
    __tablename__ = "generated_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    
    # Report metadata
    report_type = Column(String, nullable=False)  # html, pdf
    file_path = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    
    # Content summary
    summary = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    dataset = relationship("Dataset", back_populates="reports")


class ChatHistory(Base):
    """Chat conversation history."""
    
    __tablename__ = "chat_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    
    # Message content
    role = Column(String, nullable=False)  # user, assistant
    message = Column(Text, nullable=False)
    
    # Context snapshot
    context_snapshot = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    dataset = relationship("Dataset", back_populates="chat_history")
