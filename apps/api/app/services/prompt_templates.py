"""Prompt templates for AI and Fallback copilot providers."""

INTENT_TEMPLATES = {
    "Dataset Comparison": """
Follow this format strictly:
# Dataset Comparison Overview
Provide a short introduction comparing the two datasets.

## Comparison Table
Include a Markdown table comparing dimensions, missing value counts, health score, ML readiness, etc.

## Similarities
- Bullet 1
- Bullet 2

## Differences
- Bullet 1
- Bullet 2

## ML Perspective
Provide a structured assessment of modeling implications for both datasets.

## Final Recommendation
Provide actionable recommendations.
""",
    "Cleaning": """
Follow this format strictly:
# Cleaning Recommendations
Provide a short introduction.

## Issues Found
- Bullet 1
- Bullet 2

## Recommended Cleaning
Provide a Markdown table or list of steps.

## Why These Methods
Provide reasoning.

## Expected Impact
Describe expected improvements to health score and model performance.

## Summary
Provide a concise conclusion.
""",
    "Dataset Analysis": """
Follow this format strictly:
# Dataset Analysis Report

Provide a brief introduction (1-2 sentences) about the dataset and its detected domain.

## Dataset Overview
Create a Markdown table with the following properties:
| Property | Value |
| --- | --- |
| Filename | [Filename] |
| Row Count | [Rows] |
| Column Count | [Columns] |
| File Size | [Size in Bytes] |

## Overall Health
Provide a structured assessment of the overall dataset health, explaining what the raw and cleaned health scores mean from an analytical perspective.

## Data Quality Summary
Discuss major data quality findings like missing values, duplicates, and outliers. Use a bulleted list with bold metric counts.

## Cleaning Impact
Compare the dataset before and after auto-cleaning. Use a Markdown table showing row counts, treated outliers, filled missing values, etc.

## Dataset Composition
Describe column semantic types (e.g. numeric, categorical, datetime) and their profiles (cardinality, missing percentage).

## Machine Learning Readiness
Assess the ML readiness score. Explain which ML task is recommended (e.g., Classification, Regression) and discuss potential validation strategies.

## Recommendations
Provide 3-5 actionable, numbered recommendations for further preparation or engineering.

## Final Summary
Provide a concise, professional conclusion.
""",
    "Model Recommendation": """
Follow this format strictly:
# Machine Learning Model Recommendations
Identify target variable and problem type.

## Problem Type
Indicate regression, classification, clustering, etc.

## Suggested Models
Provide a comparison table of suggested models.

## Why
Explain reasoning.

## Evaluation Metrics
Identify relevant evaluation metrics.

## Recommended Pipeline
Provide recommended training/preprocessing pipeline.
""",
    "Feature Engineering": """
Follow this format strictly:
# Feature Engineering Plan
Provide introduction.

## Candidate Features
Provide a Markdown table of candidate features.

## Reasoning
Explain the reasoning.

## Expected Benefit
Describe expected performance gains.

## Implementation Ideas
Include code snippets or suggestions.
"""
}

def format_cleaning_impact(impact: dict) -> str:
    if not impact:
        return "- No cleaning impact data available.\n"
    res = ""
    res += f"- Original Rows: {impact.get('rows_before')}, Cleaned Rows: {impact.get('rows_after')}\n"
    res += f"- Missing Values Fixed: {impact.get('missing_values_fixed', 0)}\n"
    res += f"- Duplicates Removed: {impact.get('duplicates_removed', 0)}\n"
    res += f"- Outliers Treated: {impact.get('outliers_treated', 0)}\n"
    res += f"- Columns Modified: {impact.get('columns_modified', 0)}\n"
    res += f"- Cells Modified: {impact.get('cells_modified', 0)}\n"
    return res

def format_column_schema(columns_stats: dict) -> str:
    if not columns_stats:
        return "- No column profile information available.\n"
    res = ""
    for col, info in columns_stats.items():
        res += f"- {col} (Type: {info.get('type')}, Null%: {info.get('missing_pct', 0.0):.1f}%, Cardinality: {info.get('cardinality', info.get('entropy', 0))})\n"
    return res

