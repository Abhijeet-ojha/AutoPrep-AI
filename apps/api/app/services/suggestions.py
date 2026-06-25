import logging
import re

logger = logging.getLogger(__name__)

def generate_suggestions(
    intents: list[str],
    domain: str,
    history: list[dict],
    current_response: str,
    metadata: dict = None
) -> list[str]:
    """
    Generate exactly 4 dynamic suggestions by computing a weighted score for
    a set of candidate questions and returning the top 4.
    Prevents repeating suggestions used in the recent conversation.
    """
    metadata = metadata or {}
    primary_intent = intents[0] if intents else "General Discussion"
    
    # 1. Gather context stats
    health_score = metadata.get("health_score", 100)
    ml_score = metadata.get("readiness", {}).get("score", 50)
    ml_task = metadata.get("readiness", {}).get("target_type", "Classification")
    raw_metrics = metadata.get("raw_metrics", {})
    missing_count = raw_metrics.get("original_missing_count", 0)
    outliers_count = raw_metrics.get("original_outlier_count", 0)
    
    # 2. Extract recent history to avoid duplicates
    # Avoid repeating questions within the last 5 user prompts or assistant answers
    recent_history = history[-10:] if history else []
    recent_texts = []
    for msg in recent_history:
        text_clean = re.sub(r'[^a-zA-Z0-9]', '', msg.get("message", "").lower())
        recent_texts.append(text_clean)
        
    # Candidate suggestions pool
    candidates = [
        # Data Quality & Health
        {
            "text": "Explain the health score breakdown",
            "weights": {"Data Quality": 5, "Cleaning": 3},
            "condition": lambda: health_score < 80
        },
        {
            "text": "Which columns need further cleaning?",
            "weights": {"Data Quality": 4, "Cleaning": 5},
            "condition": lambda: missing_count > 0 or outliers_count > 0
        },
        {
            "text": "Explain dataset quality issues",
            "weights": {"Data Quality": 5, "General Discussion": 2},
            "condition": lambda: health_score < 90
        },
        {
            "text": "Show cleaning impact and metrics",
            "weights": {"Cleaning": 5, "Data Quality": 3},
            "condition": lambda: len(metadata.get("cleaning_logs", [])) > 0
        },
        # Machine Learning
        {
            "text": f"Is this dataset ready for {ml_task.lower()}?",
            "weights": {"Model Recommendation": 5, "Feature Engineering": 3},
            "condition": lambda: ml_score < 90
        },
        {
            "text": "Recommend feature engineering steps",
            "weights": {"Feature Engineering": 5, "Model Recommendation": 3},
            "condition": lambda: ml_score < 80
        },
        {
            "text": "Which evaluation metrics should I use?",
            "weights": {"Model Recommendation": 5},
            "condition": lambda: True
        },
        {
            "text": "Should I normalize or scale the numeric features?",
            "weights": {"Model Recommendation": 4, "Feature Engineering": 3},
            "condition": lambda: True
        },
        {
            "text": "Suggest a validation and training strategy",
            "weights": {"Model Recommendation": 5},
            "condition": lambda: True
        },
        {
            "text": "Suggest a complete ML pipeline",
            "weights": {"Model Recommendation": 4, "Feature Engineering": 4},
            "condition": lambda: True
        },
        # Comparison & Domain
        {
            "text": "Compare with Titanic",
            "weights": {"Dataset Comparison": 5},
            "condition": lambda: "titanic" not in domain.lower()
        },
        {
            "text": "Compare with Iris",
            "weights": {"Dataset Comparison": 5},
            "condition": lambda: "iris" not in domain.lower()
        },
        {
            "text": "Which preprocessing steps differ?",
            "weights": {"Dataset Comparison": 4},
            "condition": lambda: True
        },
        # General & Stats
        {
            "text": "Show dataset summary statistics",
            "weights": {"Statistics": 5, "General Discussion": 3},
            "condition": lambda: True
        },
        {
            "text": "Show correlation heatmap visual",
            "weights": {"Statistics": 5, "Visualization": 5},
            "condition": lambda: True
        },
        {
            "text": "Explain dataset quality and health",
            "weights": {"General Discussion": 5},
            "condition": lambda: True
        }
    ]

    scored_candidates = []
    for cand in candidates:
        text = cand["text"]
        # Skip if similar text matches any recent history item
        text_norm = re.sub(r'[^a-zA-Z0-9]', '', text.lower())
        is_duplicate = False
        for hist_norm in recent_texts:
            # check contains or matches
            if text_norm in hist_norm or hist_norm in text_norm:
                is_duplicate = True
                break
        
        if is_duplicate:
            continue
            
        score = 0
        # 1. Intent weighting
        if primary_intent in cand["weights"]:
            score += cand["weights"][primary_intent]
            
        # 2. Heuristics weighting
        if cand["condition"]():
            score += 3
            
        # 3. Domain boost
        if "comparison" in primary_intent.lower() and "compare" in text.lower():
            score += 2
            
        scored_candidates.append((score, text))
        
    # Sort candidates by score descending
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Extract top 4
    results = [text for _, text in scored_candidates[:4]]
    
    # Fallback to make sure we always return exactly 4 suggestions
    fallbacks = [
        "Explain dataset quality and health",
        "Is this dataset ready for machine learning?",
        "What cleaning actions were applied?",
        "What model should I use?"
    ]
    for fb in fallbacks:
        if len(results) >= 4:
            break
        if fb not in results:
            results.append(fb)
            
    return results[:4]
