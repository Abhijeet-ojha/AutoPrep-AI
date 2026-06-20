from __future__ import annotations

import io
import json
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def read_dataset(file_name: str, content: bytes) -> tuple[pd.DataFrame, str]:
    lower = file_name.lower()
    if lower.endswith(".csv"):
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                return df, encoding
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode CSV encoding")
    if lower.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        return df, "binary-xlsx"
    if lower.endswith(".json"):
        data = json.loads(content.decode("utf-8"))
        df = pd.json_normalize(data)
        return df, "utf-8"
    raise ValueError("Unsupported file format. Use CSV, XLSX, or JSON")


def infer_column_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    if pd.api.types.is_numeric_dtype(series):
        return "numerical"

    non_null = series.dropna().astype(str)
    if non_null.empty:
        return "categorical"

    lower = non_null.str.lower()
    bool_tokens = {"true", "false", "yes", "no", "0", "1"}
    if lower.isin(bool_tokens).mean() > 0.9:
        return "boolean"

    parsed_dates = pd.to_datetime(non_null, errors="coerce", utc=True)
    if parsed_dates.notna().mean() > 0.8:
        return "date"

    avg_len = non_null.str.len().mean()
    if avg_len > 25:
        return "text"

    return "categorical"


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    columns = []
    type_buckets: dict[str, list[str]] = {
        "numerical": [],
        "categorical": [],
        "date": [],
        "boolean": [],
        "text": [],
    }

    for col in df.columns:
        s = df[col]
        inferred = infer_column_type(s)
        type_buckets[inferred].append(col)

        non_na = s.dropna()
        row_count = max(len(df), 1)
        missing_count = int(s.isna().sum())
        numeric = pd.to_numeric(s, errors="coerce")
        mode = None
        if not non_na.empty:
            mode_series = non_na.mode()
            mode = mode_series.iloc[0] if not mode_series.empty else None

        columns.append(
            {
                "column_name": col,
                "inferred_type": inferred,
                "missing_count": missing_count,
                "missing_percentage": round(missing_count * 100 / row_count, 2),
                "unique_values": int(s.nunique(dropna=True)),
                "cardinality": round(float(s.nunique(dropna=True) / row_count), 4),
                "min_value": non_na.min() if not non_na.empty else None,
                "max_value": non_na.max() if not non_na.empty else None,
                "mean": float(numeric.mean()) if numeric.notna().any() else None,
                "median": float(numeric.median()) if numeric.notna().any() else None,
                "mode": mode,
                "std_dev": float(numeric.std()) if numeric.notna().any() else None,
                "skewness": float(numeric.skew()) if numeric.notna().any() else None,
            }
        )

    return {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
        "column_profiles": columns,
        "type_buckets": type_buckets,
    }


def detect_quality_issues(df: pd.DataFrame) -> dict[str, Any]:
    missing_by_column = {col: int(df[col].isna().sum()) for col in df.columns}
    missing_by_row = int(df.isna().any(axis=1).sum())
    duplicate_rows = int(df.duplicated().sum())

    outliers: dict[str, dict[str, int]] = {}
    invalid_entries: dict[str, int] = {}
    inconsistent_formatting: dict[str, int] = {}

    for col in df.columns:
        s = df[col]
        numeric = pd.to_numeric(s, errors="coerce")
        if numeric.notna().sum() > 5:
            q1 = numeric.quantile(0.25)
            q3 = numeric.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                iqr_mask = (numeric < (q1 - 1.5 * iqr)) | (numeric > (q3 + 1.5 * iqr))
                z = np.abs(stats.zscore(numeric.fillna(numeric.median()), nan_policy="omit"))
                outliers[col] = {
                    "iqr": int(iqr_mask.sum()),
                    "zscore": int((z > 3).sum()),
                }

        if s.dtype == "object":
            trimmed = s.dropna().astype(str)
            if not trimmed.empty:
                inconsistent = int((trimmed != trimmed.str.strip()).sum())
                inconsistent += int((trimmed.str.lower() != trimmed).sum())
                inconsistent_formatting[col] = inconsistent

                if "email" in col.lower():
                    invalid_entries[col] = int(
                        (~trimmed.str.contains(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", regex=True)).sum()
                    )
                if "phone" in col.lower():
                    invalid_entries[col] = int(
                        (~trimmed.str.contains(r"^[+()0-9\-\s]{7,20}$", regex=True)).sum()
                    )

        if "age" in col.lower() and numeric.notna().any():
            invalid_entries[col] = int((numeric < 0).sum())

    class_imbalance = {}
    for col in df.columns:
        if df[col].nunique(dropna=True) <= 10:
            vc = df[col].value_counts(dropna=True)
            if len(vc) > 1:
                ratio = float(vc.max() / max(vc.min(), 1))
                if ratio > 2.5:
                    class_imbalance[col] = {"imbalance_ratio": round(ratio, 2), "distribution": vc.to_dict()}

    return {
        "missing_values": {"column_wise": missing_by_column, "row_wise": missing_by_row},
        "duplicates": {"duplicate_rows": duplicate_rows, "near_duplicates": 0},
        "outliers": outliers,
        "invalid_entries": invalid_entries,
        "inconsistent_formatting": inconsistent_formatting,
        "class_imbalance": class_imbalance,
    }


def ai_understanding(df: pd.DataFrame) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    row_count = max(len(df), 1)
    for col in df.columns:
        lower = col.lower()
        unique_ratio = float(df[col].nunique(dropna=True) / row_count)

        if lower.endswith("_id") or lower in {"id", "uuid"}:
            insights.append(
                {
                    "column": col,
                    "inference": "identifier",
                    "explanation": "Column naming and high cardinality strongly indicate an identifier field.",
                }
            )
            continue

        if "date" in lower or "time" in lower:
            insights.append(
                {
                    "column": col,
                    "inference": "time_feature",
                    "explanation": "Column name indicates temporal semantics useful for trend and seasonality features.",
                }
            )
            continue

        if unique_ratio > 0.95 and df[col].dtype == "object":
            insights.append(
                {
                    "column": col,
                    "inference": "potential_leakage_or_identifier",
                    "explanation": "Very high uniqueness often behaves like an ID and can leak record-level identity.",
                }
            )
            continue

        if df[col].nunique(dropna=True) <= 2:
            insights.append(
                {
                    "column": col,
                    "inference": "target_candidate",
                    "explanation": "Binary-like cardinality makes this a candidate target for classification tasks.",
                }
            )
            continue

        insights.append(
            {
                "column": col,
                "inference": "feature_candidate",
                "explanation": "Column has non-trivial variation and appears potentially useful as an ML feature.",
            }
        )

    return insights
