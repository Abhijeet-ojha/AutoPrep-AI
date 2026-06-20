from __future__ import annotations

import io
import re
from collections import Counter
from datetime import datetime
from typing import Any

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

    if np.issubdtype(series.dropna().dtype, np.datetime64) or "date" in name or "time" in name:
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
        "numerical": [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().sum() > 0],
        "categorical": [c for c in df.columns if df[c].dtype == "object" and df[c].nunique(dropna=True) <= 50],
        "date": [c for c in df.columns if "date" in c.lower() or "time" in c.lower()],
        "boolean": [c for c in df.columns if df[c].dtype == "bool"],
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

    numeric_cols = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().sum() > 0]
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


def dataset_health_score(audit: dict[str, Any], total_rows: int) -> dict[str, Any]:
    total_rows = max(total_rows, 1)

    missing_rate = sum(audit["missing"]["by_column"].values()) / total_rows
    duplicate_rate = audit["duplicates"]["duplicate_rows"] / total_rows
    outlier_count = sum(audit["outliers"]["iqr"].values())
    outlier_rate = outlier_count / total_rows
    invalid_count = sum(i["count"] for i in audit["invalid_entries"]) if audit["invalid_entries"] else 0
    invalid_rate = invalid_count / total_rows

    scores = {
        "Missing Values": max(0, 25 - min(25, int(missing_rate * 3))),
        "Duplicates": max(0, 25 - min(25, int(duplicate_rate * 25))),
        "Outliers": max(0, 25 - min(25, int(outlier_rate * 5))),
        "Consistency": max(0, 25 - min(25, int(invalid_rate * 10))),
    }

    total = int(sum(scores.values()))

    suggestions = []
    if scores["Missing Values"] < 20:
        suggestions.append("Apply imputation and missingness indicators for affected columns.")
    if scores["Duplicates"] < 20:
        suggestions.append("Deduplicate records before model training.")
    if scores["Outliers"] < 20:
        suggestions.append("Winsorize/cap extreme values or apply robust scaling.")
    if scores["Consistency"] < 20:
        suggestions.append("Normalize categorical formats and validate rule-based fields.")

    return {"score": total, "breakdown": scores, "improvement_suggestions": suggestions}


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
        if s.nunique(dropna=True) <= 1:
            suggestions.append({"type": "drop_column", "column": c, "reason": "Constant column adds no predictive value."})
        if c.lower().endswith("_id") or c.lower() in {"id", "uuid", "customer_id", "user_id"}:
            suggestions.append({"type": "drop_column", "column": c, "reason": "Identifier column risks leakage and weak generalization."})
        if "date" in c.lower() or "time" in c.lower():
            suggestions.append(
                {
                    "type": "create_feature",
                    "column": c,
                    "reason": "Extract year/month/day/weekday from temporal fields for stronger signals.",
                }
            )

    cat_cols = [c for c in df.columns if df[c].dtype == "object"]
    for c in cat_cols:
        card = df[c].nunique(dropna=True)
        if card <= 15:
            suggestions.append({"type": "encoding", "column": c, "method": "one_hot", "reason": "Low-cardinality categorical feature."})
        else:
            suggestions.append({"type": "encoding", "column": c, "method": "target_or_frequency", "reason": "High-cardinality categorical feature."})

    num_cols = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().sum() > 0]
    for c in num_cols:
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
        "regression": any(pd.to_numeric(df[c], errors="coerce").notna().sum() > len(df) * 0.8 for c in df.columns),
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


def report_html(dataset_id: str, profile: dict[str, Any], audit: dict[str, Any], health: dict[str, Any], ml: dict[str, Any]) -> str:
    return f"""
    <html>
    <head><title>AutoPrep AI Report</title></head>
    <body>
        <h1>AutoPrep AI Report - {dataset_id}</h1>
        <h2>Dataset Summary</h2>
        <pre>{profile['summary']}</pre>
        <h2>Quality Audit</h2>
        <pre>{audit}</pre>
        <h2>Health Score</h2>
        <pre>{health}</pre>
        <h2>ML Readiness</h2>
        <pre>{ml}</pre>
    </body>
    </html>
    """.strip()
