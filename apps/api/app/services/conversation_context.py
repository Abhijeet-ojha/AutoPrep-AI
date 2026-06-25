import re
import logging

logger = logging.getLogger(__name__)

def resolve_contextual_question(question: str, context_dict: dict) -> str:
    """
    Resolve implicit pronoun, follow-up, and contextual queries using session memory.
    Supports queries like "What about Titanic?", "Show the same for Age", "Explain the second graph".
    """
    q = question.strip().lower()
    
    # 1. Dataset Comparison Follow-up
    # Patterns: "what about Titanic?", "how about Titanic?", "and Titanic?", "Titanic?"
    db_match = re.search(r'^(what about|how about|and|try|compare with)\s+([a-zA-Z0-9_\-\s]+)\??$', q)
    if db_match:
        target = db_match.group(2).strip().title()
        known_benchmarks = ["titanic", "iris", "mnist", "housing", "california", "diabetes"]
        if target.lower() in known_benchmarks or context_dict.get("previous_comparison_dataset"):
            context_dict["previous_comparison_dataset"] = target
            context_dict["previous_intent"] = "Comparison"
            logger.info(f"ContextResolver: Resolved comparison follow-up for target '{target}'")
            return f"Compare the uploaded dataset with {target}"
            
    # 2. "Show the same for <Column>" or "What about <Column>?"
    # Patterns: "show the same for Age", "how about Age?", "what about Age?"
    col_match = re.search(r'^(show the same for|what about|how about|and)\s+([a-zA-Z0-9_\-\s]+)\??$', q)
    if col_match:
        orig_stripped = question.strip()
        span_start, span_end = col_match.span(2)
        col_name = orig_stripped[span_start:span_end].strip()
        last_stat = context_dict.get("last_statistic_metric")
        if last_stat:
            logger.info(f"ContextResolver: Resolved stats follow-up for column '{col_name}' and metric '{last_stat}'")
            return f"What is the {last_stat} of {col_name}?"
        elif context_dict.get("previous_intent") == "Statistics":
            logger.info(f"ContextResolver: Resolved generic stats follow-up for column '{col_name}'")
            return f"Show statistics and summary for column {col_name}"
            
    # 3. Chart/Graph Follow-up
    # Patterns: "explain the second graph", "explain the first chart", "explain the correlation heatmap"
    chart_match = re.search(r'^(explain|describe|tell me about)\s+(the\s+)?(first|second|third|fourth|1st|2nd|3rd|4th|correlation|boxplot|histogram|scatter|bar)\s+(graph|chart|plot|heatmap)?\??$', q)
    if chart_match:
        chart_type = chart_match.group(3).strip()
        logger.info(f"ContextResolver: Resolved chart explanation follow-up for chart '{chart_type}'")
        return f"Explain the {chart_type} chart and its data distributions/relationships"

    return question

def update_conversation_context(question: str, resolved_question: str, intents: list[str], context_dict: dict) -> None:
    """
    Parse the query and update session memory with the active intent, discussed columns,
    models, metrics, or charts.
    """
    q = resolved_question.lower()
    
    # Update intent
    if intents:
        context_dict["previous_intent"] = intents[0]
        
    # Extract statistics metrics discussed
    stat_metrics = ["mean", "median", "mode", "standard deviation", "variance", "skewness", "kurtosis", "min", "max", "quartiles", "iqr"]
    for metric in stat_metrics:
        if metric in q:
            context_dict["last_statistic_metric"] = metric
            break
            
    # Extract comparison target
    for db in ["titanic", "iris", "mnist", "california", "diabetes"]:
        if db in q:
            context_dict["previous_comparison_dataset"] = db.title()
            break
            
    # Extract model names
    models = ["xgboost", "random forest", "logistic regression", "linear regression", "ridge", "lasso", "elasticnet", "svm", "k-means"]
    for m in models:
        if m in q:
            context_dict["previous_recommended_model"] = m.title()
            break
            
    # Extract discussed charts
    charts = ["correlation", "boxplot", "histogram", "scatter", "bar", "heatmap", "plot", "graph"]
    for c in charts:
        if c in q:
            discussed = context_dict.setdefault("discussed_charts", [])
            if c not in discussed:
                discussed.append(c)
            break
