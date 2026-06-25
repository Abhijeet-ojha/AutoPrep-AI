import logging
from app.services.dataset_store import DatasetState
from app.services.analytics_engine import get_dataset_analytics
from app.services.feature_analyzer import analyze_dataset_features
from app.services.ml_advisor import get_ml_recommendations

logger = logging.getLogger(__name__)

def build_ai_context(state: DatasetState, intents: list[dict], domain_info: dict, conv_context: dict) -> dict:
    """
    Constructs a metadata-only contextual summary for the LLM.
    Uses pre-computed analytics, feature analysis diagnostic flags,
    machine learning advisor recommendations, and active chat parameters.
    """
    # 1. Get statistics & summaries
    analytics = get_dataset_analytics(state)
    summary = analytics.get("summary", {})
    columns_stats = analytics.get("columns", {})
    
    # 2. Get feature analysis diagnostic flags
    df = state.current_df
    features_info = analyze_dataset_features(df, analytics)
    
    # 3. Get ML recommendations
    ml_recs = get_ml_recommendations(analytics, features_info)
    
    # Combine everything safely
    safe_context = {
        "dataset_summary": {
            "filename": state.file_name,
            "file_size_bytes": state.file_size_bytes,
            "rows": summary.get("rows", 0),
            "columns": summary.get("columns", 0),
            "memory_usage_bytes": summary.get("memory_usage_bytes", 0),
            "duplicate_rows": summary.get("duplicate_rows", 0),
            "missing_values": summary.get("missing_values", 0),
            "missing_percentage": summary.get("missing_percentage", 0.0),
        },
        "columns_stats": columns_stats,
        "detected_domain": domain_info.get("domain", "General Tabular Dataset"),
        "domain_confidence": domain_info.get("confidence", 0.0),
        "health_score": state.metadata.get("health_score", 100),
        "raw_health_score": state.metadata.get("health_score", 100),
        "raw_health_label": state.metadata.get("health", {}).get("band", "Unknown"),
        "cleaned_health_score": state.metadata.get("cleaned_health_score", 100),
        "cleaned_health_label": state.metadata.get("cleaned_health", {}).get("band", "Excellent"),
        "cleaning_impact": state.metadata.get("cleaning_impact", {}),
        "ml_readiness_score": state.metadata.get("ml_readiness_score", 50),
        "features_analysis": features_info,
        "ml_recommendations": ml_recs,
        "detected_intents": intents,
        "conversation_context": conv_context,
        "chat_history": state.metadata.get("chat_history", [])
    }
    return safe_context
