"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="function")
def client():
    """Create a test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    import pandas as pd
    return pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'name': ['Alice', 'Bob', 'Charlie', None, 'Eve'],
        'age': [25, 30, None, 40, 35],
        'salary': [50000, 60000, 55000, 70000, 65000],
        'department': ['HR', 'IT', 'IT', 'HR', 'Finance']
    })


@pytest.fixture
def sample_csv_bytes(sample_dataframe):
    """Get CSV bytes from sample DataFrame."""
    return sample_dataframe.to_csv(index=False).encode('utf-8')
