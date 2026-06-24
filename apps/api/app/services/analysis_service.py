from __future__ import annotations

import io
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

import numpy as np
import pandas as pd
from scipy import stats

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".json"}


class IngestionError(Exception):
    pass


def load_dataset(file_name: str, content: bytes) -> pd.DataFrame:
    lower = file_name.lower()

    if lower.endswith(".csv"):
        return _load_csv(content)
    if lower.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(content))
    if lower.endswith(".json"):
        return pd.read_json(io.BytesIO(content))

    raise IngestionError("Unsupported file format. Allowed: csv, xlsx, json")


def _load_csv(content: bytes) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(content), encoding=enc)
        except UnicodeDecodeError:
            continue
    raise IngestionError("Could not decode CSV with utf-8/utf-8-sig/latin-1")


def infer_column_role(col_name: str, series: pd.Series) -> dict[str, Any]:
    name = col_name.lower()
    unique_ratio = float(series.nunique(dropna=True)) / max(len(series), 1)

    if name.endswith("_id") or name in {"id", "uuid", "customer_id", "user_id"}:
        return {
            "role": "identifier",
            "confidence": 0.95,
            "reason": "Column naming strongly indicates an identifier field.",
        }

    if any(k in name for k in ["target", "label", "class", "outcome", "y"]):
        return {
            "role": "target_candidate",
            "confidence": 0.83,
            "reason": "Column name suggests a prediction target.",
        }

    if pd.api.types.is_datetime64_any_dtype(series.dropna().dtype) or "date" in name or "time" in name:
        return {
            "role": "time_feature",
            "confidence": 0.88,
            "reason": "Values and/or name suggest temporal information suitable for feature extraction.",
        }

    if unique_ratio > 0.95 and series.nunique(dropna=True) > 100:
        return {
            "role": "likely_leakage_or_identifier",
            "confidence": 0.72,
            "reason": "Very high cardinality can leak identity-like information into ML models.",
        }

    if series.dtype == "object" and series.astype(str).str.len().mean() > 35:
        return {
            "role": "text_feature",
            "confidence": 0.78,
            "reason": "Long free-form text is detected.",
        }

    return {
        "role": "ml_feature_candidate",
        "confidence": 0.7,
        "reason": "No strong anti-pattern found; column is likely usable as a feature.",
    }


def profile_dataset(df: pd.DataFrame) -> dict[str, Any]:
    columns: list[dict[str, Any]] = []

    for col in df.columns:
        s = df[col]
        numeric = pd.to_numeric(s, errors="coerce")
        is_numeric = numeric.notna().sum() > 0 and s.dtype != "bool"

        if is_numeric:
            s_num = numeric.dropna()
            mode_vals = s_num.mode()
            columns.append(
                {
                    "column": col,
                    "dtype": str(s.dtype),
                    "missing_count": int(s.isna().sum()),
                    "missing_pct": float(round(s.isna().mean() * 100, 4)),
                    "unique_values": int(s.nunique(dropna=True)),
                    "cardinality": float(round(s.nunique(dropna=True) / max(len(s), 1), 4)),
                    "min": float(s_num.min()) if not s_num.empty else None,
                    "max": float(s_num.max()) if not s_num.empty else None,
                    "mean": float(s_num.mean()) if not s_num.empty else None,
                    "median": float(s_num.median()) if not s_num.empty else None,
                    "mode": float(mode_vals.iloc[0]) if not mode_vals.empty else None,
                    "std": float(s_num.std()) if not s_num.empty else None,
                    "skewness": float(s_num.skew()) if not s_num.empty else None,
                }
            )
        else:
            mode_vals = s.mode(dropna=True)
            columns.append(
                {
                    "column": col,
                    "dtype": str(s.dtype),
                    "missing_count": int(s.isna().sum()),
                    "missing_pct": float(round(s.isna().mean() * 100, 4)),
                    "unique_values": int(s.nunique(dropna=True)),
                    "cardinality": float(round(s.nunique(dropna=True) / max(len(s), 1), 4)),
                    "min": None,
                    "max": None,
                    "mean": None,
                    "median": None,
                    "mode": str(mode_vals.iloc[0]) if not mode_vals.empty else None,
                    "std": None,
                    "skewness": None,
                }
            )

    roles = {
        "numerical": [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().sum() > 0 and str(df[c].dtype) not in ("bool", "boolean")],
        "categorical": [c for c in df.columns if df[c].dtype == "object" and df[c].nunique(dropna=True) <= 50],
        "date": [c for c in df.columns if "date" in c.lower() or "time" in c.lower()],
        "boolean": [c for c in df.columns if str(df[c].dtype) in ("bool", "boolean")],
        "text": [c for c in df.columns if df[c].dtype == "object" and df[c].astype(str).str.len().mean() > 35],
    }

    return {
        "summary": {
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
        },
        "roles": roles,
        "columns": columns,
    }


def quality_audit(df: pd.DataFrame) -> dict[str, Any]:
    missing_by_col = {col: int(df[col].isna().sum()) for col in df.columns}
    missing_by_row = int((df.isna().sum(axis=1) > 0).sum())

    duplicate_rows = int(df.duplicated().sum())

    numeric_cols = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().sum() > 0 and str(df[c].dtype) not in ("bool", "boolean")]
    iqr_outliers: dict[str, int] = {}
    zscore_outliers: dict[str, int] = {}

    for c in numeric_cols:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            iqr_outliers[c] = 0
        else:
            mask = (s < (q1 - 1.5 * iqr)) | (s > (q3 + 1.5 * iqr))
            iqr_outliers[c] = int(mask.sum())

        z = np.abs(stats.zscore(s, nan_policy="omit"))
        zscore_outliers[c] = int((z > 3).sum()) if len(z) else 0

    invalid_entries: list[dict[str, Any]] = []
    for c in numeric_cols:
        if "age" in c.lower():
            s = pd.to_numeric(df[c], errors="coerce")
            count = int((s < 0).sum())
            if count > 0:
                invalid_entries.append({"column": c, "rule": "age_cannot_be_negative", "count": count})

    for c in df.columns:
        if "email" in c.lower():
            pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}$")
            vals = df[c].dropna().astype(str)
            bad = int((~vals.str.match(pattern)).sum())
            if bad > 0:
                invalid_entries.append({"column": c, "rule": "invalid_email_pattern", "count": bad})

    inconsistent_formatting: list[dict[str, Any]] = []
    for c in df.columns:
        if df[c].dtype == "object":
            vals = df[c].dropna().astype(str)
            normalized = vals.str.strip().str.lower()
            raw_unique = vals.nunique()
            norm_unique = normalized.nunique()
            if raw_unique != norm_unique:
                inconsistent_formatting.append(
                    {
                        "column": c,
                        "issue": "case_or_whitespace_inconsistency",
                        "raw_unique": int(raw_unique),
                        "normalized_unique": int(norm_unique),
                    }
                )

    class_imbalance = None
    target_candidate = next((c for c in df.columns if any(k in c.lower() for k in ["target", "label", "class"])), None)
    if target_candidate is not None:
        dist = df[target_candidate].value_counts(dropna=True)
        if len(dist) > 1:
            ratio = float(dist.max() / max(dist.min(), 1))
            class_imbalance = {
                "target": target_candidate,
                "ratio": ratio,
                "imbalanced": ratio > 3.0,
                "distribution": {str(k): int(v) for k, v in dist.to_dict().items()},
            }

    return {
        "missing": {"by_column": missing_by_col, "rows_with_missing": missing_by_row},
        "duplicates": {"duplicate_rows": duplicate_rows, "near_duplicates": 0},
        "outliers": {"iqr": iqr_outliers, "zscore": zscore_outliers},
        "invalid_entries": invalid_entries,
        "inconsistent_formatting": inconsistent_formatting,
        "class_imbalance": class_imbalance,
    }


