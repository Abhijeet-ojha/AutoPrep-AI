from __future__ import annotations

from typing import Any


def answer_question(question: str, metadata: dict[str, Any]) -> str:
    q = question.lower()

    if "summarize" in q or "summary" in q:
        return (
            f"Dataset has {metadata.get('rows', 0)} rows and {metadata.get('columns', 0)} columns. "
            f"Health score is {metadata.get('health_score', 'N/A')} and top issues include missing values and outliers."
        )

    if "remove" in q and "column" in q:
        candidates = metadata.get("drop_candidates", [])
        if candidates:
            return f"Consider dropping: {', '.join(candidates[:5])}. They appear identifier-like or near-constant."
        return "No strong drop candidates detected yet."

    if "median" in q:
        return "Median imputation was used where numeric columns showed outliers, because it is robust to extremes."

    if "correlation" in q:
        pairs = metadata.get("top_correlations", [])
        if pairs:
            best = pairs[0]
            return f"Top observed correlation is between {best['a']} and {best['b']} ({best['value']})."
        return "No strong correlations computed yet."

    return "I can explain cleaning decisions, quality issues, feature suggestions, and ML readiness if you ask a specific question."
