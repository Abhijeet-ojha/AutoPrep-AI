import logging

logger = logging.getLogger(__name__)


def generate_insights(context: dict, db = None) -> list[dict]:
    """
    Generate deterministic rule-based insights from dataset context.
    """
    logger.info("Generating insights deterministically.")
    insights = []
    
    # 2. Extract column metadata from profile summary
    columns = context.get("profile_summary", {}).get("columns", [])
    rows = context.get("dataset_summary", {}).get("rows", 1) or 1
    
    # Rule A: Missing Values check
    for info in columns:
        col = info.get("column")
        null_count = info.get("missing_count", 0)
        null_pct = info.get("missing_pct", 0.0)
        if null_pct > 5.0:  # profile_dataset missing_pct is out of 100
            insights.append({
                "title": f"High Missing Values in '{col}'",
                "evidence": f"Column '{col}' has {null_count} missing values ({null_pct:.1f}% of total).",
                "confidence": 1.0,
                "recommendation": f"Apply imputation to fill nulls in '{col}' or drop it if it is non-essential."
            })

    # Rule B: Identifier columns check
    for info in columns:
        col = info.get("column")
        card = info.get("cardinality", 0)
        role = info.get("role", "")
        unique_values = info.get("unique_values", 0)
        if card == 1.0 or unique_values == rows or role == "identifier" or col.lower() in ("id", "uuid", "key"):
            insights.append({
                "title": f"Identifier Candidate '{col}' Detected",
                "evidence": f"Column '{col}' contains unique identifiers/indexes (unique values: {unique_values}/{rows}).",
                "confidence": 0.95,
                "recommendation": f"Exclude '{col}' from machine learning feature lists to prevent overfitting."
            })

    # Rule C: Skewness check
    for info in columns:
        col = info.get("column")
        skew = info.get("skewness")
        if skew is not None and abs(skew) > 1.5:
            direction = "right-skewed" if skew > 0 else "left-skewed"
            insights.append({
                "title": f"Highly Skewed Column '{col}'",
                "evidence": f"Column '{col}' is highly {direction} with a skewness of {skew:.2f}.",
                "confidence": 0.9,
                "recommendation": f"Consider applying a log, square root, or Box-Cox transformation to normalise '{col}'."
            })

    # Rule D: ML Readiness evaluation
    ml_score = context.get("ml_readiness_score", 50) or 50
    if ml_score >= 80:
        insights.append({
            "title": "Dataset Ready for Machine Learning",
            "evidence": f"Overall ML readiness score is high at {ml_score}/100.",
            "confidence": 0.85,
            "recommendation": "You can directly proceed to train baseline models or generate feature engineering scripts."
        })
    else:
        insights.append({
            "title": "Action Needed for ML Readiness",
            "evidence": f"ML readiness score is moderate to low at {ml_score}/100 due to quality impediments.",
            "confidence": 0.85,
            "recommendation": "Review recommended cleaning actions to resolve missing cells, outliers, or type mismatches first."
        })

    return insights


