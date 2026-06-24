import pytest
import pandas as pd
import numpy as np
from app.services.analysis_service import (
    infer_semantic_type,
    standardize_boolean_series,
    auto_clean_dataset
)
from app.core.config import settings

def test_boolean_imputation_and_detection():
    # 1. Yes/No boolean detection
    col_yes_no = pd.Series(["Yes", "No", "Yes", np.nan, "No"])
    res = infer_semantic_type("Discount", col_yes_no)
    assert res["type"] == "Boolean"
    assert res["confidence"] >= 0.70
    
    # 2. 1/0 boolean detection
    col_binary = pd.Series([1, 0, 1, 1, 0])
    res_bin = infer_semantic_type("IsActive", col_binary)
    assert res_bin["type"] == "Boolean"

    # Imputation of boolean with Mode
    # Added 'id' column to prevent drop_duplicates from dropping any rows
    df_bool = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "bool_col": ["Yes", "No", "Yes", np.nan, "Yes"]
    })
    cleaned_df, logs, impact, semantics, col_impacts = auto_clean_dataset(df_bool)
    assert semantics["bool_col"]["type"] == "Boolean"
    # Mode should be True (Yes maps to True)
    assert cleaned_df["bool_col"].iloc[3] == True
    # Dtype preservation (boolean)
    assert str(cleaned_df["bool_col"].dtype) == "boolean"


def test_identifier_detection():
    # Identifier uniqueness ratio detection
    # Name pattern id_keywords + high uniqueness ratio > 0.80
    col_id = pd.Series([f"ID_{i}" for i in range(100)])
    res = infer_semantic_type("customer_id", col_id)
    assert res["type"] == "Identifier"
    assert res["confidence"] >= 0.70

    # Uniqueness ratio > 0.50 but not Identifier -> High Cardinality Categorical
    col_prod = pd.Series([f"Product_{i%60}" for i in range(100)]) # 60 unique in 100 rows -> unique_ratio = 0.60
    res_prod = infer_semantic_type("Product_Name", col_prod)
    assert res_prod["type"] == "High Cardinality Categorical"


def test_datetime_handling():
    # Datetime forward/backward and median date handling
    # Low missingness (<= 10%): need 10 rows with 1 null to trigger ffill/bfill path
    dates = ["2026-01-01", "2026-01-02", np.nan, "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-10"]
    df_date_low = pd.DataFrame({"id": list(range(10)), "date_col": dates})
    # Safe Datetime parsing (parsed ratio > 0.80)
    res = infer_semantic_type("OrderDate", df_date_low["date_col"])
    assert res["type"] == "DateTime"

    # Low missingness (<= 10%) -> ffill/bfill
    cleaned_df, _, _, semantics, _ = auto_clean_dataset(df_date_low)
    assert semantics["date_col"]["type"] == "DateTime"
    assert pd.to_datetime(cleaned_df["date_col"].iloc[2]) == pd.to_datetime("2026-01-02")

    # High missingness (> 10%) -> Median date imputation
    dates_high = ["2026-01-01", "2026-01-10", np.nan, np.nan, "2026-01-19"] # 2/5 missing = 40%
    df_date_high = pd.DataFrame({"id": [1, 2, 3, 4, 5], "date_col": dates_high})
    cleaned_df_high, _, _, _, _ = auto_clean_dataset(df_date_high)
    # Median of 2026-01-01, 2026-01-10, 2026-01-19 is 2026-01-10
    assert pd.to_datetime(cleaned_df_high["date_col"].iloc[2]) == pd.to_datetime("2026-01-10")


def test_text_column_handling():
    # Text column handling (never using mode, fills with "Unknown")
    # Long text (avg length > 35)
    text_data = [
        "This is a very long description for item alpha",
        "This is another extremely long description for item beta",
        np.nan,
        "Yet another long string to satisfy the average length constraint",
        "A final long sentence that goes on and on to exceed thirty-five characters"
    ]
    df_text = pd.DataFrame({"id": [1, 2, 3, 4, 5], "desc_col": text_data})
    res = infer_semantic_type("desc_col", df_text["desc_col"])
    assert res["type"] == "Free Text"
    
    cleaned_df, _, _, semantics, _ = auto_clean_dataset(df_text)
    assert semantics["desc_col"]["type"] == "Free Text"
    # Should fill with "Unknown", not Mode
    assert cleaned_df["desc_col"].iloc[2] == "Unknown"


