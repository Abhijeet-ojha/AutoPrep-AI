from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd

from app.utils.analysis import detect_quality_issues


def generate_cleaning_recommendations(df: pd.DataFrame) -> list[dict[str, Any]]:
    audit = detect_quality_issues(df)
    recommendations: list[dict[str, Any]] = []

    for col, missing in audit["missing_values"]["column_wise"].items():
        if missing == 0:
            continue
        s = df[col]
        numeric = pd.to_numeric(s, errors="coerce")
        if numeric.notna().sum() > 0:
            outlier_count = audit["outliers"].get(col, {}).get("iqr", 0)
            if outlier_count > 0:
                recommendations.append(
                    {
                        "column": col,
                        "action": "Median Imputation",
                        "confidence": 92,
                        "explanation": "Column has missing values and outliers. Median is robust against extreme values.",
                        "expected_impact": "Stabilizes distribution and reduces bias from extreme values.",
                    }
                )
            else:
                recommendations.append(
                    {
                        "column": col,
                        "action": "Mean Imputation",
                        "confidence": 85,
                        "explanation": "Numeric field with missing values and no heavy outlier signal.",
                        "expected_impact": "Preserves central tendency with minimal variance distortion.",
                    }
                )
        else:
            recommendations.append(
                {
                    "column": col,
                    "action": "Mode Imputation",
                    "confidence": 88,
                    "explanation": "Categorical field with missing values is best filled by dominant category.",
                    "expected_impact": "Maintains category consistency and avoids data loss.",
                }
            )

    for col, invalid in audit["invalid_entries"].items():
        if invalid > 0:
            recommendations.append(
                {
                    "column": col,
                    "action": "Fix Invalid Entries",
                    "confidence": 90,
                    "explanation": "Validation checks detected malformed values in this column.",
                    "expected_impact": "Improves semantic correctness and downstream model reliability.",
                }
            )

    if audit["duplicates"]["duplicate_rows"] > 0:
        recommendations.append(
            {
                "column": "__dataset__",
                "action": "Remove Duplicates",
                "confidence": 97,
                "explanation": "Duplicate rows were found and can skew training distribution.",
                "expected_impact": "Reduces over-representation and improves generalization.",
            }
        )

    return recommendations


def compute_health_score(audit: dict[str, Any]) -> dict[str, Any]:
    missing_total = sum(audit["missing_values"]["column_wise"].values())
    duplicates = audit["duplicates"]["duplicate_rows"]
    outliers = sum(v.get("iqr", 0) for v in audit["outliers"].values())
    invalids = sum(audit["invalid_entries"].values())
    imbalance = len(audit["class_imbalance"])
    consistency = sum(audit["inconsistent_formatting"].values())

    breakdown = {
        "missing_values": max(0, 25 - min(25, missing_total)),
        "duplicates": max(0, 25 - min(25, duplicates)),
        "outliers": max(0, 20 - min(20, outliers)),
        "invalid_entries": max(0, 10 - min(10, invalids)),
        "class_imbalance": max(0, 10 - min(10, imbalance * 3)),
        "consistency": max(0, 10 - min(10, consistency)),
    }
    score = int(sum(breakdown.values()))

    tips = []
    if breakdown["missing_values"] < 20:
        tips.append("Apply column-wise imputation for missing values.")
    if breakdown["duplicates"] < 20:
        tips.append("Remove exact and semantic duplicate records.")
    if breakdown["outliers"] < 15:
        tips.append("Review outliers using IQR/Z-score and winsorization.")
    if breakdown["consistency"] < 8:
        tips.append("Standardize text casing and trim whitespace.")

    return {"score": score, "breakdown": breakdown, "improvement_suggestions": tips}


def apply_cleaning_actions(df: pd.DataFrame, actions: list[str]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    cleaned = df.copy()
    logs: list[dict[str, Any]] = []

    if "remove_duplicates" in actions:
        before = len(cleaned)
        cleaned = cleaned.drop_duplicates()
        logs.append({"action": "remove_duplicates", "rows_removed": before - len(cleaned)})

    if "fill_missing" in actions:
        fills = {}
        for col in cleaned.columns:
            s = cleaned[col]
            if s.isna().sum() == 0:
                continue
            num = pd.to_numeric(s, errors="coerce")
            if num.notna().sum() > 0:
                value = float(num.median())
                cleaned[col] = num.fillna(value)
            else:
                mode = s.mode()
                value = mode.iloc[0] if not mode.empty else "Unknown"
                cleaned[col] = s.fillna(value)
            fills[col] = value
        logs.append({"action": "fill_missing", "details": fills})

    if "convert_dtypes" in actions:
        converted = []
        for col in cleaned.columns:
            original = cleaned[col]
            parsed = pd.to_datetime(original, errors="coerce")
            if parsed.notna().mean() > 0.8:
                cleaned[col] = parsed
                converted.append({"column": col, "to": "datetime"})
        logs.append({"action": "convert_dtypes", "details": converted})

    if "normalize" in actions:
        from sklearn.preprocessing import MinMaxScaler

        nums = cleaned.select_dtypes(include=["number"]).columns
        if len(nums) > 0:
            scaler = MinMaxScaler()
            cleaned[nums] = scaler.fit_transform(cleaned[nums])
            logs.append({"action": "normalize", "columns": list(nums)})

    if "standardize" in actions:
        from sklearn.preprocessing import StandardScaler

        nums = cleaned.select_dtypes(include=["number"]).columns
        if len(nums) > 0:
            scaler = StandardScaler()
            cleaned[nums] = scaler.fit_transform(cleaned[nums])
            logs.append({"action": "standardize", "columns": list(nums)})

    if "encode_categories" in actions:
        cats = cleaned.select_dtypes(include=["object", "category"]).columns
        if len(cats) > 0:
            cleaned = pd.get_dummies(cleaned, columns=list(cats), drop_first=False)
            logs.append({"action": "encode_categories", "columns": list(cats)})

    return cleaned, logs


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()