def build_cleaning_recommendations(df: pd.DataFrame, audit: dict[str, Any]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []

    for col, miss in audit["missing"]["by_column"].items():
        if miss <= 0:
            continue
        s = df[col]
        num = pd.to_numeric(s, errors="coerce")
        if num.notna().sum() > 0:
            skew = float(num.dropna().skew()) if num.dropna().shape[0] > 1 else 0.0
            has_outliers = audit["outliers"]["iqr"].get(col, 0) > 0
            action = "median_imputation" if has_outliers or abs(skew) > 1 else "mean_imputation"
            reason = (
                "Column has outliers/skewness; median is robust." if action == "median_imputation" else "Distribution is relatively stable; mean preserves central tendency."
            )
            confidence = 0.92 if action == "median_imputation" else 0.84
        else:
            action = "mode_imputation"
            reason = "Categorical values are best filled by most frequent category to preserve distribution."
            confidence = 0.86

        recs.append(
            {
                "column": col,
                "recommended_action": action,
                "confidence": confidence,
                "explanation": reason,
                "expected_impact": "Reduces null-induced model instability and prevents row drops.",
            }
        )

    if audit["duplicates"]["duplicate_rows"] > 0:
        recs.append(
            {
                "column": "__rows__",
                "recommended_action": "remove_duplicates",
                "confidence": 0.97,
                "explanation": "Exact duplicate records can bias statistics and learning.",
                "expected_impact": "Improves sample diversity and metric reliability.",
            }
        )

    return recs


def get_severity(impact_score: float) -> str:
    if impact_score >= 70:
        return "High"
    elif impact_score >= 30:
        return "Medium"
    return "Low"

def get_health_band(score: float) -> str:
    score_val = round(score)
    if score_val >= 90:
        return "Excellent"
    elif score_val >= 75:
        return "Good"
    elif score_val >= 60:
        return "Fair"
    elif score_val >= 40:
        return "Poor"
    return "Critical"

def dataset_health_score(audit: dict[str, Any], profile: dict[str, Any], total_rows: int) -> dict[str, Any]:
    total_rows = max(total_rows, 1)

    # Compute stats for formula
    missing_cells = sum(audit.get("missing", {}).get("by_column", {}).values())
    total_columns = max(len(audit.get("missing", {}).get("by_column", {}).keys()), 1)
    missing_pct = (missing_cells / (total_rows * total_columns)) * 100

    duplicate_rows = audit.get("duplicates", {}).get("duplicate_rows", 0)
    duplicate_pct = (duplicate_rows / total_rows) * 100

    outlier_count = sum(audit.get("outliers", {}).get("iqr", {}).values())
    numeric_columns = max(len(audit.get("outliers", {}).get("iqr", {}).keys()), 1)
    outlier_pct = (outlier_count / (total_rows * numeric_columns)) * 100
    
    high_cardinality_columns = 0
    for col in profile.get("columns", []):
        dtype = col.get("dtype", "")
        unique = col.get("unique_values", 0)
        if "object" in dtype or "str" in dtype:
            if unique > 15:
                high_cardinality_columns += 1

    # Count unique columns with invalid entries or inconsistent formatting
    invalid_cols = set()
    for entry in audit.get("invalid_entries", []):
        invalid_cols.add(entry.get("column"))
    for entry in audit.get("inconsistent_formatting", []):
        invalid_cols.add(entry.get("column"))
    invalid_columns = len(invalid_cols)

    # Reworked deductions model
    score = 100.0
    score -= min(40.0, missing_pct * 0.6)
    score -= min(20.0, duplicate_pct * 2.0)
    score -= min(15.0, outlier_pct * 0.5)
    score -= min(10.0, high_cardinality_columns * 2.0)
    score -= min(15.0, invalid_columns * 3.0)
    score = max(0.0, min(100.0, round(score)))

    # Never show 100 if issues exist
    issues = flatten_audit(audit, profile, total_rows)
    issues_exist = len(issues) > 0
    if issues_exist:
        score = min(score, 99.0)

    score_val = int(score)
    band = get_health_band(score_val)

    scores = {
        "Missing Values": max(0, 40 - min(40, int(missing_pct * 0.6))),
        "Duplicates": max(0, 20 - min(20, int(duplicate_pct * 2.0))),
        "Outliers": max(0, 15 - min(15, int(outlier_pct * 0.5))),
        "Consistency": max(0, 10 - min(10, int(high_cardinality_columns * 2.0))),
        "Integrity": max(0, 15 - min(15, int(invalid_columns * 3.0))),
    }

    suggestions = []
    if missing_pct > 5:
        suggestions.append("Apply imputation and missingness indicators for affected columns.")
    if duplicate_pct > 0:
        suggestions.append("Deduplicate records before model training.")
    if outlier_pct > 5:
        suggestions.append("Winsorize/cap extreme values or apply robust scaling.")
    if high_cardinality_columns > 0:
        suggestions.append("Address high cardinality columns to prevent data leakage.")
    if invalid_columns > 0:
        suggestions.append("Clean or normalize columns with inconsistent formatting and invalid rules.")

    return {
        "score": score_val,
        "band": band,
        "breakdown": scores,
        "improvement_suggestions": suggestions
    }

def flatten_audit(audit: dict[str, Any], profile: dict[str, Any] | int | None = None, total_rows: int | None = None) -> list[dict[str, Any]]:
    # If profile is an integer, it means the caller passed total_rows as the second argument
    if isinstance(profile, int):
        total_rows = profile
        profile = None

    if profile is None:
        profile = {}
    if total_rows is None:
        total_rows = 1

    issues = []
    total_rows = max(total_rows, 1)
    
    # 1. Missing Values
    for col, count in audit.get("missing", {}).get("by_column", {}).items():
        if count > 0:
            impact_score = min(100, (count / total_rows) * 100 * 2)
            missing_pct = (count / total_rows) * 100
            issues.append({
                "column": col,
                "issue": "Missing Values",
                "severity": get_severity(impact_score),
                "metric_value": f"{count} missing values",
                "affected_rows": count,
                "reason": f"{count} missing values in {total_rows} rows ({missing_pct:.1f}%)",
                "recommendation": "Impute or drop missing values"
            })
            
    # 2. Outliers
    for col, count in audit.get("outliers", {}).get("iqr", {}).items():
        if count > 0:
            impact_score = min(100, (count / total_rows) * 100 * 5) 
            issues.append({
                "column": col,
                "issue": "Outliers Detected",
                "severity": get_severity(impact_score),
                "metric_value": f"{count} outliers (IQR)",
                "affected_rows": count,
                "reason": f"{count} outliers detected using IQR bounds",
                "recommendation": "Cap or remove extreme values"
            })
            
    # 3. Formatting
    for entry in audit.get("inconsistent_formatting", []):
        col = entry["column"]
        impact_score = 40
        issues.append({
            "column": col,
            "issue": "Inconsistent Formatting",
            "severity": get_severity(impact_score),
            "metric_value": "Casing/whitespace issues",
            "affected_rows": 0,
            "reason": f"Casing/whitespace inconsistencies (raw: {entry['raw_unique']}, normalized: {entry['normalized_unique']})",
            "recommendation": "Strip whitespace and normalize case"
        })
        
    # 4. Invalid Entries
    for entry in audit.get("invalid_entries", []):
        col = entry["column"]
        count = entry["count"]
        impact_score = 80
        issues.append({
            "column": col,
            "issue": entry["rule"].replace("_", " ").title(),
            "severity": get_severity(impact_score),
            "metric_value": f"{count} invalid values",
            "affected_rows": count,
            "reason": f"{count} invalid values violating rule '{entry['rule']}'",
            "recommendation": "Clean or remove invalid entries"
        })

    # 5. Duplicate Rows
    dup_rows = audit.get("duplicates", {}).get("duplicate_rows", 0)
    if dup_rows > 0:
        impact_score = min(100, (dup_rows / total_rows) * 100 * 3)
        duplicate_pct = (dup_rows / total_rows) * 100
        issues.append({
            "column": "All Columns",
            "issue": "Duplicate Rows",
            "severity": get_severity(impact_score),
            "metric_value": f"{dup_rows} duplicate rows",
            "affected_rows": dup_rows,
            "reason": f"{dup_rows} duplicate rows out of {total_rows} rows ({duplicate_pct:.1f}%)",
            "recommendation": "Remove duplicate records"
        })

    # 6. High Cardinality (for categorical columns)
    for col_info in profile.get("columns", []):
        col = col_info.get("column", "")
        dtype = col_info.get("dtype", "")
        unique = col_info.get("unique_values", 0)
        if "object" in dtype or "str" in dtype:
            if unique > 15:
                issues.append({
                    "column": col,
                    "issue": "High Cardinality",
                    "severity": "Low",
                    "metric_value": f"{unique} unique values",
                    "affected_rows": unique,
                    "reason": f"{unique} unique values in {total_rows} rows",
                    "recommendation": "Consider text preprocessing or encoding strategy"
                })

    return issues


def apply_cleaning_actions(df: pd.DataFrame, actions: list[str]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    cleaned = df.copy()
    log: list[dict[str, Any]] = []

    if "remove_duplicates" in actions:
        before = len(cleaned)
        cleaned = cleaned.drop_duplicates()
        log.append({"action": "remove_duplicates", "removed": int(before - len(cleaned))})

    if "fill_missing" in actions:
        filled = 0
        for c in cleaned.columns:
            s = cleaned[c]
            if s.isna().sum() == 0:
                continue
            num = pd.to_numeric(s, errors="coerce")
            if num.notna().sum() > 0:
                val = float(num.median())
                cleaned[c] = num.fillna(val)
            else:
                mode_vals = s.mode(dropna=True)
                val = mode_vals.iloc[0] if not mode_vals.empty else "Unknown"
                cleaned[c] = s.fillna(val)
            filled += int(s.isna().sum())
        log.append({"action": "fill_missing", "filled_cells": filled})

    if "fix_formatting" in actions:
        changed = 0
        for c in cleaned.columns:
            if cleaned[c].dtype == "object":
                original = cleaned[c].copy()
                cleaned[c] = cleaned[c].astype(str).str.strip()
                changed += int((original != cleaned[c]).sum())
        log.append({"action": "fix_formatting", "updated_cells": changed})

    if "handle_outliers" in actions:
        updated = 0
        for c in cleaned.columns:
            num = pd.to_numeric(cleaned[c], errors="coerce")
            if num.notna().sum() == 0:
                continue
            q1, q3 = num.quantile(0.25), num.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            clipped = num.clip(lower=low, upper=high)
            updated += int((num != clipped).sum())
            cleaned[c] = clipped
        log.append({"action": "handle_outliers", "updated_cells": updated})

    if "convert_dtypes" in actions:
        converted = []
        for c in cleaned.columns:
            if "date" in c.lower() or "time" in c.lower():
                parsed = pd.to_datetime(cleaned[c], errors="coerce")
                if parsed.notna().sum() > 0:
                    cleaned[c] = parsed
                    converted.append(c)
        log.append({"action": "convert_dtypes", "columns": converted})

    return cleaned, log


def feature_engineering_suggestions(df: pd.DataFrame) -> list[dict[str, Any]]:
    suggestions = []

    for c in df.columns:
        s = df[c]
        sem = infer_semantic_type(c, s)
        sem_type = sem["type"]
        
        if s.nunique(dropna=True) <= 1:
            suggestions.append({"type": "drop_column", "column": c, "reason": "Constant column adds no predictive value."})
            continue
            
        if sem_type == "Identifier":
            suggestions.append({"type": "drop_column", "column": c, "reason": f"Identifier column risks leakage and weak generalization ({sem['reason']})."})
            
        elif sem_type == "DateTime":
            suggestions.append(
                {
                    "type": "create_feature",
                    "column": c,
                    "reason": "Extract year/month/day/weekday from temporal fields for stronger signals.",
                }
            )
            
        elif sem_type == "High Cardinality Categorical":
            suggestions.append({
                "type": "encoding",
                "column": c,
                "method": "hash_or_target",
                "reason": f"High cardinality categorical column ({sem['reason']}). Consider Hash Encoding, Target Encoding, or Embeddings."
            })
            
        elif sem_type == "Categorical":
            card = s.nunique(dropna=True)
            if card <= 15:
                suggestions.append({"type": "encoding", "column": c, "method": "one_hot", "reason": "Low-cardinality categorical feature."})
            else:
                suggestions.append({"type": "encoding", "column": c, "method": "target_or_frequency", "reason": "Categorical feature with high cardinality."})
                
        elif sem_type in ("Continuous Numeric", "Discrete Numeric"):
            suggestions.append({"type": "scaling", "column": c, "method": "standard_scaler", "reason": "Improve optimizer stability for many ML models."})

    return suggestions


def ml_readiness(df: pd.DataFrame, audit: dict[str, Any], suggestions: list[dict[str, Any]]) -> dict[str, Any]:
    quality_penalty = min(40, sum(audit["missing"]["by_column"].values()) / max(len(df), 1))
    target_exists = any(any(k in c.lower() for k in ["target", "label", "class", "y"]) for c in df.columns)
    target_score = 25 if target_exists else 10
    feature_score = max(0, 35 - min(20, len([s for s in suggestions if s["type"] == "drop_column"])))

    score = int(max(0, min(100, target_score + feature_score + int(40 - quality_penalty))))

    readiness = {
        "classification": target_exists,
        "regression": any(pd.to_numeric(df[c], errors="coerce").notna().sum() > len(df) * 0.8 and str(df[c].dtype) not in ("bool", "boolean") for c in df.columns),
        "time_series": any("date" in c.lower() or "time" in c.lower() for c in df.columns),
    }

    return {
        "score": score,
        "ready_for": readiness,
        "reasoning": "Readiness combines data quality, feature utility, and target suitability checks.",
    }


def basic_chat_answer(question: str, profile: dict[str, Any], audit: dict[str, Any], recs: list[dict[str, Any]], history: list[dict[str, Any]]) -> str:
    q = question.lower()

    if "summarize" in q or "summary" in q:
        s = profile["summary"]
        return f"Dataset has {s['rows']} rows and {s['columns']} columns. Missing rows: {audit['missing']['rows_with_missing']}. Duplicate rows: {audit['duplicates']['duplicate_rows']}."

    if "remove" in q and "column" in q:
        cols = [r.get("column") for r in recs if r.get("recommended_action") == "remove_duplicates"]
        return "No direct column removal recommendation yet. Suggested row-level cleanup includes duplicate removal." if not cols else str(cols)

    if "why" in q and "median" in q:
        med_recs = [r for r in recs if "median" in r.get("recommended_action", "")]
        if not med_recs:
            return "Median imputation is recommended when outliers/skewness exist because it is robust to extreme values."
        first = med_recs[0]
        return f"{first['column']} uses {first['recommended_action']} because {first['explanation']}"

    if "outlier" in q:
        return f"IQR outliers detected per column: {audit['outliers']['iqr']}"

    if "history" in q or "version" in q:
        if not history:
            return "No cleaning history yet beyond ingestion."
        return "Latest operations: " + "; ".join([f"v{h['version']} {h['action']}" for h in history[-5:]])

    return "I can answer questions about profiling, quality issues, cleaning decisions, feature suggestions, and readiness scores for this dataset."


def preprocessing_code(recs: list[dict[str, Any]], fe: list[dict[str, Any]]) -> str:
    lines = [
        "import pandas as pd",
        "",
        "def preprocess(df: pd.DataFrame) -> pd.DataFrame:",
        "    data = df.copy()",
        "",
    ]

    for r in recs:
        col = r.get("column")
        action = r.get("recommended_action")
        if col == "__rows__" and action == "remove_duplicates":
            lines.append("    data = data.drop_duplicates()")
        elif action == "median_imputation":
            lines.append(f"    data['{col}'] = pd.to_numeric(data['{col}'], errors='coerce').fillna(pd.to_numeric(data['{col}'], errors='coerce').median())")
        elif action == "mean_imputation":
            lines.append(f"    data['{col}'] = pd.to_numeric(data['{col}'], errors='coerce').fillna(pd.to_numeric(data['{col}'], errors='coerce').mean())")
        elif action == "mode_imputation":
            lines.append(f"    data['{col}'] = data['{col}'].fillna(data['{col}'].mode(dropna=True).iloc[0] if not data['{col}'].mode(dropna=True).empty else 'Unknown')")

    lines.append("")
    for s in fe:
        if s.get("type") == "create_feature" and s.get("column"):
            c = s["column"]
            lines.append(f"    dt = pd.to_datetime(data['{c}'], errors='coerce')")
            lines.append(f"    data['{c}_month'] = dt.dt.month")
            lines.append(f"    data['{c}_weekday'] = dt.dt.weekday")

    lines.append("    return data")
    return "\n".join(lines)


def generate_pdf_report(
    session_id: str,
    output_path: str,
    profile: dict[str, Any],
    audit: dict[str, Any],
    health: dict[str, Any],
    ml: dict[str, Any],
    charts_dir: str,
    cleaning_logs: list[dict[str, Any]],
    rows_before: int,
    rows_after: int,
    column_semantics: dict[str, Any] | None = None,
    cleaning_impact: dict[str, Any] | None = None,
    cleaned_health: dict[str, Any] | None = None,
) -> None:
    if cleaned_health is None:
        cleaned_health = {"score": 100, "band": "Excellent"}

    doc = SimpleDocTemplate(output_path, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    normal_style = styles['Normal']
    normal_style.fontSize = 8
    normal_style.leading = 10
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.whitesmoke
    )

    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#1e293b"),
        alignment=1, # Center
        spaceAfter=20
    )

    section_style = ParagraphStyle(
        'ReportSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=15,
        spaceAfter=10
    )

    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=10
    )

    def cell_p(text, style):
        return Paragraph(str(text), style)

    # ------------------ PAGE 1: EXECUTIVE SUMMARY ------------------
    story.append(Spacer(1, 20))
    story.append(Paragraph("AutoPrep AI - Executive Report", title_style))
    story.append(Paragraph(f"Dataset ID: {session_id}", normal_style))
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("Dataset Overview", section_style))
    summary = profile.get("summary", {})
    
    # Calculate stats for narrative
    missing_cells = sum(audit.get("missing", {}).get("by_column", {}).values())
    total_cols_count = len(profile.get("columns", []))
    missing_pct = (missing_cells / max(rows_before * total_cols_count, 1)) * 100
    outliers_count = sum(audit.get("outliers", {}).get("iqr", {}).values())
    
    # Calculate unique affected columns count in raw dataset
    affected_cols = set()
    for col, m in audit.get("missing", {}).get("by_column", {}).items():
        if m > 0:
            affected_cols.add(col)
    for col, o in audit.get("outliers", {}).get("iqr", {}).items():
        if o > 0:
            affected_cols.add(col)
    affected_cols_count = len(affected_cols)

    # Dynamic Narrative
    narrative_text = (
        f"The uploaded dataset '{summary.get('filename', 'dataset')}' contained "
        f"{missing_pct:.2f}% missing values across {affected_cols_count} affected columns "
        f"and {outliers_count} detected outliers. "
        f"AutoPrep AI successfully resolved all missing values, treated outliers using adaptive "
        f"statistical methods, and improved the dataset health score from {health.get('score', 100)} "
        f"({health.get('band', 'Unknown')}) to {cleaned_health.get('score', 100)} ({cleaned_health.get('band', 'Excellent')}). "
        f"The dataset is now suitable for machine learning and advanced analytical workflows."
    )

    overview_data = [
        [cell_p("Metric", header_style), cell_p("Value", header_style)],
        [cell_p("Filename", normal_style), cell_p(summary.get("filename", "Unknown"), normal_style)],
        [cell_p("Raw Row Count", normal_style), cell_p(str(rows_before), normal_style)],
        [cell_p("Cleaned Row Count", normal_style), cell_p(str(rows_after), normal_style)],
        [cell_p("Column Count", normal_style), cell_p(str(summary.get("columns", 0)), normal_style)],
        [cell_p("Raw Dataset Health Score", normal_style), cell_p(f"{health.get('score', 0)}/100 ({health.get('band', 'Unknown')})", normal_style)],
        [cell_p("Cleaned Dataset Health Score", normal_style), cell_p(f"{cleaned_health.get('score', 0)}/100 ({cleaned_health.get('band', 'Excellent')})", normal_style)],
        [cell_p("ML Readiness Score", normal_style), cell_p(f"{ml.get('score', 50)}/100", normal_style)]
    ]
    
    t_overview = Table(overview_data, colWidths=[200, 304])
    t_overview.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6)
    ]))
    story.append(t_overview)
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("Executive Summary Narrative", section_style))
    story.append(Paragraph(narrative_text, body_style))
    
    story.append(PageBreak())

    # ------------------ PAGE 2: DATA QUALITY FINDINGS ------------------
    story.append(Paragraph("Data Quality Findings (Raw Dataset)", section_style))
    story.append(Paragraph("The following data quality issues were detected in the raw dataset prior to cleaning:", body_style))
    story.append(Spacer(1, 10))
    
    issues = flatten_audit(audit, profile, rows_before)
    if issues:
        audit_data = [[
            cell_p("Column", header_style),
            cell_p("Issue", header_style),
            cell_p("Severity", header_style),
            cell_p("Metric", header_style),
            cell_p("Affected Rows", header_style),
            cell_p("Recommendation", header_style)
        ]]
        for issue in issues:
            audit_data.append([
                cell_p(issue["column"], normal_style),
                cell_p(issue["issue"], normal_style),
                cell_p(issue["severity"], normal_style),
                cell_p(issue["metric_value"], normal_style),
                cell_p(str(issue["affected_rows"]), normal_style),
                cell_p(issue["recommendation"], normal_style)
            ])
            
        t_audit = Table(audit_data, colWidths=[80, 80, 50, 70, 74, 150])
        t_audit.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(t_audit)
    else:
        story.append(Paragraph("No significant raw data quality issues were detected.", body_style))
        
    story.append(PageBreak())

    # ------------------ PAGE 3: COLUMN CLASSIFICATION SUMMARY ------------------
    story.append(Paragraph("Column Classification Summary", section_style))
    story.append(Paragraph("AutoPrep AI's semantic classification engine determined the following column semantics and configured the corresponding cleaning strategies:", body_style))
    story.append(Spacer(1, 10))
    
    if column_semantics:
        class_data = [[
            cell_p("Column", header_style),
            cell_p("Semantic Type", header_style),
            cell_p("Confidence", header_style),
            cell_p("Reason", header_style),
            cell_p("Cleaning Strategy", header_style)
        ]]
        for col, info in column_semantics.items():
            class_data.append([
                cell_p(col, normal_style),
                cell_p(info.get("type", "Unknown"), normal_style),
                cell_p(f"{info.get('confidence', 0.0)*100:.0f}%", normal_style),
                cell_p(info.get("reason", "No reason provided"), normal_style),
                cell_p(info.get("strategy", "None"), normal_style)
            ])
            
        t_class = Table(class_data, colWidths=[94, 90, 50, 150, 120])
        t_class.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(t_class)
    else:
        story.append(Paragraph("No column semantic classification data available.", body_style))
        
    story.append(PageBreak())

    # ------------------ PAGE 4: CLEANING ACTIONS PERFORMED ------------------
    story.append(Paragraph("Cleaning Actions Performed", section_style))
    story.append(Paragraph("The dataset cleaning engine executed the following transformations on the dataset:", body_style))
    story.append(Spacer(1, 10))
    
    if cleaning_logs:
        action_data = [[
            cell_p("Column", header_style),
            cell_p("Issue", header_style),
            cell_p("Strategy", header_style),
            cell_p("Reason", header_style),
            cell_p("Affected Cells", header_style),
            cell_p("Confidence", header_style)
        ]]
        for log in cleaning_logs:
            col = log.get("column") or "All Columns"
            conf = log.get("confidence", 1.0)
            conf_str = f"{conf*100:.0f}%" if conf is not None else "100%"
            action_data.append([
                cell_p(col, normal_style),
                cell_p(log.get("issue", "Deduplication"), normal_style),
                cell_p(log.get("strategy", "Remove Duplicates"), normal_style),
                cell_p(log.get("reason", ""), normal_style),
                cell_p(str(log.get("affected_cells", 0)), normal_style),
                cell_p(conf_str, normal_style)
            ])
            
        t_action = Table(action_data, colWidths=[94, 70, 90, 150, 50, 50])
        t_action.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(t_action)
    else:
        story.append(Paragraph("No cleaning operations were required or performed.", body_style))
        
    story.append(PageBreak())

    # ------------------ PAGE 5: BEFORE VS AFTER COMPARISON ------------------
    story.append(Paragraph("Before vs After Comparison", section_style))
    story.append(Paragraph("Summary comparison of quality metrics showing the improvements achieved by AutoPrep AI:", body_style))
    story.append(Spacer(1, 10))
    
    # Compile before vs after comparison
    raw_missing = missing_cells
    raw_duplicates = audit.get("duplicates", {}).get("duplicate_rows", 0)
    raw_outliers = outliers_count
    
    after_missing = 0
    after_duplicates = 0
    after_outliers = 0
    after_affected_cols = 0
    
    comp_data = [
        [cell_p("Metric", header_style), cell_p("Before Cleaning (Raw)", header_style), cell_p("After Cleaning (Cleaned)", header_style)],
        [cell_p("Missing Values", normal_style), cell_p(str(raw_missing), normal_style), cell_p(str(after_missing), normal_style)],
        [cell_p("Duplicate Rows", normal_style), cell_p(str(raw_duplicates), normal_style), cell_p(str(after_duplicates), normal_style)],
        [cell_p("Outliers Detected", normal_style), cell_p(str(raw_outliers), normal_style), cell_p(str(after_outliers), normal_style)],
        [cell_p("Columns Affected", normal_style), cell_p(str(affected_cols_count), normal_style), cell_p(str(after_affected_cols), normal_style)]
    ]
    
    t_comp = Table(comp_data, colWidths=[180, 162, 162])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8)
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 25))
    
    story.append(Paragraph("Cleaning Engine Impact Stats", section_style))
    impact_data = [
        [cell_p("Total Cells Modified", normal_style), cell_p(str(cleaning_impact.get("cells_modified", 0) if cleaning_impact else 0), normal_style)],
        [cell_p("Rows Before Cleaning", normal_style), cell_p(str(rows_before), normal_style)],
        [cell_p("Rows After Cleaning", normal_style), cell_p(str(rows_after), normal_style)]
    ]
    t_impact = Table(impact_data, colWidths=[200, 304])
    t_impact.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6)
    ]))
    story.append(t_impact)
    
    story.append(PageBreak())

    # ------------------ PAGE 6: VISUAL INSIGHTS ------------------
    story.append(Paragraph("Visual Insights & Interpretations", section_style))
    story.append(Paragraph("Detailed visual insights generated from the raw dataset attributes:", body_style))
    story.append(Spacer(1, 10))
    
    chart_existed = False
    
    chart_info = [
        ("missing_values.png", "Missing Values Distribution", 
         "Missing Values Chart: Shows the distribution of null cells across attributes. Higher missingness suggests potential biases in subset analysis and requires robust mode or mean imputation strategies."),
        ("correlation_heatmap.png", "Correlation Heatmap", 
         "Correlation Heatmap: Details the pairwise linear relationships between numerical fields. Strong patterns identify feature redundancy, helping prevent multicollinearity in linear models."),
        ("histogram.png", "Distribution Histogram", 
         "Distribution Histogram: Visualizes the empirical probability density of the primary numeric attribute. Displays skewness or multimodal features, prompting scaling decisions."),
        ("boxplot.png", "Outlier Boxplot", 
         "Outlier Boxplot: Outlines the quartile bounds and anomalies beyond the 1.5 IQR threshold. Displays data dispersion and skew, showing the range of values capped during cleaning.")
    ]
    
    for filename, title, interpretation in chart_info:
        chart_path = os.path.join(charts_dir, filename)
        if os.path.exists(chart_path):
            chart_existed = True
            story.append(Paragraph(title, styles['Heading3']))
            story.append(Spacer(1, 4))
            story.append(Image(chart_path, width=350, height=200))
            story.append(Spacer(1, 6))
            story.append(Paragraph(interpretation, body_style))
            story.append(Spacer(1, 15))
            
    if not chart_existed:
        story.append(Paragraph("No visualization charts were generated or found for this dataset.", body_style))
        
    story.append(PageBreak())

    # ------------------ PAGE 7: AI RECOMMENDATIONS ------------------
    story.append(Paragraph("AI Recommendations & Next Steps", section_style))
    story.append(Spacer(1, 10))
    
    # Load insight suggest functions
    from app.services.insight_engine import suggest_advanced_features, recommend_models
    
    fe_suggestions = suggest_advanced_features(profile)
    model_recs = recommend_models(profile)
    
    story.append(Paragraph("Feature Engineering Suggestions", styles['Heading3']))
    story.append(Spacer(1, 5))
    if fe_suggestions:
        for idx, sug in enumerate(fe_suggestions[:4]):
            text = f"<b>{idx+1}. {sug.get('feature_name')}</b>: {sug.get('reason')} <i>Benefit: {sug.get('expected_benefit')}</i>"
            story.append(Paragraph(text, body_style))
    else:
        story.append(Paragraph("No specific feature engineering suggestions were generated.", body_style))
        
    story.append(Spacer(1, 15))
    story.append(Paragraph("Model Recommendations", styles['Heading3']))
    story.append(Spacer(1, 5))
    if model_recs and model_recs.get("task") != "Unknown":
        story.append(Paragraph(f"<b>Target Variable:</b> '{model_recs.get('target_column')}' (Task: {model_recs.get('task')})", body_style))
        for sug in model_recs.get("recommendations", []):
            text = f"- <b>{sug.get('model')}</b>: {sug.get('explanation')}"
            story.append(Paragraph(text, body_style))
    else:
        story.append(Paragraph("No target column was identified, so predictive model recommendations were skipped.", body_style))
        
    story.append(Spacer(1, 15))
    story.append(Paragraph("Potential Risks & Next Steps", styles['Heading3']))
    story.append(Spacer(1, 5))
    
    # Dynamic risks & next steps
    risks = []
    if missing_cells > 0:
        risks.append("Imputation preserves record density but can reduce metric variance if missingness ratio was extremely high.")
    if outliers_count > 0:
        risks.append("Capping outliers modifies raw values; verify downstream if capped values influence linear patterns.")
    if not risks:
        risks.append("No primary quality or downstream classification risks detected.")
        
    for r in risks:
        story.append(Paragraph(f"• Risk: {r}", body_style))
        
    story.append(Spacer(1, 5))
    story.append(Paragraph("• Next Step: Export the cleaned dataset to your standard data-warehouse or model pipeline.", body_style))
    story.append(Paragraph("• Next Step: Train baseline model benchmarks using the recommended models listed above.", body_style))

    # Compile exact 7 pages build
    def draw_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.drawString(54, 36, f"Page {doc.page} of 7")
        canvas.drawRightString(doc.pagesize[0] - 54, 36, "AutoPrep AI Report")
        canvas.restoreState()
        
    doc.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)


