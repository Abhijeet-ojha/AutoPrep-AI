import os
import logging
import pandas as pd
import numpy as np
from app.services.dataset_store import DatasetState

logger = logging.getLogger(__name__)

def get_dataset_analytics(state: DatasetState) -> dict:
    """
    Perform statistical computation of dataset summaries and column-level properties.
    Caches the calculations in state.metadata["cached_analytics"].
    """
    if "cached_analytics" in state.metadata:
        return state.metadata["cached_analytics"]

    logger.info(f"Computing analytics for dataset {state.dataset_id}...")
    df = state.current_df
    num_rows = len(df)
    num_cols = len(df.columns)
    
    # 1. Dataset summary metrics
    memory_usage = int(df.memory_usage(deep=True).sum())
    duplicates = int(df.duplicated().sum())
    missing_values = int(df.isna().sum().sum())
    missing_pct = float((missing_values / (num_rows * num_cols)) * 100) if num_rows and num_cols else 0.0
    
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
    categorical_cols = list(df.select_dtypes(include=[object, "category", "bool"]).columns)
    
    # Detect datetime columns based on name and parseable fraction
    datetime_cols = []
    for col in df.columns:
        if df[col].dtype in [np.datetime64, "datetime64[ns]"]:
            datetime_cols.append(col)
        elif "date" in col.lower() or "time" in col.lower():
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() > 0.5 * num_rows:
                    datetime_cols.append(col)
            except Exception:
                pass

    summary = {
        "rows": num_rows,
        "columns": num_cols,
        "memory_usage_bytes": memory_usage,
        "duplicate_rows": duplicates,
        "missing_values": missing_values,
        "missing_percentage": round(missing_pct, 2),
        "numeric_columns_count": len(numeric_cols),
        "categorical_columns_count": len(categorical_cols),
        "datetime_columns_count": len(datetime_cols),
    }

    # 2. Column statistics
    columns_stats = {}
    
    # Numeric column stats
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        
        q25 = float(series.quantile(0.25))
        q50 = float(series.quantile(0.50))
        q75 = float(series.quantile(0.75))
        iqr = q75 - q25
        
        lower_bound = q25 - 1.5 * iqr
        upper_bound = q75 + 1.5 * iqr
        outliers = int(((df[col] < lower_bound) | (df[col] > upper_bound)).sum())
        zeros = int((df[col] == 0).sum())
        
        try:
            skew = float(series.skew())
        except Exception:
            skew = 0.0
            
        try:
            kurt = float(series.kurt())
        except Exception:
            kurt = 0.0
            
        mode_val = series.mode()
        mode = float(mode_val.iloc[0]) if not mode_val.empty else 0.0

        columns_stats[col] = {
            "type": "numeric",
            "mean": float(series.mean()),
            "median": float(series.median()),
            "mode": mode,
            "std": float(series.std()) if len(series) > 1 else 0.0,
            "variance": float(series.var()) if len(series) > 1 else 0.0,
            "min": float(series.min()),
            "max": float(series.max()),
            "q25": q25,
            "q50": q50,
            "q75": q75,
            "iqr": iqr,
            "skewness": round(skew, 2) if not np.isnan(skew) else 0.0,
            "kurtosis": round(kurt, 2) if not np.isnan(kurt) else 0.0,
            "outliers_count": outliers,
            "zeros_count": zeros,
            "missing_count": int(df[col].isna().sum()),
            "missing_pct": round(float(df[col].isna().sum() / num_rows) * 100, 2) if num_rows else 0.0
        }

    # Categorical column stats
    for col in categorical_cols:
        series = df[col].dropna()
        cardinality = int(df[col].nunique())
        top_vc = series.value_counts()
        
        top_values = []
        for val, freq in top_vc.head(5).items():
            top_values.append({
                "value": str(val),
                "count": int(freq),
                "pct": round(float(freq / num_rows) * 100, 2) if num_rows else 0.0
            })
            
        entropy = 0.0
        if not series.empty:
            vc_norm = series.value_counts(normalize=True)
            entropy = float(-np.sum(vc_norm * np.log2(vc_norm + 1e-12)))

        imbalance = "Balanced"
        if cardinality > 1 and not top_vc.empty:
            ratio = top_vc.iloc[0] / max(1, top_vc.iloc[-1])
            if ratio > 3.0:
                imbalance = f"Severe Imbalance ({ratio:.1f}:1)"
            elif ratio > 1.5:
                imbalance = f"Moderate Imbalance ({ratio:.1f}:1)"

        columns_stats[col] = {
            "type": "categorical",
            "cardinality": cardinality,
            "top_values": top_values,
            "entropy": round(entropy, 2),
            "class_imbalance": imbalance,
            "missing_count": int(df[col].isna().sum()),
            "missing_pct": round(float(df[col].isna().sum() / num_rows) * 100, 2) if num_rows else 0.0
        }

    # Datetime column stats
    for col in datetime_cols:
        series = pd.to_datetime(df[col], errors="coerce").dropna()
        if series.empty:
            continue
            
        min_date = series.min()
        max_date = series.max()
        span_days = int((max_date - min_date).days)
        
        missing_dates = 0
        if span_days > 1 and span_days < 10000:
            expected_range = pd.date_range(start=min_date, end=max_date, freq='D')
            actual_dates = set(series.dt.date)
            missing_dates = int(sum(1 for d in expected_range if d.date() not in actual_dates))

        columns_stats[col] = {
            "type": "datetime",
            "min_date": min_date.isoformat(),
            "max_date": max_date.isoformat(),
            "date_span_days": span_days,
            "missing_dates_estimate": missing_dates,
            "missing_count": int(df[col].isna().sum()),
            "missing_pct": round(float(df[col].isna().sum() / num_rows) * 100, 2) if num_rows else 0.0
        }

    analytics = {
        "summary": summary,
        "columns": columns_stats,
    }
    state.metadata["cached_analytics"] = analytics
    return analytics

