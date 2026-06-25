import logging

logger = logging.getLogger(__name__)

def plan_query_mode(question: str) -> str:
    """
    Categorize user query into one of the 5 execution modes to plan backend tools
    and guide LLM prompting.
    """
    q = question.lower()
    
    # 1. COMPARISON
    comparison_kws = ["compare", "comparison", "versus", "vs", "similarities", "differences"]
    if any(kw in q for kw in comparison_kws) or any(db in q for db in ["titanic", "iris", "mnist", "california", "diabetes"]):
        logger.info(f"QueryPlanner: COMPARISON mode selected for '{question}'")
        return "COMPARISON"
        
    # 2. RECOMMENDATION
    rec_kws = [
        "recommend", "suggest", "should i", "feature engineering", "preprocessing",
        "scaling", "encoding", "ml", "pipeline", "algorithm", "model", "prepare",
        "what next", "next step", "what should i do"
    ]
    if any(kw in q for kw in rec_kws):
        logger.info(f"QueryPlanner: RECOMMENDATION mode selected for '{question}'")
        return "RECOMMENDATION"
        
    # 3. INSIGHT
    insight_kws = ["why", "explain", "reason", "interpret", "cause", "perspective", "meaning", "insight", "discrepancy"]
    if any(kw in q for kw in insight_kws):
        logger.info(f"QueryPlanner: INSIGHT mode selected for '{question}'")
        return "INSIGHT"
        
    # 4. ANALYTICS
    analytics_kws = [
        "how many rows", "how many columns", "row count", "column count", "dataset size", "shape of",
        "how many duplicate", "number of duplicate", "duplicate count",
        "how many missing", "missing count", "number of missing", "null count", "nan count",
        "how many outliers", "outlier count", "show missing", "list columns", "what columns",
        "mean of", "average of", "std of", "standard deviation of", "variance of", "median of", "mode of",
        "skewness of", "kurtosis of", "datatype of", "type of", "cardinality of", "entropy of",
        "what is the mean", "what is the average", "what is the std", "what is the median",
        "what is the max", "what is the min", "statistics of", "summary of"
    ]
    if any(kw in q for kw in analytics_kws):
        logger.info(f"QueryPlanner: ANALYTICS mode selected for '{question}'")
        return "ANALYTICS"
        
    # 5. GENERAL
    logger.info(f"QueryPlanner: GENERAL mode selected for '{question}'")
    return "GENERAL"