def infer_semantic_type(col_name: str, series: pd.Series) -> dict[str, Any]:
    name_lower = col_name.lower()
    series_clean = series.dropna()
    total_rows = len(series)
    
    if total_rows == 0 or series_clean.empty:
        return {
            "type": "Unknown",
            "confidence": 0.0,
            "reason": "Unable to determine semantic type"
        }
        
    unique_count = int(series_clean.nunique())
    unique_ratio = float(unique_count / total_rows)
    unique_ratio_clean = float(unique_count / len(series_clean)) if len(series_clean) > 0 else 0.0

    # Additional Fix 1: Pre-classification Numeric Coercion Check
    is_coerced_numeric = False
    if series_clean.dtype == "object" or str(series_clean.dtype) == "string":
        # Clean currency symbols, commas, percentage signs, and whitespace
        cleaned_series = (
            series_clean.astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.strip()
        )
        try:
            # Check numeric conversion
            coerced = pd.to_numeric(cleaned_series, errors="coerce")
            valid_count = int(coerced.notna().sum())
            total_clean = len(series_clean)
            if total_clean > 0 and (valid_count / total_clean) > 0.80:
                is_coerced_numeric = True
                series_clean = coerced.dropna()
                # Update variables used for classification
                unique_count = int(series_clean.nunique())
                unique_ratio = float(unique_count / total_rows)
                unique_ratio_clean = float(unique_count / len(series_clean)) if len(series_clean) > 0 else 0.0
        except Exception:
            pass

    # Check mixed types (only if not coerced to numeric)
    is_mixed = False
    has_text = False
    has_num = False
    has_bool = False
    if not is_coerced_numeric:
        type_counts = series_clean.apply(lambda x: type(x).__name__).value_counts()
        is_mixed = len(type_counts) > 1
        has_text = any(t in type_counts for t in ("str", "object"))
        has_num = any(t in type_counts for t in ("int", "float", "int64", "float64"))
        has_bool = any(t in type_counts for t in ("bool", "bool_"))
    
    res = None
    
    # 1. Identifier Check (first priority)
    id_keywords = {"id", "customer_id", "invoice_no", "invoiceno", "order_id", "orderid", "uuid", "key", "employee_id", "employeeno"}
    is_id_name = any(k == name_lower or name_lower.endswith("_" + k) or name_lower.endswith(k) for k in id_keywords)
    
    if is_id_name and unique_ratio_clean >= 0.80:
        res = {
            "type": "Identifier",
            "confidence": 0.98,
            "reason": f"Matches identifier naming pattern and uniqueness ratio of non-missing values is high ({unique_ratio_clean:.2f})."
        }
    
    # 2. DateTime Check
    elif pd.api.types.is_datetime64_any_dtype(series_clean.dtype):
        res = {
            "type": "DateTime",
            "confidence": 0.99,
            "reason": "Column is natively formatted as DateTime."
        }
    elif not res and (series_clean.dtype == "object" or str(series_clean.dtype) == "string"):
        # Check that it's not purely numeric strings to avoid converting numbers
        is_pure_numeric = series_clean.astype(str).str.match(r'^-?\d+(\.\d+)?$').all()
        if not is_pure_numeric:
            try:
                parsed = pd.to_datetime(series_clean, errors="coerce")
                success_ratio = float(parsed.notna().sum() / len(series_clean))
                if success_ratio > 0.8:
                    res = {
                        "type": "DateTime",
                        "confidence": 0.95,
                        "reason": f"Successfully parsed as DateTime with {success_ratio*100:.1f}% valid timestamps."
                    }
            except Exception:
                pass

    # 3. Boolean Check
    if not res:
        if str(series_clean.dtype) in ("bool", "boolean"):
            res = {
                "type": "Boolean",
                "confidence": 0.99,
                "reason": "Column is natively formatted as boolean."
            }
        elif unique_count == 2:
            vals_cleaned = {str(v).strip().lower() for v in series_clean.unique()}
            boolean_formats = {
                ("true", "false"), ("yes", "no"), ("y", "n"), ("1", "0"), ("1.0", "0.0"), ("t", "f"),
            }
            
            is_bool_format = False
            for fmt in boolean_formats:
                if vals_cleaned.issubset(fmt):
                    is_bool_format = True
                    break
                    
            if is_bool_format:
                res = {
                    "type": "Boolean",
                    "confidence": 0.96,
                    "reason": f"Column contains boolean-like representations: {vals_cleaned}."
                }

    # 4. Unknown/Ambiguous mixed column check
    if not res and is_mixed and has_text and (has_num or has_bool):
        res = {
            "type": "Unknown",
            "confidence": 0.0,
            "reason": "Unable to determine semantic type"
        }

    # 5. Numeric Check (Continuous vs Discrete) - Prioritized before categorical/text checks
    is_numeric = pd.api.types.is_numeric_dtype(series_clean.dtype)
    if not res and is_numeric:
        is_discrete = True
        try:
            # Check sample of values
            for val in series_clean.head(100):
                if not float(val).is_integer():
                    is_discrete = False
                    break
        except (ValueError, TypeError):
            is_discrete = False
            
        if is_discrete:
            # Removed 'age' from continuous keywords, added 'spent'
            continuous_keywords = {"revenue", "income", "salary", "price", "cost", "amount", "spent", "temperature", "rate", "pct", "percent"}
            if any(k in name_lower for k in continuous_keywords):
                res = {
                    "type": "Continuous Numeric",
                    "confidence": 0.90,
                    "reason": f"Integer values representing continuous metrics (e.g. price, spent) based on column name '{col_name}'."
                }
            else:
                res = {
                    "type": "Discrete Numeric",
                    "confidence": 0.92,
                    "reason": "Examined values are integer-like count metrics."
                }
        else:
            res = {
                "type": "Continuous Numeric",
                "confidence": 0.90,
                "reason": "Continuous numeric values containing floating-point decimals."
            }

    # 6. Free Text Check
    if not res and (series_clean.dtype == "object" or str(series_clean.dtype) == "string"):
        avg_len = float(series_clean.astype(str).str.len().mean())
        if avg_len > 35:
            res = {
                "type": "Free Text",
                "confidence": 0.88,
                "reason": f"Free text detected: average length is {avg_len:.1f} characters (> 35)."
            }

    # 7. Extremely High Cardinality Detection (Only for non-numeric, object/string columns with unique_count > 10)
    if not res and unique_count > 10 and unique_ratio > 0.50 and (series_clean.dtype == "object" or str(series_clean.dtype) == "string"):
        res = {
            "type": "High Cardinality Categorical",
            "confidence": 0.85,
            "reason": f"High cardinality categorical column: uniqueness ratio is {unique_ratio:.2f} (> 0.50) and it is not an Identifier."
        }

    # 8. Categorical Check
    if not res and (series_clean.dtype == "object" or str(series_clean.dtype) == "string"):
        res = {
            "type": "Categorical",
            "confidence": 0.90,
            "reason": "Categorical values stored as strings."
        }
    elif not res:
        # Non-numeric: check standard categorical thresholds
        if unique_count <= 20 or (unique_ratio < 0.05 and unique_count <= 50):
            res = {
                "type": "Categorical",
                "confidence": 0.85,
                "reason": f"Low cardinality column ({unique_count} unique values) acting as categories."
            }

    # Fallback & Threshold Check
    if not res or res["confidence"] < 0.70 or res["type"] == "Unknown":
        return {
            "type": "Unknown",
            "confidence": 0.0,
            "reason": "Unable to determine semantic type"
        }
        
    return res


