"""
Gemini Service Layer - AI-powered explanations, insights, and conversational intelligence.

This service uses Gemini 2.5 Flash for:
- Explanations and recommendations
- Dataset insights and executive summaries
- Conversational analytics
- ML readiness reasoning

It does NOT perform deterministic data processing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure Gemini
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)


class GeminiService:
    """Service for interacting with Gemini 2.5 Flash API."""

    def __init__(self):
        self.model_name = "gemini-2.0-flash-exp"
        self.generation_config = {
            "temperature": 0.3,  # Lower temperature for more deterministic outputs
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
    def _get_model(self):
        """Get configured Gemini model."""
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        return genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _generate_with_retry(self, prompt: str) -> str:
        """Generate text with automatic retry on failure."""
        try:
            model = self._get_model()
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            raise

    def generate_cleaning_explanation(
        self,
        column: str,
        action: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate explanation for why a specific cleaning action was recommended.
        
        Args:
            column: Column name
            action: Recommended action (e.g., 'median_imputation')
            metadata: Column metadata (dtype, missing_pct, stats, etc.)
        
        Returns:
            {
                "explanation": str,
                "reasoning": str,
                "confidence": float
            }
        """
        prompt = f"""You are a data quality expert. Explain why the following cleaning action was recommended.

Column: {column}
Action: {action}
Metadata: {json.dumps(metadata, indent=2)}

Provide a concise explanation (2-3 sentences) that:
1. Explains why this specific action was chosen
2. References the column's characteristics
3. Mentions the expected impact

Respond in JSON format:
{{
    "explanation": "brief explanation for users",
    "reasoning": "technical reasoning",
    "confidence": 0.85
}}
"""
        
        try:
            response = self._generate_with_retry(prompt)
            # Try to parse JSON from response
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            logger.warning(f"Failed to generate cleaning explanation: {e}")
            return {
                "explanation": f"Apply {action} to handle data quality issues in {column}.",
                "reasoning": "AI explanation unavailable",
                "confidence": 0.7,
            }

    def generate_dataset_summary(
        self,
        profile: dict[str, Any],
        audit: dict[str, Any],
        health: dict[str, Any],
    ) -> str:
        """
        Generate executive summary of dataset.
        
        Args:
            profile: Dataset profile
            audit: Quality audit results
            health: Health score breakdown
        
        Returns:
            Executive summary text
        """
        prompt = f"""You are a data analyst. Provide an executive summary of this dataset.

Profile Summary:
- Rows: {profile['summary']['rows']}
- Columns: {profile['summary']['columns']}
- Memory: {profile['summary']['memory_usage_bytes']} bytes

Quality Issues:
- Missing values: {sum(audit['missing']['by_column'].values())} cells
- Duplicate rows: {audit['duplicates']['duplicate_rows']}
- Outliers detected: {sum(audit['outliers']['iqr'].values())} cells

Health Score: {health['score']}/100

Write a 4-5 sentence executive summary that:
1. Describes the dataset size and scope
2. Highlights the most critical quality issues
3. Recommends next steps
4. Mentions the overall health assessment

Be concise and actionable.
"""
        
        try:
            return self._generate_with_retry(prompt)
        except Exception as e:
            logger.warning(f"Failed to generate dataset summary: {e}")
            return f"Dataset contains {profile['summary']['rows']} rows and {profile['summary']['columns']} columns with a health score of {health['score']}/100. Review quality issues and apply recommended cleaning actions."

    def generate_feature_engineering_reasoning(
        self,
        suggestions: list[dict[str, Any]],
        profile: dict[str, Any],
    ) -> str:
        """
        Generate reasoning for feature engineering suggestions.
        
        Args:
            suggestions: List of feature engineering suggestions
            profile: Dataset profile
        
        Returns:
            Reasoning text
        """
        prompt = f"""You are a machine learning engineer. Explain the feature engineering strategy for this dataset.

Dataset has {profile['summary']['columns']} columns and {profile['summary']['rows']} rows.

Suggested transformations:
{json.dumps(suggestions[:10], indent=2)}

Write a 3-4 sentence explanation that:
1. Summarizes the key transformations needed
2. Explains why these transformations improve ML performance
3. Prioritizes the most impactful changes

Be technical but accessible.
"""
        
        try:
            return self._generate_with_retry(prompt)
        except Exception as e:
            logger.warning(f"Failed to generate feature engineering reasoning: {e}")
            return "Apply standard transformations including encoding categorical variables, scaling numeric features, and extracting temporal components to prepare features for machine learning."

    def generate_ml_readiness_reasoning(
        self,
        score: int,
        ready_for: dict[str, bool],
        profile: dict[str, Any],
        audit: dict[str, Any],
    ) -> str:
        """
        Generate reasoning for ML readiness score.
        
        Args:
            score: ML readiness score (0-100)
            ready_for: Dict of task readiness booleans
            profile: Dataset profile
            audit: Quality audit
        
        Returns:
            Reasoning text
        """
        prompt = f"""You are an ML platform engineer. Explain the ML readiness assessment for this dataset.

ML Readiness Score: {score}/100

Task Readiness:
{json.dumps(ready_for, indent=2)}

Dataset: {profile['summary']['rows']} rows, {profile['summary']['columns']} columns
Quality Issues: {sum(audit['missing']['by_column'].values())} missing cells

Write a 3-4 sentence explanation that:
1. Interprets the readiness score
2. Explains which ML tasks are viable
3. Identifies the main blockers to full readiness

Be specific about what needs improvement.
"""
        
        try:
            return self._generate_with_retry(prompt)
        except Exception as e:
            logger.warning(f"Failed to generate ML readiness reasoning: {e}")
            return f"Dataset readiness score is {score}/100. Address data quality issues and feature engineering requirements before training models."

    def generate_executive_report_summary(
        self,
        profile: dict[str, Any],
        audit: dict[str, Any],
        health: dict[str, Any],
        ml_readiness: dict[str, Any],
        cleaning_history: list[dict[str, Any]],
    ) -> str:
        """
        Generate comprehensive executive summary for PDF reports.
        
        Args:
            profile: Dataset profile
            audit: Quality audit
            health: Health score
            ml_readiness: ML readiness assessment
            cleaning_history: History of cleaning operations
        
        Returns:
            Executive summary text
        """
        prompt = f"""You are a senior data consultant. Write an executive summary for this dataset analysis report.

Dataset Overview:
- Size: {profile['summary']['rows']} rows × {profile['summary']['columns']} columns
- Health Score: {health['score']}/100
- ML Readiness: {ml_readiness['score']}/100

Quality Findings:
- Missing: {sum(audit['missing']['by_column'].values())} cells
- Duplicates: {audit['duplicates']['duplicate_rows']} rows
- Outliers: {sum(audit['outliers']['iqr'].values())} cells

Cleaning Actions Performed: {len(cleaning_history)}

Write a professional 5-7 sentence executive summary that:
1. Introduces the dataset and its purpose
2. Highlights key quality findings
3. Summarizes improvements made
4. Provides ML readiness assessment
5. Recommends next steps

Use a professional, confident tone suitable for stakeholders.
"""
        
        try:
            return self._generate_with_retry(prompt)
        except Exception as e:
            logger.warning(f"Failed to generate executive report summary: {e}")
            return f"This report analyzes a dataset with {profile['summary']['rows']} rows and {profile['summary']['columns']} columns. The dataset achieved a health score of {health['score']}/100 and ML readiness of {ml_readiness['score']}/100. {len(cleaning_history)} cleaning operations were performed. Review detailed findings and implement recommended actions for production use."

    def answer_dataset_question(
        self,
        question: str,
        context: dict[str, Any],
    ) -> str:
        """
        Answer natural language questions about the dataset.
        
        Args:
            question: User's question
            context: Dataset context (profile, audit, history, etc.)
        
        Returns:
            Answer text
        """
        prompt = f"""You are an AI data assistant. Answer the user's question about their dataset.

User Question: {question}

Dataset Context:
{json.dumps(context, indent=2)[:3000]}  # Truncate to avoid token limits

Provide a clear, concise answer (2-4 sentences) that:
1. Directly answers the question
2. References specific data points from the context
3. Provides actionable insights when relevant

If you cannot answer based on available context, say so clearly.
"""
        
        try:
            return self._generate_with_retry(prompt)
        except Exception as e:
            logger.warning(f"Failed to answer dataset question: {e}")
            return "I'm having trouble processing your question right now. Please try rephrasing or ask about specific aspects like data quality, cleaning recommendations, or ML readiness."

    def generate_insights(
        self,
        profile: dict[str, Any],
        audit: dict[str, Any],
        correlations: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate top insights about the dataset.
        
        Args:
            profile: Dataset profile
            audit: Quality audit
            correlations: Top correlations (optional)
        
        Returns:
            List of insights with confidence levels
        """
        prompt = f"""You are a data scientist. Generate 5-7 key insights about this dataset.

Profile:
{json.dumps(profile['summary'], indent=2)}

Quality Issues:
- Missing: {sum(audit['missing']['by_column'].values())} cells
- Duplicates: {audit['duplicates']['duplicate_rows']}
- Outliers: {sum(audit['outliers']['iqr'].values())}

{f"Top Correlations: {json.dumps(correlations[:5], indent=2)}" if correlations else ""}

Generate insights in JSON format:
[
    {{
        "insight": "brief insight statement",
        "confidence": 0.85,
        "reasoning": "why this matters"
    }},
    ...
]

Focus on:
- Actionable findings
- Quality patterns
- Feature relationships
- ML implications
"""
        
        try:
            response = self._generate_with_retry(prompt)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            logger.warning(f"Failed to generate insights: {e}")
            return [
                {
                    "insight": f"Dataset contains {profile['summary']['rows']} rows with {profile['summary']['columns']} features",
                    "confidence": 0.95,
                    "reasoning": "Basic dataset characteristics",
                }
            ]

    def generate_ml_strategy(
        self,
        profile: dict[str, Any],
        target_column: str | None,
        class_balance: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Generate ML strategy recommendations.
        
        Args:
            profile: Dataset profile
            target_column: Target column name (if detected)
            class_balance: Class balance info (if applicable)
        
        Returns:
            {
                "recommended_tasks": list[str],
                "recommended_models": list[dict],
                "reasoning": str
            }
        """
        prompt = f"""You are an AutoML advisor. Recommend ML strategy for this dataset.

Dataset: {profile['summary']['rows']} rows × {profile['summary']['columns']} columns
Target Column: {target_column or "Not detected"}
{f"Class Balance: {json.dumps(class_balance, indent=2)}" if class_balance else ""}

Numeric Columns: {len(profile['roles']['numerical'])}
Categorical Columns: {len(profile['roles']['categorical'])}

Respond in JSON format:
{{
    "recommended_tasks": ["classification", "regression", "clustering"],
    "recommended_models": [
        {{"name": "Random Forest", "reason": "why", "priority": 1}},
        {{"name": "XGBoost", "reason": "why", "priority": 2}}
    ],
    "reasoning": "overall strategy explanation"
}}

Consider:
- Dataset size and complexity
- Target variable type
- Class balance issues
- Feature types
"""
        
        try:
            response = self._generate_with_retry(prompt)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            logger.warning(f"Failed to generate ML strategy: {e}")
            return {
                "recommended_tasks": ["classification"] if target_column else ["clustering"],
                "recommended_models": [
                    {"name": "Random Forest", "reason": "Robust baseline model", "priority": 1}
                ],
                "reasoning": "Standard ML approach recommended",
            }


# Global instance
gemini_service = GeminiService()
