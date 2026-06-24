"""Metrics aggregation service for AutoPrep AI."""

import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import Dataset, CleaningLog, SystemMetric

logger = logging.getLogger(__name__)


def track_copilot_call(provider_name: str, db: Session) -> None:
    """
    Record a copilot call by updating the persistent JSON-based SystemMetric record.
    
    Args:
        provider_name: Class name of the provider used (e.g. GeminiProvider / FallbackProvider)
        db: SQLAlchemy database session
    """
    try:
        key = "gemini_calls" if "Gemini" in provider_name else "fallback_calls"
        metric = db.query(SystemMetric).filter(SystemMetric.key == key).first()
        if not metric:
            metric = SystemMetric(key=key, value={"count": 1})
            db.add(metric)
        else:
            val = dict(metric.value or {})
            val["count"] = val.get("count", 0) + 1
            metric.value = val
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to track copilot call metrics: {e}")


def get_system_metrics(db: Session) -> dict:
    """
    Retrieve aggregated, lightweight system metrics dynamically.
    
    Args:
        db: SQLAlchemy database session
        
    Returns:
        Dict of computed system metrics
    """
    try:
        total_datasets = db.query(Dataset).count()
        
        avg_health = db.query(func.avg(Dataset.health_score)).filter(Dataset.health_score != None).scalar()
        avg_health_val = float(round(avg_health, 2)) if avg_health is not None else 0.0
        
        # Determine the most common cleaning action
        action_counts = db.query(CleaningLog.action, func.count(CleaningLog.action)).group_by(CleaningLog.action).all()
        most_common = "None"
        if action_counts:
            # Sort tuples by count (second item) descending
            action_counts.sort(key=lambda x: x[1], reverse=True)
            most_common = action_counts[0][0]
            
        # Get Gemini vs Fallback counts from SystemMetric JSON value
        gemini_metric = db.query(SystemMetric).filter(SystemMetric.key == "gemini_calls").first()
        fallback_metric = db.query(SystemMetric).filter(SystemMetric.key == "fallback_calls").first()
        
        gemini_count = gemini_metric.value.get("count", 0) if gemini_metric and isinstance(gemini_metric.value, dict) else 0
        fallback_count = fallback_metric.value.get("count", 0) if fallback_metric and isinstance(fallback_metric.value, dict) else 0
        
        return {
            "total_datasets_processed": total_datasets,
            "average_health_score": avg_health_val,
            "most_common_cleaning_action": most_common,
            "gemini_vs_fallback_usage": {
                "gemini": gemini_count,
                "fallback": fallback_count
            }
        }
    except Exception as e:
        logger.error(f"Failed to compile system metrics: {e}")
        return {
            "total_datasets_processed": 0,
            "average_health_score": 0.0,
            "most_common_cleaning_action": "None",
            "gemini_vs_fallback_usage": {
                "gemini": 0,
                "fallback": 0
            }
        }