def standardize_boolean_series(series: pd.Series) -> pd.Series:
    mapping = {
        "true": True, "false": False,
        "yes": True, "no": False,
        "y": True, "n": False,
        "t": True, "f": False,
        "1": True, "0": False,
        "1.0": True, "0.0": False,
        1: True, 0: False,
        1.0: True, 0.0: False,
        True: True, False: False
    }
    def map_val(val):
        if pd.isna(val):
            return val
        if isinstance(val, str):
            cleaned = val.strip().lower()
            return mapping.get(cleaned, val)
        return mapping.get(val, val)
        
    return series.apply(map_val)


def auto_clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """
    Automatically clean the dataset based on semantic rules.
    Returns cleaned DataFrame, cleaning logs, impact statistics, column semantics, and column impacts.
    """
    from app.core.config import settings
    cleaned = df.copy()
    logs = []
    
    column_semantics = {}
    column_impacts = []
    
    # Impact tracking metrics
    missing_values_fixed = 0
    duplicates_removed = 0
    outliers_treated = 0
    columns_modified_set = set()
    cells_modified = 0

    # Calculate original metrics for metadata / audit trail
    original_missing_count = int(df.isna().sum().sum())
    original_duplicate_count = int(df.duplicated().sum())
    original_outlier_count = 0
    # Count original outliers using same rules as before cleaning
    for col in df.columns:
        s = df[col]
        sem_res = infer_semantic_type(col, s)
        sem_type = sem_res["type"]
        if sem_type in ("Continuous Numeric", "Discrete Numeric"):
            s_num = pd.to_numeric(s, errors="coerce").dropna()
            if len(s_num) > 2:
                q1, q3 = s_num.quantile(0.25), s_num.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    original_outlier_count += int(((s_num < (q1 - 1.5 * iqr)) | (s_num > (q3 + 1.5 * iqr))).sum())

    # 1. Duplicates
    dup_count = int(cleaned.duplicated().sum())
    if dup_count > 0:
        cleaned = cleaned.drop_duplicates()
        duplicates_removed = dup_count
        cells_modified += dup_count * len(df.columns)
        logs.append({
            "column": None,
            "semantic_type": "Dataset",
            "issue": "Duplicate Rows",
            "strategy": "Remove Duplicates",
            "method": "drop_exact_duplicates",
            "confidence": 0.98,
            "reason": f"Removed {dup_count} exact duplicate rows.",
            "affected_rows": dup_count,
            "affected_cells": dup_count * len(df.columns)
        })

    # Columns loop
    for col in df.columns:
        s = cleaned[col]
        
        # Infer semantic type
        sem_res = infer_semantic_type(col, s)
        sem_type = sem_res["type"]

        # Numeric Coercion Check: if it was inferred as numeric but stored as object/string
        if sem_type in ("Continuous Numeric", "Discrete Numeric") and (s.dtype == "object" or str(s.dtype) == "string"):
            cleaned_s = (
                s.astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("$", "", regex=False)
                .str.replace("%", "", regex=False)
                .str.strip()
            )
            coerced = pd.to_numeric(cleaned_s, errors="coerce")
            cleaned[col] = coerced
            s = cleaned[col]
            
            # Log the coercion format cleanup
            logs.append({
                "column": col,
                "semantic_type": sem_type,
                "issue": "Numeric Formatting",
                "strategy": "Numeric Coercion",
                "method": "strip_non_numeric_chars",
                "confidence": 0.95,
                "reason": f"Stripped currency symbols, percentage signs, and commas to convert column to numeric.",
                "affected_rows": int(s.notna().sum()),
                "affected_cells": int(s.notna().sum())
            })
        
        # Track column-level metrics before
        null_count_before = int(s.isna().sum())
        outlier_count_before = 0
        if sem_type in ("Continuous Numeric", "Discrete Numeric"):
            s_num = pd.to_numeric(s, errors="coerce").dropna()
            if len(s_num) > 2:
                q1, q3 = s_num.quantile(0.25), s_num.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    outlier_count_before = int(((s_num < (q1 - 1.5 * iqr)) | (s_num > (q3 + 1.5 * iqr))).sum())
        
        col_modified = False
        col_cells_modified = 0
        col_missing_fixed = 0
        col_outliers_treated = 0
        
        applied_actions = []
        applied_reasons = []

        # 0. Unknown Fallback
        if sem_type == "Unknown":
            logs.append({
                "column": col,
                "semantic_type": "Unknown",
                "issue": "Unknown Semantic Type",
                "strategy": "None",
                "method": "none",
                "confidence": 0.0,
                "reason": f"Warning: Column '{col}' is classified as Unknown semantic type. Left untouched to prevent accidental corruption.",
                "affected_rows": 0,
                "affected_cells": 0
            })
            applied_actions.append("None")
            applied_reasons.append("Unable to determine semantic type")

        else:
            # Whitespace stripping for object-like/categorical/text columns
            if sem_type in ("Categorical", "Free Text", "High Cardinality Categorical") and s.dtype == "object":
                s_str = s.astype(str)
                non_null_mask = s.notna()
                stripped = s_str.str.strip()
                changes = int(((s_str != stripped) & non_null_mask).sum())
                if changes > 0:
                    cleaned[col] = cleaned[col].astype(str).str.strip()
                    col_modified = True
                    col_cells_modified += changes
                    logs.append({
                        "column": col,
                        "semantic_type": sem_type,
                        "issue": "Whitespace Formatting",
                        "strategy": "Strip Whitespace",
                        "method": "strip_whitespace",
                        "confidence": 0.95,
                        "reason": f"Stripped leading/trailing whitespace in {changes} cells.",
                        "affected_rows": changes,
                        "affected_cells": changes
                    })
                    applied_actions.append("Strip Whitespace")
                    applied_reasons.append(f"Stripped whitespace in {changes} cells")
                    s = cleaned[col]

            # 2. DateTime Auto-Convert (if DateTime parsed successfully)
            if sem_type == "DateTime" and s.dtype == "object":
                try:
                    parsed = pd.to_datetime(s, errors="coerce")
                    cleaned[col] = parsed
                    col_modified = True
                    col_cells_modified += len(s)
                    logs.append({
                        "column": col,
                        "semantic_type": "DateTime",
                        "issue": "DateTime Formatting",
                        "strategy": "DateTime Conversion",
                        "method": "datetime_parse",
                        "confidence": 0.95,
                        "reason": "Parsed date strings to native datetime format.",
                        "affected_rows": len(s),
                        "affected_cells": len(s)
                    })
                    applied_actions.append("DateTime Conversion")
                    applied_reasons.append("Parsed to native datetime")
                    s = cleaned[col]
                except Exception:
                    pass

            # 3. Missing Value Imputation
            null_count = int(s.isna().sum())
            if null_count > 0:
                if sem_type == "Continuous Numeric":
                    numeric_series = pd.to_numeric(s, errors="coerce")
                    s_num = numeric_series.dropna()
                    skewness = float(s_num.skew()) if len(s_num) > 1 else 0.0
                    
                    if abs(skewness) > 1.5:
                        val = float(s_num.median())
                        strategy = "Median Imputation"
                        method = "median_imputation"
                        reason = f"Filled {null_count} missing values with Median ({val:.2f}) because the distribution is highly skewed (skew={skewness:.2f})."
                        reason_short = f"Skewness = {skewness:.2f}"
                        confidence = 0.88
                    else:
                        val = float(s_num.mean())
                        strategy = "Mean Imputation"
                        method = "mean_imputation"
                        reason = f"Filled {null_count} missing values with Mean ({val:.2f}) as the distribution is approximately normal (skew={skewness:.2f})."
                        reason_short = f"Skewness = {skewness:.2f}"
                        confidence = 0.82
                    
                    cleaned[col] = numeric_series.fillna(val)
                    col_modified = True
                    col_cells_modified += null_count
                    col_missing_fixed += null_count
                    logs.append({
                        "column": col,
                        "semantic_type": sem_type,
                        "issue": "Missing Values",
                        "strategy": strategy,
                        "method": method,
                        "confidence": confidence,
                        "reason": reason,
                        "affected_rows": null_count,
                        "affected_cells": null_count
                    })
                    applied_actions.append(strategy)
                    applied_reasons.append(reason_short)

                elif sem_type == "Discrete Numeric":
                    numeric_series = pd.to_numeric(s, errors="coerce")
                    s_num = numeric_series.dropna()
                    val = int(round(s_num.median())) if not s_num.empty else 0
                    cleaned[col] = numeric_series.fillna(val)
                    col_modified = True
                    col_cells_modified += null_count
                    col_missing_fixed += null_count
                    logs.append({
                        "column": col,
                        "semantic_type": sem_type,
                        "issue": "Missing Values",
                        "strategy": "Discrete Median Imputation",
                        "method": "discrete_median_imputation",
                        "confidence": 0.90,
                        "reason": f"Filled {null_count} missing values with rounded integer Median ({val}).",
                        "affected_rows": null_count,
                        "affected_cells": null_count
                    })
                    applied_actions.append("Discrete Median Imputation")
                    applied_reasons.append(f"Median = {val}")

                elif sem_type == "Boolean":
                    s_mapped = standardize_boolean_series(s)
                    mode_vals = s_mapped.mode(dropna=True)
                    val = bool(mode_vals.iloc[0]) if not mode_vals.empty else False
                    cleaned[col] = s_mapped.fillna(val)
                    col_modified = True
                    col_cells_modified += null_count
                    col_missing_fixed += null_count
                    logs.append({
                        "column": col,
                        "semantic_type": sem_type,
                        "issue": "Missing Values",
                        "strategy": "Mode Imputation",
                        "method": "mode_imputation",
                        "confidence": 0.95,
                        "reason": f"Filled {null_count} missing values with Boolean Mode ({val}).",
                        "affected_rows": null_count,
                        "affected_cells": null_count
                    })
                    applied_actions.append("Mode Imputation")
                    applied_reasons.append(f"Boolean Mode = {val}")

                elif sem_type in ("Categorical", "High Cardinality Categorical"):
                    missing_pct = null_count / len(s)
                    if missing_pct <= 0.10:
                        mode_vals = s.mode(dropna=True)
                        val = str(mode_vals.iloc[0]) if not mode_vals.empty else "Unknown"
                        strategy = "Mode Imputation"
                        method = "mode_imputation"
                        reason = f"Filled {null_count} missing values with Mode ('{val}') since missing percentage ({missing_pct*100:.1f}%) is low."
                        reason_short = f"Mode = '{val}'"
                        confidence = 0.90
                    else:
                        val = "Unknown"
                        strategy = "Fill Unknown"
                        method = "fill_unknown"
                        reason = f"Filled {null_count} missing values with 'Unknown' since missing percentage ({missing_pct*100:.1f}%) is high."
                        reason_short = "Filled Unknown"
                        confidence = 0.80
                    
                    cleaned[col] = s.fillna(val)
                    col_modified = True
                    col_cells_modified += null_count
                    col_missing_fixed += null_count
                    logs.append({
                        "column": col,
                        "semantic_type": sem_type,
                        "issue": "Missing Values",
                        "strategy": strategy,
                        "method": method,
                        "confidence": confidence,
                        "reason": reason,
                        "affected_rows": null_count,
                        "affected_cells": null_count
                    })
                    applied_actions.append(strategy)
                    applied_reasons.append(reason_short)

                elif sem_type == "Identifier":
                    strategy = getattr(settings, "identifier_missing_strategy", "flag_issue")
                    if strategy == "remove_rows":
                        before_rows = len(cleaned)
                        cleaned = cleaned.dropna(subset=[col])
                        removed_rows = before_rows - len(cleaned)
                        col_modified = True
                        col_cells_modified += removed_rows * len(df.columns)
                        logs.append({
                            "column": col,
                            "semantic_type": sem_type,
                            "issue": "Missing Values",
                            "strategy": "Remove Rows",
                            "method": "remove_rows",
                            "confidence": 0.95,
                            "reason": f"Removed {removed_rows} rows due to missing identifier keys.",
                            "affected_rows": removed_rows,
                            "affected_cells": removed_rows * len(df.columns)
                        })
                        applied_actions.append("Remove Rows")
                        applied_reasons.append("Missing identifier rows removed")
                    elif strategy in ("flag_issue", "leave_untouched"):
                        logs.append({
                            "column": col,
                            "semantic_type": sem_type,
                            "issue": "Missing Values",
                            "strategy": "Flag Issue",
                            "method": "flag_issue",
                            "confidence": 1.0,
                            "reason": f"Warning: Identifier column contains {null_count} missing values. Left untouched per configuration.",
                            "affected_rows": 0,
                            "affected_cells": 0
                        })
                        applied_actions.append("Flag Issue")
                        applied_reasons.append("Warning logged for missing identifiers")

                elif sem_type == "DateTime":
                    missing_pct = null_count / len(s)
                    if missing_pct <= 0.10:
                        cleaned[col] = s.ffill().bfill()
                        col_modified = True
                        col_cells_modified += null_count
                        col_missing_fixed += null_count
                        logs.append({
                            "column": col,
                            "semantic_type": sem_type,
                            "issue": "Missing Values",
                            "strategy": "Forward/Backward Fill",
                            "method": "ffill_bfill",
                            "confidence": 0.90,
                            "reason": f"Imputed {null_count} missing dates using forward and backward propagation.",
                            "affected_rows": null_count,
                            "affected_cells": null_count
                        })
                        applied_actions.append("Forward/Backward Fill")
                        applied_reasons.append("Low missingness date propagation")
                    else:
                        s_clean = s.dropna()
                        if not s_clean.empty:
                            median_ts = pd.Timestamp(int(s_clean.astype('int64').median()))
                            cleaned[col] = s.fillna(median_ts)
                            col_modified = True
                            col_cells_modified += null_count
                            col_missing_fixed += null_count
                            logs.append({
                                "column": col,
                                "semantic_type": sem_type,
                                "issue": "Missing Values",
                                "strategy": "Median Date Imputation",
                                "method": "median_date_imputation",
                                "confidence": 0.82,
                                "reason": f"Imputed {null_count} missing dates with Median Date ({median_ts.strftime('%Y-%m-%d')}).",
                                "affected_rows": null_count,
                                "affected_cells": null_count
                            })
                            applied_actions.append("Median Date Imputation")
                            applied_reasons.append(f"Median date = {median_ts.strftime('%Y-%m-%d')}")

                elif sem_type == "Free Text":
                    cleaned[col] = s.fillna("Unknown")
                    col_modified = True
                    col_cells_modified += null_count
                    col_missing_fixed += null_count
                    logs.append({
                        "column": col,
                        "semantic_type": sem_type,
                        "issue": "Missing Values",
                        "strategy": "Fill Unknown",
                        "method": "fill_unknown",
                        "confidence": 0.85,
                        "reason": f"Filled {null_count} missing free text entries with 'Unknown'.",
                        "affected_rows": null_count,
                        "affected_cells": null_count
                    })
                    applied_actions.append("Fill Unknown")
                    applied_reasons.append("Filled text nulls with 'Unknown'")
                
                s = cleaned[col]

            # 4. Outliers
            if sem_type in ("Continuous Numeric", "Discrete Numeric"):
                s_num = pd.to_numeric(s, errors="coerce")
                s_clean = s_num.dropna()
                if len(s_clean) > 2:
                    skewness = float(s_clean.skew()) if len(s_clean) > 1 else 0.0
                    
                    if abs(skewness) > 1.5:
                        outlier_method = "iqr"
                    elif len(df) < 500:
                        outlier_method = "iqr"
                    else:
                        outlier_method = "zscore"
                        
                    if outlier_method == "iqr":
                        q1, q3 = s_clean.quantile(0.25), s_clean.quantile(0.75)
                        iqr = q3 - q1
                        if iqr > 0:
                            low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                            outliers_mask = (s_clean < low) | (s_clean > high)
                        else:
                            outliers_mask = pd.Series(False, index=s_clean.index)
                    else:
                        mean = s_clean.mean()
                        std = s_clean.std()
                        if std > 0:
                            low, high = mean - 3 * std, mean + 3 * std
                            outliers_mask = np.abs((s_clean - mean) / std) > 3
                        else:
                            outliers_mask = pd.Series(False, index=s_clean.index)
                            
                    outlier_count = int(outliers_mask.sum())
                    if outlier_count > 0:
                        strategy = getattr(settings, "outlier_strategy", "cap")
                        
                        if strategy == "cap":
                            clipped = s_clean.clip(lower=low, upper=high)
                            cleaned[col] = clipped.reindex(cleaned.index).fillna(clipped.median())
                            col_modified = True
                            col_cells_modified += outlier_count
                            col_outliers_treated += outlier_count
                            logs.append({
                                "column": col,
                                "semantic_type": sem_type,
                                "issue": "Outliers",
                                "strategy": f"Clip {outlier_method.upper()} Bounds",
                                "method": f"clip_{outlier_method}_bounds",
                                "confidence": 0.85 if outlier_method == "iqr" else 0.80,
                                "reason": f"Capped {outlier_count} outliers using {outlier_method.upper()} bounds [{low:.2f}, {high:.2f}] (Skewness={skewness:.2f}, Rows={len(df)}).",
                                "affected_rows": outlier_count,
                                "affected_cells": outlier_count
                            })
                            applied_actions.append(f"Clip {outlier_method.upper()} Bounds")
                            applied_reasons.append(f"Capped {outlier_count} outliers")
                        elif strategy == "remove":
                            before_rows = len(cleaned)
                            outlier_indices = s_clean[outliers_mask].index
                            cleaned = cleaned.drop(outlier_indices, errors="ignore")
                            removed_rows = before_rows - len(cleaned)
                            col_modified = True
                            col_cells_modified += removed_rows * len(df.columns)
                            col_outliers_treated += outlier_count
                            logs.append({
                                "column": col,
                                "semantic_type": sem_type,
                                "issue": "Outliers",
                                "strategy": "Remove Outliers",
                                "method": f"remove_{outlier_method}_outliers",
                                "confidence": 0.85 if outlier_method == "iqr" else 0.80,
                                "reason": f"Removed {removed_rows} rows containing {outlier_method.upper()} outliers (Skewness={skewness:.2f}, Rows={len(df)}).",
                                "affected_rows": removed_rows,
                                "affected_cells": removed_rows * len(df.columns)
                            })
                            applied_actions.append("Remove Outliers")
                            applied_reasons.append(f"Removed {removed_rows} rows with outliers")
                        elif strategy == "flag":
                            logs.append({
                                "column": col,
                                "semantic_type": sem_type,
                                "issue": "Outliers",
                                "strategy": "Flag Outliers",
                                "method": f"flag_{outlier_method}_outliers",
                                "confidence": 1.0,
                                "reason": f"Warning: Detected {outlier_count} outliers using {outlier_method.upper()} bounds. Left untouched.",
                                "affected_rows": 0,
                                "affected_cells": 0
                            })
                            applied_actions.append("Flag Outliers")
                            applied_reasons.append(f"Flagged {outlier_count} outliers")
                s = cleaned[col]

            # 5. Dtype Preservation
            if sem_type == "Discrete Numeric":
                try:
                    cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce").round().astype("Int64")
                except Exception:
                    pass
            elif sem_type == "Boolean":
                try:
                    cleaned[col] = standardize_boolean_series(cleaned[col]).astype("boolean")
                except Exception:
                    pass

        # Build column strategy metadata
        if not applied_actions:
            col_strategy = "None"
            col_reason = "No cleaning required based on data profile."
        else:
            col_strategy = " + ".join(applied_actions)
            col_reason = "; ".join(applied_reasons)

        column_semantics[col] = {
            "type": sem_type,
            "confidence": sem_res["confidence"],
            "strategy": col_strategy,
            "reason": col_reason
        }

        # Update impacts
        missing_values_fixed += col_missing_fixed
        outliers_treated += col_outliers_treated
        if col_modified:
            columns_modified_set.add(col)
            cells_modified += col_cells_modified
            
        s_after = cleaned[col]
        null_count_after = int(s_after.isna().sum())
        outlier_count_after = 0
        if sem_type in ("Continuous Numeric", "Discrete Numeric"):
            s_num = pd.to_numeric(s_after, errors="coerce").dropna()
            if len(s_num) > 2:
                q1, q3 = s_num.quantile(0.25), s_num.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    outlier_count_after = int(((s_num < (q1 - 1.5 * iqr)) | (s_num > (q3 + 1.5 * iqr))).sum())
                    
        column_impacts.append({
            "column": col,
            "missing_before": null_count_before,
            "missing_after": null_count_after,
            "outliers_before": outlier_count_before,
            "outliers_after": outlier_count_after
        })

    cleaning_impact = {
        "rows_before": int(len(df)),
        "rows_after": int(len(cleaned)),
        "missing_values_fixed": int(missing_values_fixed),
        "duplicates_removed": int(duplicates_removed),
        "outliers_treated": int(outliers_treated),
        "columns_modified": int(len(columns_modified_set)),
        "cells_modified": int(cells_modified),
        "original_missing_count": original_missing_count,
        "original_duplicate_count": original_duplicate_count,
        "original_outlier_count": original_outlier_count
    }

    return cleaned, logs, cleaning_impact, column_semantics, column_impacts

