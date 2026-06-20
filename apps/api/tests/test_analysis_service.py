"""Tests for analysis service."""

import pytest
import pandas as pd

from app.services.analysis_service import (
    infer_column_role,
    profile_dataset,
    quality_audit,
    build_cleaning_recommendations,
    dataset_health_score,
)


def test_infer_column_role_identifier():
    """Test column role inference for identifier columns."""
    series = pd.Series([1, 2, 3, 4, 5])
    result = infer_column_role("customer_id", series)
    
    assert result["role"] == "identifier"
    assert result["confidence"] > 0.9


def test_infer_column_role_target():
    """Test column role inference for target columns."""
    series = pd.Series([0, 1, 0, 1, 1])
    result = infer_column_role("target", series)
    
    assert result["role"] == "target_candidate"
    assert result["confidence"] > 0.8


def test_profile_dataset(sample_dataframe):
    """Test dataset profiling."""
    profile = profile_dataset(sample_dataframe)
    
    assert "summary" in profile
    assert profile["summary"]["rows"] == 5
    assert profile["summary"]["columns"] == 5
    
    assert "roles" in profile
    assert "columns" in profile
    assert len(profile["columns"]) == 5


def test_quality_audit(sample_dataframe):
    """Test quality audit."""
    audit = quality_audit(sample_dataframe)
    
    assert "missing" in audit
    assert audit["missing"]["by_column"]["name"] == 1
    assert audit["missing"]["by_column"]["age"] == 1
    
    assert "duplicates" in audit
    assert "outliers" in audit


def test_build_cleaning_recommendations(sample_dataframe):
    """Test cleaning recommendation generation."""
    audit = quality_audit(sample_dataframe)
    recs = build_cleaning_recommendations(sample_dataframe, audit)
    
    assert len(recs) > 0
    assert all("recommended_action" in rec for rec in recs)
    assert all("confidence" in rec for rec in recs)


def test_dataset_health_score(sample_dataframe):
    """Test health score calculation."""
    audit = quality_audit(sample_dataframe)
    health = dataset_health_score(audit, len(sample_dataframe))
    
    assert "score" in health
    assert 0 <= health["score"] <= 100
    assert "breakdown" in health
    assert len(health["breakdown"]) == 4