def test_numeric_imputation_and_outliers():
    # 1. Mean vs Median selection for skewed numeric distributions (skewness > 1.5)
    skewed_data = [1.0, 1.2, 1.1, 1.3, 100.0, np.nan] # Mean is 20.94, Median is 1.2
    df_skewed = pd.DataFrame({"id": [1, 2, 3, 4, 5, 6], "num_col": skewed_data})
    cleaned_df, logs, impact, semantics, col_impacts = auto_clean_dataset(df_skewed)
    assert semantics["num_col"]["type"] == "Continuous Numeric"
    # Skewed -> Should fill with Median (1.2)
    assert abs(cleaned_df["num_col"].iloc[5] - 1.2) < 1e-4

    # 2. Normal distribution -> Mean imputation
    normal_data = [10.0, 11.0, 9.0, 10.5, 9.5, np.nan]
    df_normal = pd.DataFrame({"id": [1, 2, 3, 4, 5, 6], "num_col": normal_data})
    cleaned_df_norm, _, _, _, _ = auto_clean_dataset(df_normal)
    # Mean of 10, 11, 9, 10.5, 9.5 is 10.0
    assert abs(cleaned_df_norm["num_col"].iloc[5] - 10.0) < 1e-4

    # 3. IQR outlier capping vs Z-score outlier capping
    original_strategy = settings.outlier_strategy
    try:
        # Check 'cap' strategy
        settings.outlier_strategy = "cap"
        df_outliers = pd.DataFrame({"id": [1, 2, 3, 4, 5, 6, 7], "col": [1, 2, 1, 2, 1, 2, 100]}) # IQR outlier capping
        cleaned_df_cap, logs_cap, _, _, _ = auto_clean_dataset(df_outliers)
        assert cleaned_df_cap["col"].iloc[6] < 100 # Capped

        # Check 'remove' strategy
        settings.outlier_strategy = "remove"
        cleaned_df_rem, logs_rem, _, _, _ = auto_clean_dataset(df_outliers)
        assert len(cleaned_df_rem) < len(df_outliers) # Outlier row removed

        # Check 'flag' strategy
        settings.outlier_strategy = "flag"
        cleaned_df_flag, logs_flag, _, _, _ = auto_clean_dataset(df_outliers)
        assert len(cleaned_df_flag) == len(df_outliers)
        assert cleaned_df_flag["col"].iloc[6] == 100 # Left untouched, but log entry added
    finally:
        settings.outlier_strategy = original_strategy


def test_confidence_threshold_and_fallback():
    # If confidence < 0.70, then type = "Unknown", skip aggressive cleaning, add warning log
    mixed_col = pd.Series([1, "Approved", True, "Pending"])
    res = infer_semantic_type("Status", mixed_col)
    assert res["type"] == "Unknown"
    assert res["confidence"] == 0.0
    assert res["reason"] == "Unable to determine semantic type"

    df_mixed = pd.DataFrame({"id": [1, 2, 3, 4, 5], "Status": [1, "Approved", True, "Pending", np.nan]})
    cleaned_df, logs, impact, semantics, col_impacts = auto_clean_dataset(df_mixed)
    assert semantics["Status"]["type"] == "Unknown"
    # Unmodified value (np.nan is still np.nan)
    assert pd.isna(cleaned_df["Status"].iloc[4])
    # Warning logged in logs
    warning_logs = [log for log in logs if log["column"] == "Status" and log["semantic_type"] == "Unknown"]
    assert len(warning_logs) > 0
    assert "Warning" in warning_logs[0]["reason"]


def test_original_metrics_and_column_impacts():
    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "num": [10.0, 11.0, np.nan, 9.0, 100.0],
        "cat": ["A", "B", "A", np.nan, "B"]
    })
    # Duplicates to be removed
    df_dup = pd.concat([df, df.iloc[[0]]], ignore_index=True) # 6 rows, 1 exact duplicate

    cleaned_df, logs, impact, semantics, col_impacts = auto_clean_dataset(df_dup)
    
    # Check original metrics tracked
    assert impact["original_missing_count"] == 2
    assert impact["original_duplicate_count"] == 1
    assert impact["original_outlier_count"] == 1

    # Check column-level impacts before/after
    num_impact = next(c for c in col_impacts if c["column"] == "num")
    assert num_impact["missing_before"] == 1
    assert num_impact["missing_after"] == 0
    assert num_impact["outliers_before"] == 1
    assert num_impact["outliers_after"] == 0


def test_edge_cases():
    # 1. 100% missing column
    df_empty = pd.DataFrame({"id": [1, 2, 3], "empty": [np.nan, np.nan, np.nan]})
    cleaned, _, _, semantics, _ = auto_clean_dataset(df_empty)
    assert semantics["empty"]["type"] == "Unknown"
    assert pd.isna(cleaned["empty"].iloc[0])

    # 2. Constant-value column
    df_constant = pd.DataFrame({"id": [1, 2, 3, 4], "const": [1, 1, 1, 1]})
    cleaned, _, _, semantics, _ = auto_clean_dataset(df_constant)
    assert semantics["const"]["type"] in ("Discrete Numeric", "Categorical")

    # 3. Mixed boolean/text column
    df_mixed_bool = pd.DataFrame({"id": [1, 2, 3, 4, 5], "mixed": ["True", "False", "Maybe", "Yes", np.nan]})
    cleaned, _, _, semantics, _ = auto_clean_dataset(df_mixed_bool)
    assert semantics["mixed"]["type"] == "Categorical"

    # 4. Datetime with invalid strings
    df_date_invalid = pd.DataFrame({"id": [1, 2, 3, 4, 5], "dates": ["2026-01-01", "invalid_date_here", "2026-01-03", "not_a_date", np.nan]})
    cleaned, _, _, semantics, _ = auto_clean_dataset(df_date_invalid)
    assert semantics["dates"]["type"] == "Categorical"

    # 5. Identifier column with missing values
    df_id_missing = pd.DataFrame({"id": ["id_1", "id_2", np.nan, "id_4"]})
    cleaned, _, _, semantics, _ = auto_clean_dataset(df_id_missing)
    assert semantics["id"]["type"] == "Identifier"

    # 6. Dataset containing only categorical columns
    df_only_cat = pd.DataFrame({"id": [1, 2, 3], "c1": ["A", "B", "A"], "c2": ["X", "Y", "Z"]})
    cleaned, _, _, semantics, _ = auto_clean_dataset(df_only_cat)
    assert semantics["c1"]["type"] == "Categorical"
    assert semantics["c2"]["type"] == "Categorical"

    # 7. Dataset containing only numeric columns
    df_only_num = pd.DataFrame({"id": [1, 2, 3], "n1": [1.1, 2.2, 3.3], "n2": [10, 20, 30]})
    cleaned, _, _, semantics, _ = auto_clean_dataset(df_only_num)
    assert semantics["n1"]["type"] == "Continuous Numeric"
    assert semantics["n2"]["type"] == "Discrete Numeric"