def evaluate_analytics_query(question: str, df: pd.DataFrame, analytics: dict) -> str:
    """
    Directly answer statistical/size queries from computed analytics or DataFrame,
    bypassing the LLM entirely.
    """
    q = question.lower()
    summary = analytics.get("summary", {})
    cols_stats = analytics.get("columns", {})
    
    # 1. Dataset size / shape
    if any(k in q for k in ["how many rows", "row count", "number of rows"]):
        return f"The dataset has a total of **{summary.get('rows')}** rows."
    if any(k in q for k in ["how many columns", "column count", "number of columns"]):
        return f"The dataset has a total of **{summary.get('columns')}** columns."
    if "shape" in q or "size" in q:
        return f"The dataset dimensions are **{summary.get('rows')}** rows and **{summary.get('columns')}** columns."
        
    # 2. Duplicates
    if "duplicate" in q:
        return f"The dataset contains **{summary.get('duplicate_rows')}** duplicate rows."
        
    # 3. Missing values
    for col in df.columns:
        if col.lower() in q and any(k in q for k in ["missing", "null", "nan"]):
            col_stat = cols_stats.get(col, {})
            missing = col_stat.get("missing_count", 0)
            pct = col_stat.get("missing_pct", 0.0)
            return f"Column **{col}** has **{missing}** missing values ({pct:.2f}% of total rows)."
            
    if any(k in q for k in ["missing", "null", "nan"]):
        return f"The dataset contains a total of **{summary.get('missing_values')}** missing values (approx. **{summary.get('missing_percentage')}%** of all cells)."
        
    # 4. Outliers
    if "outlier" in q:
        total_outliers = sum(info.get("outliers_count", 0) for info in cols_stats.values() if isinstance(info, dict) and "outliers_count" in info)
        return f"AutoPrep AI detected a total of **{total_outliers}** outliers in the dataset using the IQR method (1.5 IQR threshold)."

    # 5. List column datatypes
    if any(k in q for k in ["datatype", "data type", "list columns", "show columns", "column types"]):
        resp = "### Column Schema Profile\n\n"
        resp += "| Column Name | Type | Missing Count | Missing % |\n"
        resp += "| :--- | :--- | :--- | :--- |\n"
        for col, info in cols_stats.items():
            resp += f"| **{col}** | {info.get('type', 'unknown')} | {info.get('missing_count', 0)} | {info.get('missing_pct', 0.0):.1f}% |\n"
        return resp
        
    # 6. Specific Column Metric (mean, average, median, std, variance, min, max, etc.)
    metrics_map = {
        "mean": "mean",
        "average": "mean",
        "median": "median",
        "mode": "mode",
        "standard deviation": "std",
        "std": "std",
        "variance": "variance",
        "min": "min",
        "max": "max",
        "skewness": "skewness",
        "kurtosis": "kurtosis",
        "outlier": "outliers_count",
        "zero": "zeros_count"
    }
    
    for metric_kw, stat_key in metrics_map.items():
        if metric_kw in q:
            for col in df.columns:
                if col.lower() in q:
                    col_stat = cols_stats.get(col, {})
                    if col_stat and stat_key in col_stat:
                        val = col_stat[stat_key]
                        return f"The calculated **{metric_kw}** of column **{col}** is **{val}**."
                        
    return "I found statistical indicators in your question, but could not map them to a specific column or summary metric. Please mention the specific column name."
