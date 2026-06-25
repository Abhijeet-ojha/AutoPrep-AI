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
    Retrieve In-Memory State -> Plan Query -> Route Intent -> local Analytics/LLM -> Update Chat History -> Return.
    """
    from app.services.analytics_engine import get_dataset_analytics, evaluate_analytics_query
    from app.services.dataset_domain_detector import detect_dataset_domain
    from app.services.intent_router import route_intents
    from app.services.conversation_context import resolve_contextual_question, update_conversation_context
    from app.services.suggestions import generate_suggestions
    from app.services.query_planner import plan_query_mode
    from app.services.ai_context_builder import build_ai_context
    from app.services.prompt_templates import build_copilot_prompt
    from app.services.gemini_sanitizer import sanitize_for_gemini
    from app.services.gemini_service import get_copilot_provider, FallbackProvider

    start_time = time.time()

    # 1. Retrieve session state from store
    state = dataset_store.get(dataset_id)
    context = state.metadata
    insights = context.get("insights", [])

    # 2. Domain & Context initialization
    conversation_context = context.setdefault("conversation_context", {})
    profile = context.get("profile", {})
    domain_info = detect_dataset_domain(profile)
    
    # 3. Contextual query resolution
    resolved_question = resolve_contextual_question(question, conversation_context)
    
    # 4. Mode planning & Intent routing
    mode = plan_query_mode(resolved_question)
    detected_intents = route_intents(resolved_question)
    intents_list = [item["intent"] for item in detected_intents]
    
    provider_name = "AnalyticsEngine"
    if mode == "ANALYTICS":
        analytics = get_dataset_analytics(state)
        df = state.current_df
        response_text = evaluate_analytics_query(resolved_question, df, analytics)
    else:
        # Build contextual safe builder
        safe_context = build_ai_context(state, detected_intents, domain_info, conversation_context)
        prompt = build_copilot_prompt(resolved_question, safe_context)

        # Sanitize prompt
        sanitize_for_gemini(prompt)

        # Retrieve provider chain and generate response
        provider = get_copilot_provider(context, insights, resolved_question)
        provider_name = provider.__class__.__name__
        
        try:
            response_text = provider.generate(prompt)
        except Exception as e:
            logger.warning(f"Active provider chain failed: {e}. Executing offline fallback...")
            fallback = FallbackProvider(safe_context, insights, resolved_question)
            provider_name = "FallbackProvider"
            response_text = fallback.generate(prompt)

    # 5. Append to Chat History
    chat_history = context.setdefault("chat_history", [])
    chat_history.append({"role": "user", "message": question})
    chat_history.append({"role": "assistant", "message": response_text})
    if len(chat_history) > 10:
        context["chat_history"] = chat_history[-10:]
        
    # 6. Update context memory
    update_conversation_context(question, resolved_question, intents_list, conversation_context)

    # Observability Logging
    duration_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(
        "Copilot API call completed",
        extra={
            "session_id": dataset_id,
            "endpoint": f"/datasets/{dataset_id}/copilot",
            "processing_time": duration_ms,
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