def test_regression_dataset_and_pdf(tmp_path):
    # Messy regression dataset containing different data types, missing values, currencies, etc.
    df = pd.DataFrame({
        "Customer ID": ["id_1", "id_2", "id_3", "id_4", "id_5", "id_6", "id_7", "id_8", "id_9", "id_10"],
        "Price Per Unit": ["$1,200.50", " $450.00 ", "1,500", "250.75", np.nan, "$80.00", "$99.99", "$120.00", "$300.00", np.nan],
        "Quantity": [1, 2, 5, 10, np.nan, 3, 4, 2, 1, 1],
        "Total Spent": ["$1,200.50", "$900.00", "$7,500.00", "$2,507.50", np.nan, "$240.00", "$399.96", "$240.00", "$300.00", np.nan],
        "Discount Applied": ["Yes", "No", np.nan, "Yes", "No", "No", "Yes", np.nan, "No", "Yes"],
        "Join Date": ["2026-01-01", "2026-01-02", np.nan, "2026-01-04", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-10"]
    })
    
    # 1. Validate Semantic Classification
    from app.services.analysis_service import (
        profile_dataset,
        quality_audit,
        dataset_health_score,
        auto_clean_dataset,
        generate_pdf_report
    )
    
    # Check raw classification
    res_cust = infer_semantic_type("Customer ID", df["Customer ID"])
    res_price = infer_semantic_type("Price Per Unit", df["Price Per Unit"])
    res_qty = infer_semantic_type("Quantity", df["Quantity"])
    res_spent = infer_semantic_type("Total Spent", df["Total Spent"])
    res_disc = infer_semantic_type("Discount Applied", df["Discount Applied"])
    
    assert res_cust["type"] == "Identifier"
    assert res_price["type"] == "Continuous Numeric"
    assert res_qty["type"] == "Discrete Numeric"
    assert res_spent["type"] == "Continuous Numeric"
    assert res_disc["type"] == "Boolean"

    # 2. Check Health Scores (Raw vs Cleaned)
    raw_profile = profile_dataset(df)
    raw_audit = quality_audit(df)
    raw_health = dataset_health_score(raw_audit, raw_profile, len(df))
    
    cleaned_df, cleaning_logs, cleaning_impact, column_semantics, column_impacts = auto_clean_dataset(df)
    
    cleaned_profile = profile_dataset(cleaned_df)
    cleaned_audit = quality_audit(cleaned_df)
    cleaned_health = dataset_health_score(cleaned_audit, cleaned_profile, len(cleaned_df))
    
    # Verify health score improves
    assert cleaned_health["score"] > raw_health["score"]
    
    # Verify raw health is capped or reduced due to missingness/errors
    assert raw_health["score"] < 100
    
    # 3. Verify PDF generation compiles successfully
    charts_dir = str(tmp_path / "charts")
    import os
    os.makedirs(charts_dir, exist_ok=True)
    
    from app.services.analysis_service import generate_and_save_charts, ml_readiness, feature_engineering_suggestions
    generate_and_save_charts(df, raw_audit, raw_profile, charts_dir)
    
    fe_suggestions = feature_engineering_suggestions(cleaned_df)
    readiness = ml_readiness(cleaned_df, cleaned_audit, fe_suggestions)
    
    pdf_output = os.path.join(charts_dir, "report.pdf")
    generate_pdf_report(
        session_id="test_session",
        output_path=pdf_output,
        profile=raw_profile,
        audit=raw_audit,
        health=raw_health,
        ml=readiness,
        charts_dir=charts_dir,
        cleaning_logs=cleaning_logs,
        rows_before=len(df),
        rows_after=len(cleaned_df),
        column_semantics=column_semantics,
        cleaning_impact=cleaning_impact,
        cleaned_health=cleaned_health
    )
    
    assert os.path.exists(pdf_output)
    assert os.path.getsize(pdf_output) > 0
