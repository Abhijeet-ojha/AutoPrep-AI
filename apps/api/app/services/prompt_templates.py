"""Prompt templates for AI and Fallback copilot providers."""

def build_copilot_prompt(question: str, context: dict, insights: list[dict]) -> str:
    """
    Builds a structured prompt for the Gemini Copilot using metadata-only context and insights.
    Never exposes raw records.
    """
    from app.services.insight_engine import (
        suggest_advanced_features,
        recommend_models,
        generate_health_explanation,
        get_structured_cleaning_plan
    )
    
    dataset_summary = context.get("dataset_summary", {})
    filename = dataset_summary.get("filename", "unknown")
    rows = dataset_summary.get("rows", 0)
    cols = dataset_summary.get("columns", 0)
    raw_health_score = context.get("raw_health_score", 100)
    raw_health_label = context.get("raw_health_label", "Unknown")
    cleaned_health_score = context.get("cleaned_health_score", 100)
    cleaned_health_label = context.get("cleaned_health_label", "Excellent")
    cleaning_impact = context.get("cleaning_impact", {})
    ml_score = context.get("ml_readiness_score", 50)

    # Format cleaning impact
    cleaning_impact_str = ""
    if cleaning_impact:
        cleaning_impact_str += f"- Original Rows: {cleaning_impact.get('rows_before')}, Cleaned Rows: {cleaning_impact.get('rows_after')}\n"
        cleaning_impact_str += f"- Missing Values Fixed: {cleaning_impact.get('missing_values_fixed', 0)}\n"
        cleaning_impact_str += f"- Duplicates Removed: {cleaning_impact.get('duplicates_removed', 0)}\n"
        cleaning_impact_str += f"- Outliers Treated: {cleaning_impact.get('outliers_treated', 0)}\n"
        cleaning_impact_str += f"- Columns Modified: {cleaning_impact.get('columns_modified', 0)}\n"
        cleaning_impact_str += f"- Cells Modified: {cleaning_impact.get('cells_modified', 0)}\n"
    else:
        cleaning_impact_str = "- No cleaning impact data available.\n"
    
    profile_summary = dict(context.get("profile_summary", {}))
    profile_summary["column_semantics"] = context.get("column_semantics", {})
    
    # Pre-compute advisors deterministically
    features = suggest_advanced_features(profile_summary)
    models = recommend_models(profile_summary)
    health_explain = generate_health_explanation(context)
    cleaning_plan = get_structured_cleaning_plan(context)
    
    # Format pre-computed deterministic insights
    insights_str = ""
    for idx, ins in enumerate(insights, 1):
        insights_str += f"- [{idx}] {ins['title']}: {ins['evidence']} (Rec: {ins['recommendation']})\n"
        
    # Format cleaning logs
    cleaning_str = ""
    for log in context.get("cleaning_history", []):
        col_str = f" on column '{log.get('column')}'" if log.get('column') else ""
        cleaning_str += f"- Action: {log.get('action')}{col_str} (Method: {log.get('method')}, Reason: {log.get('reason')})\n"
        
    # Format columns schema profile
    columns_str = ""
    column_semantics = context.get("column_semantics", {})
    for info in profile_summary.get("columns", []):
        col = info.get("column")
        sem_type_str = f", Semantic Type: {column_semantics.get(col)}" if col in column_semantics else ""
        columns_str += f"- {col} (Type: {info.get('dtype')}{sem_type_str}, Null%: {info.get('missing_pct', 0.0):.1f}%, Cardinality: {info.get('cardinality')})\n"
        
    # Format structured cleaning plan
    plan_str = ""
    for idx, step in enumerate(cleaning_plan, 1):
        plan_str += f"Step {idx}: Action={step['action']}, Column={step['column']}, Method={step['method']}, Reason={step['reason']}\n"

    # Format feature suggestions
    features_str = ""
    for feat in features:
        features_str += f"- Feature: {feat['feature_name']}\n  Reason: {feat['reason']}\n  Benefit: {feat['expected_benefit']}\n  Confidence: {feat['confidence_score']:.2f}\n"

    # Format model recommendations
    model_str = f"Task Identified: {models.get('task')}\n"
    if models.get("error"):
        model_str += f"Warning: {models['error']}\n"
    else:
        for idx, rec in enumerate(models.get("recommendations", []), 1):
            model_str += f"{idx}. Model: {rec['model']}\n   Explanation: {rec['explanation']}\n"
        
    prompt = f"""You are the AutoPrep AI Dataset Copilot, an expert backend engineer, data analyst, and ML platform lead.
Your role is to help the user prepare their dataset for modeling.

Here is the privacy-safe METADATA context of the user's dataset:
- File Name: {filename}
- Shape: {rows} rows, {cols} columns
- Raw Health Score: {raw_health_score}/100 ({raw_health_label})
- Cleaned Health Score: {cleaned_health_score}/100 ({cleaned_health_label})
- ML Readiness Score: {ml_score}/100

Cleaning Impact Tracker:
{cleaning_impact_str}

Detailed Health score explanation:
{health_explain}

Structured Cleaning Plan Recommendations:
{plan_str if plan_str else "No cleaning steps required."}

Deterministic Quality Insights (pre-computed):
{insights_str if insights_str else "No quality alerts detected."}

Active Column Schema:
{columns_str if columns_str else "No column profile information available."}

Dynamic Feature Engineering Suggestions:
{features_str if features_str else "No advanced feature suggestions."}

Model Recommendation Engine Output:
{model_str}

Dataset Version & Cleaning History:
{cleaning_str if cleaning_str else "No cleaning history record."}

User Question: "{question}"

Instructions:
1. Provide a professional, concise explanation, data summary, or cleaning plan matching the user's question.
2. Rely ONLY on the metadata and insights provided above. Do not assume or request raw data rows.
3. Suggest Python/Pandas code or cleaning actions when applicable. Refer directly to the structured cleaning plans, feature suggestions, or model recommendations in your advice.
4. Keep your response direct, structured, and easy to read.
"""
    return prompt.strip()
