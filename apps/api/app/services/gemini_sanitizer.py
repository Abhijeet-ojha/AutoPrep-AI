import re
import pandas as pd
from typing import Any

MAX_TEXT_LENGTH = 10000
MAX_LIST_LENGTH = 100


def sanitize_for_gemini(payload: Any) -> Any:
    """
    Acts as a privacy firewall before any Gemini request.
    Recursively inspects the payload and raises ValueError if raw rows,
    DataFrames, CSV tables, or oversized content is detected.
    """
    _check_value(payload)
    return payload


def _check_value(val: Any):
    # 1. Block raw pandas structures
    if isinstance(val, (pd.DataFrame, pd.Series)):
        raise ValueError("Pandas DataFrames and Series objects are strictly forbidden in Gemini payloads.")

    # 2. Block string dumps that exceed length or match tabular structures
    if isinstance(val, str):
        if len(val) > MAX_TEXT_LENGTH:
            raise ValueError(f"String length {len(val)} exceeds the privacy threshold of {MAX_TEXT_LENGTH} characters.")
        
        # Check for CSV formatting patterns (multiple lines with several commas)
        lines = [line.strip() for line in val.splitlines() if line.strip()]
        if len(lines) >= 3:
            comma_count_lines = [line.count(",") for line in lines[:5]]
            if all(cc >= 2 for cc in comma_count_lines) and len(comma_count_lines) >= 3:
                raise ValueError("Tabular CSV content format detected in prompt/payload string.")
                
        # Check for raw JSON row list patterns e.g. [{"a": 1}, {"a": 2}]
        trimmed = val.strip()
        if trimmed.startswith("[") and trimmed.endswith("]"):
            if re.search(r'\{\s*".*?"\s*:', trimmed):
                raise ValueError("JSON records array serialization format detected in prompt/payload string.")

    # 3. Block oversized lists
    elif isinstance(val, list):
        if len(val) > MAX_LIST_LENGTH:
            raise ValueError(f"List length {len(val)} exceeds the privacy threshold of {MAX_LIST_LENGTH} items.")
        for item in val:
            _check_value(item)

    # 4. Block oversized or structured dicts representing data tables
    elif isinstance(val, dict):
        if len(val) > MAX_LIST_LENGTH:
            raise ValueError(f"Dictionary cardinality {len(val)} exceeds the privacy threshold of {MAX_LIST_LENGTH} keys.")
            
        # Detect DataFrame JSON splits/records structure (e.g. {"columns": [], "data": []})
        if "columns" in val and "data" in val and isinstance(val["data"], list):
            raise ValueError("Serialized DataFrame JSON structure detected in payload dictionary.")
            
        for k, v in val.items():
            _check_value(v)