def suggest_advanced_features(profile_summary: dict) -> list[dict]:
    """
    Suggest features dynamically based on detected column names to avoid hardcoding.
    """
    suggestions = []
    
    # High Cardinality Categorical recommendations
    column_semantics = profile_summary.get("column_semantics", {})
    for col_name, sem_type in column_semantics.items():
        if sem_type == "High Cardinality Categorical":
            suggestions.append({
                "feature_name": f"{col_name}_Encoded",
                "reason": f"Column '{col_name}' is classified as High Cardinality Categorical.",
                "expected_benefit": "Using Hash Encoding, Target Encoding, or Embeddings will reduce dimensionality while preserving feature representation for model training.",
                "confidence_score": 0.92
            })

    columns = profile_summary.get("columns", [])
    col_names = [col.get("column", "") for col in columns]
    col_names_lower = [name.lower() for name in col_names]

    has_age = any("age" in name for name in col_names_lower)
    has_tenure = any(any(k in name for k in ("tenure", "months", "days", "joined")) for name in col_names_lower)
    
    # Financial metrics
    has_revenue = any(any(k in name for k in ("price", "amount", "revenue", "spending", "sales")) for name in col_names_lower)
    # Order count
    has_order = any(any(k in name for k in ("order", "quantity", "count")) for name in col_names_lower)

    if has_age:
        # Find exact age column name
        age_col = next((name for name in col_names if "age" in name.lower()), "Age")
        suggestions.append({
            "feature_name": f"{age_col}_Group",
            "reason": f"Column '{age_col}' has high granularity. Grouping ages into categorical bins reduces noise.",
            "expected_benefit": "Enables models to capture non-linear relationships (e.g. customer lifecycle stages) more effectively.",
            "confidence_score": 0.85
        })

    if has_revenue and has_order:
        rev_col = next((name for name in col_names if any(k in name.lower() for k in ("price", "amount", "revenue", "spending", "sales"))), "Revenue")
        order_col = next((name for name in col_names if any(k in name.lower() for k in ("order", "quantity", "count"))), "Orders")
        suggestions.append({
            "feature_name": f"{rev_col}_Per_{order_col}",
            "reason": f"Combine financial columns ('{rev_col}') and frequency ('{order_col}') to calculate transactional efficiency.",
            "expected_benefit": "Captures average transactional basket size and purchase intensity directly.",
            "confidence_score": 0.90
        })

    if has_tenure:
        tenure_col = next((name for name in col_names if any(k in name.lower() for k in ("tenure", "months", "days", "joined"))), "Tenure")
        suggestions.append({
            "feature_name": f"{tenure_col}_Band",
            "reason": f"Transform duration variable '{tenure_col}' into cohort categories.",
            "expected_benefit": "Improves model ability to categorize user loyalty stages and evaluate churn risk cohorts.",
            "confidence_score": 0.85
        })

    # Fallback to standard scaling suggestions for numeric columns if nothing else applies
    if not suggestions:
        num_cols = [col.get("column") for col in columns if col.get("mean") is not None]
        if num_cols:
            suggestions.append({
                "feature_name": f"{num_cols[0]}_Scaled",
                "reason": f"Scale numeric values in column '{num_cols[0]}' to a standard normal distribution.",
                "expected_benefit": "Prevents numerical scaling disparities and stabilizes gradient-descent optimizers.",
                "confidence_score": 0.75
            })

    return suggestions


def recommend_models(profile_summary: dict) -> dict:
    """
    Recommend ML models deterministically based on target column detection.
    Does not guess target task if no target column is identified.
    """
    columns = profile_summary.get("columns", [])
    target_col = None
    for col_info in columns:
        col_name = col_info.get("column", "").lower()
        if any(k in col_name for k in ("target", "label", "class", "outcome", "purchased", "clicked")) or col_name == "y":
            target_col = col_info
            break

    if not target_col:
        return {
            "task": "Unknown",
            "recommendations": [],
            "error": "Unable to determine target variable. Please specify target column."
        }

    unique_vals = target_col.get("unique_values", 0)
    dtype = target_col.get("dtype", "").lower()
    target_name = target_col.get("column", "")

    # Categorical classification if object, bool or low cardinality
    is_categorical = "object" in dtype or "str" in dtype or "bool" in dtype or unique_vals <= 10

    if is_categorical:
        return {
            "task": "Supervised (Classification)",
            "target_column": target_name,
            "recommendations": [
                {
                    "model": "XGBoost",
                    "explanation": "High-performance gradient boosted decision trees for non-linear structured classification."
                },
                {
                    "model": "Random Forest",
                    "explanation": "Robust ensemble method that reduces variance and handles categorical feature splits well."
                },
                {
                    "model": "Logistic Regression",
                    "explanation": "Simple, highly interpretable baseline linear model for binary or multiclass outcomes."
                }
            ]
        }
    else:
        return {
            "task": "Supervised (Regression)",
            "target_column": target_name,
            "recommendations": [
                {
                    "model": "XGBoost Regressor",
                    "explanation": "Gradient boosting that excels at predicting continuous numeric variables with complex features."
                },
                {
                    "model": "Random Forest Regressor",
                    "explanation": "Ensemble decision tree regressor robust to numerical outliers and noise."
                },
                {
                    "model": "Ridge/Linear Regression",
                    "explanation": "Fast baseline regression model that quantifies direct linear dependencies."
                }
            ]
        }


