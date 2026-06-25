import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from app.services.dataset_store import DatasetState
from app.services.analytics_engine import get_dataset_analytics, evaluate_analytics_query
from app.services.feature_analyzer import analyze_dataset_features
from app.services.ml_advisor import get_ml_recommendations
from app.services.query_planner import plan_query_mode
from app.services.conversation_context import resolve_contextual_question, update_conversation_context

@pytest.fixture
def mock_dataset_state(sample_dataframe):
    # Setup state
    state = DatasetState(
        dataset_id="test_session_id",
        file_name="mock_dataset.csv",
        file_size_bytes=1000,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow(),
        metadata={},
        file_path="test_session_id/cleaned.csv"
    )
    
    # Mock current_df property using a local dict cache or patch
    # We will override the property on the object instance
    type(state).current_df = property(lambda self: sample_dataframe)
    return state

def test_analytics_engine_computations(mock_dataset_state):
    analytics = get_dataset_analytics(mock_dataset_state)
    summary = analytics["summary"]
    cols_stats = analytics["columns"]
    
    assert summary["rows"] == 5
    assert summary["columns"] == 5
    assert summary["numeric_columns_count"] == 3  # id, age, salary
    assert summary["categorical_columns_count"] == 2  # name, department
    
    # Test column stats
    assert "age" in cols_stats
    assert cols_stats["age"]["type"] == "numeric"
    assert cols_stats["age"]["missing_count"] == 1
    
    assert "department" in cols_stats
    assert cols_stats["department"]["type"] == "categorical"
    assert cols_stats["department"]["cardinality"] == 3

def test_cache_correctness(mock_dataset_state):
    # Ensure cache is filled
    assert "cached_analytics" not in mock_dataset_state.metadata
    analytics = get_dataset_analytics(mock_dataset_state)
    assert "cached_analytics" in mock_dataset_state.metadata
    
    # Modify cache manually to verify it is returned on next call
    mock_dataset_state.metadata["cached_analytics"] = {"dummy": "data"}
    second_call = get_dataset_analytics(mock_dataset_state)
    assert second_call == {"dummy": "data"}

def test_feature_analyzer_diagnostics(sample_dataframe):
    # Add a constant column and a duplicate/correlated column
    df = sample_dataframe.copy()
    df["constant_col"] = 1.0
    df["salary_copy"] = df["salary"] * 2
    
    profile = {"columns": {}} # placeholder
    analysis = analyze_dataset_features(df, profile)
    
    assert "constant_col" in analysis["constant_columns"]
    assert "id" in analysis["identifiers"]
    
    # Multicollinearity check
    assert len(analysis["high_correlations"]) >= 1
    assert "salary" in analysis["multicollinear_features"]
    assert "salary_copy" in analysis["multicollinear_features"]

def test_ml_advisor_recommendations():
    profile = {
        "columns": [
            {"column": "age", "type": "numeric"},
            {"column": "salary", "type": "numeric"},
            {"column": "department", "type": "categorical"},
            {"column": "target_col", "type": "categorical"}
        ]
    }
    features_info = {
        "target_column": "target_col",
        "target_imbalance": "Balanced",
        "high_cardinality_columns": []
    }
    
    recs = get_ml_recommendations(profile, features_info)
    assert recs["task"] == "Supervised (Classification)"
    assert recs["problem_type"] == "Classification"
    assert any(m["model"] == "XGBoost Classifier" for m in recs["suggested_algorithms"])

def test_query_planner_modes():
    assert plan_query_mode("How many rows are in this dataset?") == "ANALYTICS"
    assert plan_query_mode("Explain the outlier distribution of Age") == "INSIGHT"
    assert plan_query_mode("Recommend models for classifying target") == "RECOMMENDATION"
    assert plan_query_mode("Compare this dataset with Titanic") == "COMPARISON"
    assert plan_query_mode("Hello!") == "GENERAL"

def test_conversation_context_resolution():
    context_dict = {
        "previous_comparison_dataset": "Iris",
        "previous_intent": "Comparison"
    }
    resolved = resolve_contextual_question("What about Titanic?", context_dict)
    assert resolved == "Compare the uploaded dataset with Titanic"
    assert context_dict["previous_comparison_dataset"] == "Titanic"
    
    # Stats resolution
    context_dict2 = {
        "last_statistic_metric": "mean",
        "previous_intent": "Statistics"
    }
    resolved2 = resolve_contextual_question("Show the same for Age", context_dict2)
    assert resolved2 == "What is the mean of Age?"

def test_analytics_query_direct_evaluation(mock_dataset_state):
    analytics = get_dataset_analytics(mock_dataset_state)
    df = mock_dataset_state.current_df
    
    ans1 = evaluate_analytics_query("how many rows are there?", df, analytics)
    assert "5" in ans1
    
    ans2 = evaluate_analytics_query("show missing values in age", df, analytics)
    assert "age" in ans2.lower()
    assert "1" in ans2
