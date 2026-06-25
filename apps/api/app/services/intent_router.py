import logging

logger = logging.getLogger(__name__)

def route_intents(question: str) -> list[dict]:
    """
    Classify user query into multiple intents using weighted keyword mapping.
    Ties are broken using the priority order:
    Statistics -> Data Quality -> Cleaning -> Visualization -> Feature Engineering -> Model Recommendation -> Dataset Comparison -> General Discussion
    """
    q = question.lower()
    
    intent_keywords = {
        "Statistics": [("mean", 0.8), ("median", 0.8), ("mode", 0.8), ("std", 0.7), ("deviation", 0.7), ("variance", 0.7), ("skewness", 0.7), ("kurtosis", 0.7), ("min", 0.5), ("max", 0.5), ("stat", 0.6), ("summary", 0.5), ("average", 0.6), ("percentile", 0.6), ("quantiles", 0.6)],
        "Data Quality": [("quality", 0.8), ("health", 0.8), ("score", 0.6), ("issue", 0.6), ("anomaly", 0.6), ("corrupt", 0.6), ("audit", 0.6), ("missing", 0.5), ("null", 0.5), ("outlier", 0.5), ("duplicate", 0.5)],
        "Cleaning": [("clean", 0.8), ("impute", 0.8), ("preprocess", 0.7), ("handling", 0.5), ("treatment", 0.5), ("fix", 0.4), ("remove", 0.4), ("auto-clean", 0.8), ("autoclean", 0.8)],
        "Visualization": [("plot", 0.8), ("chart", 0.8), ("visualize", 0.8), ("heatmap", 0.8), ("correlation", 0.6), ("graph", 0.6), ("histogram", 0.7), ("boxplot", 0.7), ("distribution", 0.5)],
        "Feature Engineering": [("feature", 0.8), ("engineering", 0.8), ("transform", 0.6), ("create", 0.5), ("candidate", 0.5), ("encode", 0.5), ("scale", 0.5)],
        "Model Recommendation": [("model", 0.8), ("algorithm", 0.8), ("train", 0.7), ("predict", 0.7), ("xgboost", 0.6), ("regression", 0.5), ("classification", 0.5), ("pipeline", 0.5), ("evaluate", 0.5)],
        "Dataset Comparison": [("compare", 0.8), ("comparison", 0.8), ("versus", 0.6), ("vs", 0.6), ("difference", 0.4), ("similarities", 0.4), ("iris", 0.5), ("titanic", 0.5)],
        "General Discussion": [("hello", 0.5), ("hi", 0.5), ("copilot", 0.4), ("help", 0.4), ("what is", 0.3), ("how to", 0.3)]
    }
    
    scores = {}
    for intent, kws in intent_keywords.items():
        score = 0.0
        for kw, weight in kws:
            if kw in q:
                score = min(1.0, score + weight)
        if score > 0.0:
            scores[intent] = round(score, 2)
            
    priority_order = [
        "Statistics", "Data Quality", "Cleaning", "Visualization", 
        "Feature Engineering", "Model Recommendation", "Dataset Comparison", "General Discussion"
    ]
    
    def sort_key(item):
        intent, score = item
        priority_idx = priority_order.index(intent) if intent in priority_order else len(priority_order)
        return (-score, priority_idx)
        
    sorted_intents = sorted(scores.items(), key=sort_key)
    
    if not sorted_intents or sorted_intents[0][1] < 0.25:
        return [{"intent": "General Discussion", "confidence": 1.0}]
        
    return [{"intent": intent, "confidence": score} for intent, score in sorted_intents]