def build_copilot_prompt(question: str, safe_context: dict) -> str:
    intents = safe_context.get("detected_intents", [])
    primary_intent = intents[0]["intent"] if intents else "General Discussion"
    
    # Select template
    template_instruction = INTENT_TEMPLATES.get(
        primary_intent,
        "Provide a professional, structured analysis matching the user's question."
    )
    
    # Pre-calculated features & models
    features = safe_context.get("features_analysis", {}).get("feature_importances", [])
    features_str = ""
    for idx, f in enumerate(features, 1):
        features_str += f"- [{idx}] Feature: {f['feature']} (Importance: {f['importance']})\n"
        
    ml_recs = safe_context.get("ml_recommendations", {})
    models_str = ""
    for idx, rec in enumerate(ml_recs.get("suggested_algorithms", []), 1):
        models_str += f"- [{idx}] Model: {rec['model']} - {rec['explanation']}\n"

    prompt = f"""You are the AutoPrep AI Dataset Copilot, an expert data analyst and machine learning engineer.
Your role is to help the user prepare their dataset.

Here is the privacy-safe AUTHORITATIVE METADATA context of the user's dataset (Calculated Deterministically on the Backend):
- File Name: {safe_context.get('dataset_summary', {}).get('filename', 'unknown')}
- Shape: {safe_context.get('dataset_summary', {}).get('rows', 0)} rows, {safe_context.get('dataset_summary', {}).get('columns', 0)} columns
- Raw Health Score: {safe_context.get('raw_health_score', 100)}/100 ({safe_context.get('raw_health_label', 'Unknown')})
- Cleaned Health Score: {safe_context.get('cleaned_health_score', 100)}/100 ({safe_context.get('cleaned_health_label', 'Excellent')})
- ML Readiness Score: {safe_context.get('ml_readiness_score', 50)}/100
- Recommended ML Task: {ml_recs.get('task', 'Unknown')}
- Detected Dataset Domain: {safe_context.get('detected_domain', 'General Tabular Dataset')} (Confidence: {safe_context.get('domain_confidence', 0.0)})

Cleaning Impact Tracker:
{format_cleaning_impact(safe_context.get('cleaning_impact', {}))}

Active Column Schema:
{format_column_schema(safe_context.get('columns_stats', {}))}

Pre-Calculated Diagnostic Feature Importance:
{features_str if features_str else "No target column feature importances calculated."}

Pre-Calculated ML Advisor Recommendations:
{models_str if models_str else "No models suggested."}

Conversation Memory Context:
{safe_context.get('conversation_context', {})}

User Question: "{question}"

PRIMARY DETECTED INTENT: {primary_intent}
All Detected Intents: {', '.join([f"{item['intent']} ({item['confidence']})" for item in intents])}

INSTRUCTIONS FOR INTENT "{primary_intent}":
{template_instruction}

RESPONSE FORMATTING RULES:
1. Short introduction (1-2 sentences).
2. Structured headings matching the sections above.
3. Use Markdown tables when comparing or showing stats. Avoid raw lists of numbers.
4. Use bullet lists for descriptions.
5. End with actionable recommendations and a concise conclusion.
6. Avoid large walls of text. Prefer: Tables -> Bullets -> Paragraphs.

STRICT GUARDRAILS:
* You are NOT responsible for calculating statistics. Rely strictly on pre-computed values.
* If statistics or diagnostics are missing, state that they are unavailable; NEVER invent/hallucinate values.
* Never repeat information, statistics, or tables.
* Never expose implementation details.
* Never use forbidden phrases such as "the backend...", "according to the system...", "discrepancy...", "internal...", "prompt...", "implementation...". Explain findings from the user's perspective (e.g. "AutoPrep AI has identified...", "In this dataset...").
"""
    return prompt.strip()
