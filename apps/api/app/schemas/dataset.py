from typing import Any

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    dataset_id: str
    file_name: str
    rows: int
    columns: int
    memory_usage_bytes: int
    file_size_bytes: int
    encoding: str


class ColumnProfile(BaseModel):
    column_name: str
    inferred_type: str
    missing_count: int
    missing_percentage: float
    unique_values: int
    cardinality: float
    min_value: Any = None
    max_value: Any = None
    mean: float | None = None
    median: float | None = None
    mode: Any = None
    std_dev: float | None = None
    skewness: float | None = None


class Recommendation(BaseModel):
    column: str
    action: str
    confidence: float = Field(ge=0, le=100)
    explanation: str
    expected_impact: str


class CleaningRequest(BaseModel):
    actions: list[str]


class ChatRequest(BaseModel):
    question: str


class ScoreBreakdown(BaseModel):
    missing_values: int
    duplicates: int
    outliers: int
    invalid_entries: int
    class_imbalance: int
    consistency: int


class HealthScoreResponse(BaseModel):
    score: int
    breakdown: ScoreBreakdown
    improvement_suggestions: list[str]
