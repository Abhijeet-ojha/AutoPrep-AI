"""Copilot orchestrator service."""

import logging
import time
from app.services.dataset_store import dataset_store
from app.services.prompt_templates import build_copilot_prompt
from app.services.gemini_sanitizer import sanitize_for_gemini
from app.services.gemini_service import get_copilot_provider, FallbackProvider, MultiProviderChain

logger = logging.getLogger(__name__)


def ask_copilot(
    dataset_id: str,
    question: str,
) -> dict:
    """
    Orchestrates the Copilot workflow:
    Retrieve In-Memory State -> Prompt Template -> Sanitize -> LLM Provider Chain -> Update Chat History -> Return.
    
    Args:
        dataset_id: Dataset identifier (session ID)
        question: User query text
        
    Returns:
        Dict of results including response, insights, health score and cleaning logs
    """
    start_time = time.time()

    # 1. Retrieve session state from in-memory store (raises KeyError if expired/missing)
    state = dataset_store.get(dataset_id)
    context = state.metadata

    # Extract components
    insights = context.get("insights", [])

    # Create a safe copy of context for prompt building and sanitization (omitting oversized Plotly visual specs)
    profile_summary = dict(context.get("profile", {}))
    profile_summary["quality_audit"] = context.get("quality", {})
    
    # Format column semantics as simple key-values for the prompt context
    raw_semantics = context.get("column_semantics", {})
    column_semantics_mapped = {}
    for col, info in raw_semantics.items():
        if isinstance(info, dict):
            column_semantics_mapped[col] = info.get("type", "Unknown")
        else:
            column_semantics_mapped[col] = str(info)

    safe_context = {
        "dataset_summary": context.get("dataset_summary", {}),
        "health_score": context.get("health_score", 100),
        "raw_health_score": context.get("health_score", 100),
        "raw_health_label": context.get("health", {}).get("band", "Unknown"),
        "cleaned_health_score": context.get("cleaned_health_score", 100),
        "cleaned_health_label": context.get("cleaned_health", {}).get("band", "Excellent"),
        "cleaning_impact": context.get("cleaning_impact", {}),
        "ml_readiness_score": context.get("ml_readiness_score", 50),
        "profile_summary": profile_summary,
        "cleaning_history": context.get("cleaning_logs", []),
        "chat_history": context.get("chat_history", []),
        "column_semantics": column_semantics_mapped
    }

    # 2. Build prompt using prompt templates
    prompt = build_copilot_prompt(question, safe_context, insights)

    # 3. Sanitize prompt, safe_context, and insights to block data leaks
    sanitize_for_gemini(prompt)
    sanitize_for_gemini(safe_context)
    sanitize_for_gemini(insights)

    # 4. Retrieve provider chain and generate response
    provider = get_copilot_provider(context, insights, question)
    provider_name = provider.__class__.__name__
    
    try:
        response_text = provider.generate(prompt)
        if isinstance(provider, MultiProviderChain):
            provider_name = provider.successful_provider
    except Exception as e:
        logger.warning(f"Active provider chain failed: {e}. Executing offline fallback...")
        fallback = FallbackProvider(safe_context, insights, question)
        provider_name = "FallbackProvider"
        response_text = fallback.generate(prompt)

    # 5. Append to Chat History in the session metadata
    chat_history = context.setdefault("chat_history", [])
    chat_history.append({"role": "user", "message": question})
    chat_history.append({"role": "assistant", "message": response_text})
    
    # Keep last 10 messages for prompt size limits
    if len(chat_history) > 10:
        context["chat_history"] = chat_history[-10:]

    # Observability Logging
    duration_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(
        "Copilot API call completed",
        extra={
            "session_id": dataset_id,
            "endpoint": f"/datasets/{dataset_id}/copilot",
            "processing_time": duration_ms,
            "event": "copilot_calls",
            "provider_used": provider_name
        }
    )

    return {
        "response": response_text,
        "insights": insights,
        "health_score": context.get("health_score", 100),
        "health_explanation": context.get("health_explanation", ""),
        "recommended_actions": context.get("cleaning_logs", [])
    }