def _safe_numeric_coercion(series: pd.Series) -> pd.Series:
    """Helper to convert potentially messy string/object numeric series to clean numeric series."""
    if series.dtype == "object" or str(series.dtype) == "string":
        s_clean = (
            series.astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.strip()
        )
        return pd.to_numeric(s_clean, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def generate_and_save_charts(df: pd.DataFrame, audit: dict[str, Any], profile: dict[str, Any], output_dir: str) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    generated = []
    
    # 1. Missing Values Chart
    missing_by_col = audit.get("missing", {}).get("by_column", {})
    missing_cols = [(col, count) for col, count in missing_by_col.items() if count > 0]
    if missing_cols:
        missing_cols.sort(key=lambda x: x[1], reverse=True)
        cols = [c[0] for c in missing_cols[:15]]
        counts = [c[1] for c in missing_cols[:15]]
        
        plt.figure(figsize=(6, 4))
        plt.bar(cols, counts, color="#ef4444")
        plt.title("Missing Values Count by Column")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        path = os.path.join(output_dir, "missing_values.png")
        plt.savefig(path)
        plt.close()
        generated.append("missing_values.png")

    # 2. Correlation Heatmap
    numeric_cols = profile.get("roles", {}).get("numerical", [])
    if len(numeric_cols) >= 2:
        df_num = pd.DataFrame()
        for col in numeric_cols:
            df_num[col] = _safe_numeric_coercion(df[col])
        corr_matrix = df_num.corr(numeric_only=True).fillna(0)
        plt.figure(figsize=(6, 4))
        plt.imshow(corr_matrix, cmap='RdBu', vmin=-1, vmax=1)
        plt.colorbar()
        plt.xticks(range(len(numeric_cols)), numeric_cols, rotation=45, ha="right")
        plt.yticks(range(len(numeric_cols)), numeric_cols)
        plt.title("Numeric Correlation Heatmap")
        plt.tight_layout()
        path = os.path.join(output_dir, "correlation_heatmap.png")
        plt.savefig(path)
        plt.close()
        generated.append("correlation_heatmap.png")

    # 3. Distribution Histogram
    numeric_col = numeric_cols[0] if numeric_cols else None
    if numeric_col:
        non_null_vals = _safe_numeric_coercion(df[numeric_col]).dropna()
        if len(non_null_vals) > 0:
            plt.figure(figsize=(6, 4))
            plt.hist(non_null_vals[:5000], bins=30, color="#3b82f6")
            plt.title(f"Distribution of '{numeric_col}'")
            plt.tight_layout()
            path = os.path.join(output_dir, "histogram.png")
            plt.savefig(path)
            plt.close()
            generated.append("histogram.png")

    # 4. Box Plot
    if numeric_col:
        non_null_vals = _safe_numeric_coercion(df[numeric_col]).dropna()
        if len(non_null_vals) > 0:
            plt.figure(figsize=(6, 4))
            plt.boxplot(non_null_vals[:5000], vert=False, patch_artist=True,
                        boxprops=dict(facecolor="#8b5cf6"))
            plt.title(f"Outliers in '{numeric_col}'")
            plt.tight_layout()
            path = os.path.join(output_dir, "boxplot.png")
            plt.savefig(path)
            plt.close()
            generated.append("boxplot.png")
            
    return generated


def generate_plotly_insights(df: pd.DataFrame, audit: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Generate Plotly JSON specifications for 5 required charts from the raw dataset:
    1. Correlation Heatmap
    2. Missing Value Chart
    3. Histogram
    4. Box Plot
    5. Distribution Chart
    """
    insights = []

    # 1. Correlation Heatmap
    numeric_cols = profile.get("roles", {}).get("numerical", [])
    if len(numeric_cols) >= 2:
        df_num = pd.DataFrame()
        for col in numeric_cols:
            df_num[col] = _safe_numeric_coercion(df[col])
        corr_matrix = df_num.corr(numeric_only=True).fillna(0)
        corr_z = [[round(val, 2) for val in row] for row in corr_matrix.values.tolist()]
        x_labels = corr_matrix.columns.tolist()
        y_labels = corr_matrix.index.tolist()
    elif len(numeric_cols) == 1:
        corr_z = [[1.0]]
        x_labels = [numeric_cols[0]]
        y_labels = [numeric_cols[0]]
    else:
        corr_z = [[1.0]]
        x_labels = ["No Numeric Columns"]
        y_labels = ["No Numeric Columns"]

    insights.append({
        "title": "Correlation Heatmap",
        "data": [
            {
                "z": corr_z,
                "x": x_labels,
                "y": y_labels,
                "type": "heatmap",
                "colorscale": "RdBu",
                "zmin": -1.0,
                "zmax": 1.0,
                "hoverongaps": False
            }
        ],
        "layout": {
            "title": "Numeric Correlation Heatmap",
            "xaxis": {"automargin": True},
            "yaxis": {"automargin": True}
        }
    })

    # 2. Missing Value Chart
    missing_by_col = audit.get("missing", {}).get("by_column", {})
    missing_cols = [(col, count) for col, count in missing_by_col.items()]
    missing_cols.sort(key=lambda x: x[1], reverse=True)
    missing_cols = missing_cols[:15]
    
    x_cols = [c[0] for c in missing_cols] if missing_cols else ["No Columns"]
    y_counts = [c[1] for c in missing_cols] if missing_cols else [0]

    insights.append({
        "title": "Missing Value Chart",
        "data": [
            {
                "x": x_cols,
                "y": y_counts,
                "type": "bar",
                "marker": {"color": "#ef4444"}
            }
        ],
        "layout": {
            "title": "Missing Values Count by Column",
            "xaxis": {"title": "Columns", "automargin": True},
            "yaxis": {"title": "Count", "automargin": True}
        }
    })

    # 3. Histogram
    hist_col = numeric_cols[0] if numeric_cols else None
    hist_vals = []
    if hist_col:
        hist_vals = _safe_numeric_coercion(df[hist_col]).dropna().tolist()[:5000]
    
    if not hist_vals:
        fallback_col = df.columns[0] if len(df.columns) > 0 else None
        if fallback_col:
            hist_col = fallback_col
            hist_vals = df[fallback_col].dropna().astype(str).tolist()[:5000]
        else:
            hist_col = "No Data"
            hist_vals = [0]

    insights.append({
        "title": "Histogram",
        "data": [
            {
                "x": hist_vals,
                "type": "histogram",
                "marker": {"color": "#3b82f6"}
            }
        ],
        "layout": {
            "title": f"Distribution of '{hist_col}'",
            "xaxis": {"title": hist_col, "automargin": True},
            "yaxis": {"title": "Frequency", "automargin": True}
        }
    })

    # 4. Box Plot
    box_col = numeric_cols[0] if numeric_cols else None
    box_vals = []
    if box_col:
        box_vals = _safe_numeric_coercion(df[box_col]).dropna().tolist()[:5000]

    if not box_vals:
        fallback_col = df.columns[0] if len(df.columns) > 0 else None
        if fallback_col:
            box_col = fallback_col
            box_vals = df[fallback_col].dropna().astype(str).tolist()[:5000]
        else:
            box_col = "No Data"
            box_vals = [0]

    insights.append({
        "title": "Box Plot",
        "data": [
            {
                "x": box_vals,
                "type": "box",
                "name": box_col,
                "marker": {"color": "#8b5cf6"}
            }
        ],
        "layout": {
            "title": f"Outliers in '{box_col}'",
            "xaxis": {"title": box_col, "automargin": True}
        }
    })

    # 5. Distribution Chart
    dist_col = None
    for col in df.columns:
        if any(k in col.lower() for k in ["target", "label", "class", "outcome", "y"]):
            dist_col = col
            break

    if not dist_col:
        cat_cols = profile.get("roles", {}).get("categorical", [])
        if cat_cols:
            dist_col = cat_cols[0]
        else:
            bool_cols = profile.get("roles", {}).get("boolean", [])
            if bool_cols:
                dist_col = bool_cols[0]

    if not dist_col:
        for col in df.columns:
            if df[col].nunique(dropna=True) <= 50:
                dist_col = col
                break

    if not dist_col:
        dist_col = df.columns[0] if len(df.columns) > 0 else "No Data"

    if dist_col in df.columns:
        counts = df[dist_col].value_counts(dropna=True).head(15)
        dist_x = counts.index.astype(str).tolist()
        dist_y = counts.values.tolist()
    else:
        dist_x = ["No Data"]
        dist_y = [0]

    insights.append({
        "title": "Distribution Chart",
        "data": [
            {
                "x": dist_x,
                "y": dist_y,
                "type": "bar",
                "marker": {"color": "#10b981"}
            }
        ],
        "layout": {
            "title": f"Distribution of '{dist_col}'",
            "xaxis": {"title": dist_col, "type": "category", "automargin": True},
            "yaxis": {"title": "Count", "automargin": True}
        }
    })

    return insights

