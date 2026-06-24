import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Dataset
from app.services.dataset_store import dataset_store
from app.services.analysis_service import (
    profile_dataset,
    quality_audit,
    dataset_health_score,
    feature_engineering_suggestions,
    ml_readiness,
)

logger = logging.getLogger(__name__)


def build_ai_context(dataset_id: str, db: Session) -> dict:
    """
    Build a Gemini-safe dataset context payload without raw rows.
    Uses cached database metadata if present; otherwise, computes and caches it.
    """
    db_dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if db_dataset is None:
        raise KeyError(f"Dataset session {dataset_id} not found")

    # Check database status/expiration
    if db_dataset.status in ("EXPIRED", "DELETED") or db_dataset.expires_at < datetime.utcnow():
        raise KeyError(f"Dataset session {dataset_id} has expired or been deleted")

    # Fallback: Compute metadata if not cached in DB
    if db_dataset.profile is None or "quality_audit" not in db_dataset.profile or db_dataset.health_score is None or db_dataset.ml_readiness_score is None:
        logger.info(f"Metadata cache miss for dataset {dataset_id}. Computing...")
        try:
            state = dataset_store.get(dataset_id, db)
            df = state.current_df
            
            profile = profile_dataset(df)
            audit = quality_audit(df)
            health = dataset_health_score(audit, len(df))
            fe = feature_engineering_suggestions(df)
            ml_data = ml_readiness(df, audit, fe)
            
            health_score_val = health.get("score", 100) if isinstance(health, dict) else health
            ml_score_val = ml_data.get("readiness_score", 50) if isinstance(ml_data, dict) else 50
            
            # Cache back to database
            profile["quality_audit"] = audit
            db_dataset.profile = profile
            db_dataset.health_score = int(health_score_val)
            db_dataset.ml_readiness_score = int(ml_score_val)
            db_dataset.rows = int(df.shape[0])
            db_dataset.columns = int(df.shape[1])
            db_dataset.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_dataset)
        except Exception as e:
            logger.error(f"Failed to compute and cache metadata for dataset {dataset_id}: {e}")
            raise

    # Extract version details
    versions_summary = [
        {
            "version": v.version,
            "action": v.action,
            "details": v.details or {},
            "created_at": v.created_at.isoformat() if v.created_at else None
        }
        for v in db_dataset.versions
    ]

    # Extract cleaning logs details
    cleaning_summary = [
        {
            "version": log.version,
            "action": log.action,
            "column": log.column,
            "details": log.details or {},
            "affected_rows": log.affected_rows,
            "affected_cells": log.affected_cells
        }
        for log in db_dataset.cleaning_logs
    ]

    # Extract recent chat history (limit to last 5 messages for brevity)
    chat_summary = [
        {
            "role": msg.role,
            "message": msg.message
        }
        for msg in db_dataset.chat_history[-5:]
    ]

    # Redact string modes or text from profile columns to prevent any raw data leaks
    profile_summary = {}
    if db_dataset.profile:
        import copy
        profile_summary = copy.deepcopy(db_dataset.profile)
        if "columns" in profile_summary:
            for col_info in profile_summary["columns"]:
                if "mode" in col_info and isinstance(col_info["mode"], str):
                    col_info["mode"] = "[Redacted Stat]"

    # Form structured AI context
    return {
        "dataset_summary": {
            "dataset_id": db_dataset.id,
            "filename": db_dataset.file_name,
            "file_size_bytes": db_dataset.file_size_bytes,
            "rows": db_dataset.rows,
            "columns": db_dataset.columns,
            "created_at": db_dataset.created_at.isoformat() if db_dataset.created_at else None,
            "status": db_dataset.status
        },
        "profile_summary": profile_summary,
        "health_score": db_dataset.health_score,
        "ml_readiness_score": db_dataset.ml_readiness_score,
        "versions": versions_summary,
        "cleaning_history": cleaning_summary,
        "chat_history": chat_summary
    }