def generate_health_explanation(context: dict) -> str:
    """
    Generate an explainable health score summary based on profile and quality audit metadata.
    """
    health_score = context.get("health_score", 100)
    profile_summary = context.get("profile_summary", {})
    audit = profile_summary.get("quality_audit", {})

    total_rows = context.get("dataset_summary", {}).get("rows", 1) or 1
    total_cols = context.get("dataset_summary", {}).get("columns", 1) or 1

    # Cells missing percent
    missing_cells = 0
    for col_info in profile_summary.get("columns", []):
        missing_cells += col_info.get("missing_count", 0)
    total_cells = total_rows * total_cols
    missing_pct = (missing_cells / total_cells) * 100 if total_cells > 0 else 0.0

    # Duplicate records percent
    duplicate_rows = audit.get("duplicates", {}).get("duplicate_rows", 0) or 0
    duplicate_pct = (duplicate_rows / total_rows) * 100

    # High cardinality categorical columns
    high_card_cols = 0
    for col_info in profile_summary.get("columns", []):
        dtype = col_info.get("dtype", "")
        unique = col_info.get("unique_values", 0)
        if "object" in dtype or "str" in dtype:
            if unique > 15:
                high_card_cols += 1

    primary_issues = []
    if missing_pct > 1.0:
        primary_issues.append(f"{missing_pct:.1f}% missing values")
    if duplicate_pct > 1.0:
        primary_issues.append(f"{duplicate_pct:.1f}% duplicate records")
    if high_card_cols > 0:
        primary_issues.append(f"{high_card_cols} high-cardinality categorical column{'s' if high_card_cols > 1 else ''}")

    outliers_count = sum(audit.get("outliers", {}).get("iqr", {}).values()) if audit.get("outliers") else 0
    if outliers_count > 0:
        primary_issues.append(f"{outliers_count} outlier values detected")

    format_issues = len(audit.get("inconsistent_formatting", [])) if audit.get("inconsistent_formatting") else 0
    if format_issues > 0:
        primary_issues.append(f"{format_issues} column{'s' if format_issues > 1 else ''} with inconsistent formatting")

    if not primary_issues:
        primary_issues.append("No primary quality issues detected.")

    if health_score >= 90:
        effort = "Low"
    elif health_score >= 70:
        effort = "Medium"
    else:
        effort = "High"

    issues_str = "\n".join(f"- {issue}" for issue in primary_issues)
    return f"Health Score = {health_score}\n\nPrimary Issues:\n{issues_str}\n\nEstimated Cleaning Effort:\n{effort}"


def get_structured_cleaning_plan(context: dict) -> list[dict]:
    """
    Compile a structured cleaning plan containing actions mapped directly to the cleaning engine.
    """
    plan = []
    profile_summary = context.get("profile_summary", {})
    audit = profile_summary.get("quality_audit", {})
    columns = profile_summary.get("columns", [])

    # 1. Duplicates check
    duplicate_rows = audit.get("duplicates", {}).get("duplicate_rows", 0) or 0
    if duplicate_rows > 0:
        plan.append({
            "action": "remove_duplicates",
            "column": None,
            "method": "drop_exact_duplicates",
            "reason": f"Dataset contains {duplicate_rows} exact duplicate rows."
        })

    # 2. Missing values check
    for col_info in columns:
        col_name = col_info.get("column", "")
        missing_count = col_info.get("missing_count", 0)
        missing_pct = col_info.get("missing_pct", 0.0)
        if missing_count > 0:
            dtype = col_info.get("dtype", "").lower()
            mean_val = col_info.get("mean")
            skew = col_info.get("skewness")
            
            if mean_val is not None:
                # Numerical column
                if skew is not None and abs(skew) > 1.5:
                    method = "median"
                else:
                    method = "mean"
            else:
                method = "mode"

            plan.append({
                "action": "fill_missing",
                "column": col_name,
                "method": method,
                "reason": f"Column '{col_name}' has {missing_count} missing cells ({missing_pct:.1f}% missing)."
            })

    # 3. Outliers check
    outlier_iqr = audit.get("outliers", {}).get("iqr", {}) if audit.get("outliers") else {}
    for col_name, outlier_count in outlier_iqr.items():
        if outlier_count > 0:
            plan.append({
                "action": "handle_outliers",
                "column": col_name,
                "method": "clip_iqr_bounds",
                "reason": f"Column '{col_name}' has {outlier_count} IQR outliers."
            })

    # 4. Inconsistent formatting check
    formatting = audit.get("inconsistent_formatting", [])
    for format_issue in formatting:
        col_name = format_issue.get("column", "")
        plan.append({
            "action": "fix_formatting",
            "column": col_name,
            "method": "strip_whitespace",
            "reason": f"Column '{col_name}' has casing or whitespace formatting inconsistencies."
        })

    # 5. Convert datetime strings check
    for col_info in columns:
        col_name = col_info.get("column", "")
        dtype = col_info.get("dtype", "").lower()
        if "date" in col_name.lower() or "time" in col_name.lower():
            if "object" in dtype or "str" in dtype:
                plan.append({
                    "action": "convert_dtypes",
                    "column": col_name,
                    "method": "datetime_parse",
                    "reason": f"Column '{col_name}' is temporal but stored as string text."
                })

    return plan
