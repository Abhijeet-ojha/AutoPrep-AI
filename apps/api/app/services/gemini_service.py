"""LLM API service and offline fallback providers."""

import logging
from abc import ABC, abstractmethod
import google.generativeai as genai
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class CopilotProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate response text based on the constructed prompt."""
        pass

    @abstractmethod
    def generate_stream(self, prompt: str):
        """Generate response text stream based on the constructed prompt."""
        pass


class GeminiProvider(CopilotProvider):
    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is missing from settings/environment.")
        genai.configure(api_key=settings.gemini_api_key)

    def generate(self, prompt: str) -> str:
        logger.info("Sending request to Gemini model 'gemini-2.5-flash'...")
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            if not response.text:
                raise RuntimeError("Gemini returned empty content.")
            return response.text
        except Exception as e:
            logger.error(f"Gemini API execution failed: {e}")
            raise

    def generate_stream(self, prompt: str):
        logger.info("Sending streaming request to Gemini model 'gemini-2.5-flash'...")
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt, stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini API streaming execution failed: {e}")
            raise


class GroqProvider(CopilotProvider):
    def __init__(self):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is missing from settings/environment.")

    def generate(self, prompt: str) -> str:
        logger.info(f"Sending request to Groq model '{settings.groq_model}'...")
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are AutoPrep AI Dataset Copilot, an expert data scientist assistant. Provide concise, accurate and professional insights."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                if response.status_code != 200:
                    raise RuntimeError(f"Groq API returned status {response.status_code}: {response.text}")
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                if not content:
                    raise RuntimeError("Groq returned empty completion.")
                return content
        except Exception as e:
            logger.error(f"Groq API execution failed: {e}")
            raise

    def generate_stream(self, prompt: str):
        logger.info(f"Sending streaming request to Groq model '{settings.groq_model}'...")
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are AutoPrep AI Dataset Copilot, an expert data scientist assistant. Provide concise, accurate and professional insights."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "stream": True
        }
        try:
            import json
            with httpx.Client(timeout=30.0) as client:
                with client.stream("POST", "https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        raise RuntimeError(f"Groq API returned status {response.status_code}")
                    for line in response.iter_lines():
                        if not line.strip():
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_str)
                                delta = chunk_json["choices"][0]["delta"]
                                if "content" in delta:
                                    yield delta["content"]
                            except Exception:
                                pass
        except Exception as e:
            logger.error(f"Groq API streaming execution failed: {e}")
            raise


class FallbackProvider(CopilotProvider):
    def __init__(self, context: dict, insights: list[dict], question: str | None = None):
        self.context = context
        self.insights = insights
        self.question = question or ""

    def generate(self, prompt: str) -> str:
        logger.info("Using FallbackProvider to deterministically generate response...")
        from app.services.insight_engine import (
            suggest_advanced_features,
            recommend_models,
            generate_health_explanation,
            get_structured_cleaning_plan
        )
        
        # Determine user question intent
        q = (self.question or prompt).lower()
        if 'user question: "' in q:
            try:
                q = q.split('user question: "')[1].split('"')[0]
            except Exception:
                pass
                
        profile_summary = self.context.get("profile_summary", {})
        filename = self.context.get("dataset_summary", {}).get("filename", "unknown")
        
        header = f"**[Copilot Offline / Fallback Mode]**\n"
        header += f"Automated preparation advice for **{filename}**:\n\n"
        
        if "feature" in q or "suggest" in q:
            features = suggest_advanced_features(profile_summary)
            resp = "### Feature Engineering Suggestions:\n\n"
            for feat in features:
                resp += f"- **{feat['feature_name']}**:\n"
                resp += f"  *Reason:* {feat['reason']}\n"
                resp += f"  *Expected Benefit:* {feat['expected_benefit']}\n"
                resp += f"  *Confidence:* {feat['confidence_score']:.2f}\n\n"
            return header + resp
            
        elif "model" in q or "use" in q or "algorithm" in q:
            models = recommend_models(profile_summary)
            resp = "### Model Recommendation:\n\n"
            resp += f"**Task Identified:** {models.get('task')}\n\n"
            if models.get("error"):
                resp += f"⚠️ *Warning:* {models['error']}\n"
            else:
                for idx, rec in enumerate(models.get("recommendations", []), 1):
                    resp += f"{idx}. **{rec['model']}**\n"
                    resp += f"   *Explanation:* {rec['explanation']}\n\n"
            return header + resp
            
        elif "health" in q or "score" in q or "quality" in q:
            explanation = generate_health_explanation(self.context)
            return header + f"### Health Explanation:\n\n{explanation}"
            
        elif "cleaning plan" in q or "structured plan" in q or "preparation plan" in q:
            plan = get_structured_cleaning_plan(self.context)
            resp = "### Structured Cleaning Plan:\n\n"
            if not plan:
                resp += "No quality actions required. The dataset looks clean!\n"
            else:
                resp += "Recommended Actionable Cleaning Steps:\n"
                for idx, step in enumerate(plan, 1):
                    col_str = f" on column `{step['column']}`" if step['column'] else ""
                    resp += f"{idx}. **{step['action']}**{col_str} (Method: `{step['method']}`)\n"
                    resp += f"   *Reason:* {step['reason']}\n\n"
            return header + resp
            
        else:
            # Full structured report
            ds = self.context.get("dataset_summary", {})
            raw_metrics = self.context.get("raw_metrics", {})
            cleaning_impact = self.context.get("cleaning_impact", {})
            readiness = self.context.get("readiness", {})
            
            resp = "# Dataset Analysis Report\n\n"
            resp += "Here is the professional structured dataset analysis computed deterministically by AutoPrep AI.\n\n"
            
            # 1. Dataset Overview
            resp += "## Dataset Overview\n"
            resp += "| Property | Value |\n"
            resp += "| --- | --- |\n"
            resp += f"| Filename | {ds.get('filename', 'unknown')} |\n"
            resp += f"| Row Count | {ds.get('rows', 0)} |\n"
            resp += f"| Column Count | {ds.get('columns', 0)} |\n"
            resp += f"| File Size | {ds.get('file_size_bytes', 0)} bytes |\n\n"
            
            # 2. Overall Health
            explanation = generate_health_explanation(self.context)
            resp += f"## Overall Health\n{explanation}\n\n"
            
            # 3. Data Quality Summary
            missing = raw_metrics.get("original_missing_count", 0)
            dups = raw_metrics.get("original_duplicate_count", 0)
            outliers = raw_metrics.get("original_outlier_count", 0)
            resp += "## Data Quality Summary\n"
            resp += f"- **Missing Values**: Found **{missing}** missing cells in the raw dataset.\n"
            resp += f"- **Duplicate Rows**: Identified **{dups}** duplicate rows.\n"
            resp += f"- **Outliers**: Detected **{outliers}** outlier values across numeric features.\n\n"
            
            # 4. Cleaning Impact
            resp += "## Cleaning Impact\n"
            resp += "| Metric | Before Auto-Clean | After Auto-Clean |\n"
            resp += "| --- | --- | --- |\n"
            resp += f"| Row Count | {cleaning_impact.get('rows_before', ds.get('rows', 0))} | {cleaning_impact.get('rows_after', ds.get('rows', 0))} |\n"
            resp += f"| Missing Values | {missing} | 0 |\n"
            resp += f"| Duplicate Rows | {dups} | 0 |\n"
            resp += f"| Outliers Treated | 0 | {cleaning_impact.get('outliers_treated', 0)} |\n\n"
            
            # 5. Dataset Composition
            resp += "## Dataset Composition\n"
            profile_summary = self.context.get("profile_summary") or self.context.get("profile", {})
            if profile_summary:
                resp += "| Column | Type | Missing% | Unique Values |\n"
                resp += "| --- | --- | --- | --- |\n"
                for col, info in profile_summary.items():
                    resp += f"| {col} | {info.get('type', 'unknown')} | {info.get('missing_pct', 0.0):.1f}% | {info.get('cardinality', 'N/A')} |\n"
                resp += "\n"
            else:
                resp += "Column schema composition metadata is currently unavailable.\n\n"
                
            # 6. Machine Learning Readiness
            resp += "## Machine Learning Readiness\n"
            resp += f"The dataset has a Machine Learning Readiness score of **{readiness.get('score', 50)}/100**.\n"
            resp += f"- **Target Task Recommendation**: {readiness.get('target_type', 'General modeling')} ({readiness.get('recommended_task', 'predictive task')}).\n"
            resp += f"- **Pre-processing Advice**: Features have been imputed, duplicates evicted, and columns semantically annotated.\n\n"
            
            # 7. Recommendations
            resp += "## Recommendations\n"
            plan = get_structured_cleaning_plan(self.context)
            if not plan:
                resp += "1. No quality actions required. The dataset is fully cleaned and ready!\n"
            else:
                for idx, step in enumerate(plan, 1):
                    col_str = f" on column `{step['column']}`" if step['column'] else ""
                    resp += f"{idx}. **{step['action']}**{col_str} (Method: `{step['method']}`): {step['reason']}\n"
            resp += "\n"
            
            # 8. Final Summary
            resp += "## Final Summary\n"
            resp += "The dataset has been successfully cleaned and optimized. It is recommended to download the cleaned CSV and proceed with model training."
            
            return header + resp

    def generate_stream(self, prompt: str):
        full_text = self.generate(prompt)
        import time
        words = full_text.split(" ")
        for i in range(0, len(words), 3):
            chunk = " ".join(words[i:i+3]) + " "
            yield chunk
            time.sleep(0.03)


class MultiProviderChain(CopilotProvider):
    def __init__(self, providers: list[tuple[str, CopilotProvider]]):
        self.providers = providers
        self.successful_provider = "None"

    def generate(self, prompt: str) -> str:
        last_error = None
        for name, provider in self.providers:
            try:
                result = provider.generate(prompt)
                self.successful_provider = name
                return result
            except Exception as e:
                logger.warning(f"LLM Provider {name} failed: {e}. Trying next provider in chain...")
                last_error = e
        raise RuntimeError(f"All LLM providers in chain failed. Last error: {last_error}")

    def generate_stream(self, prompt: str):
        last_error = None
        for name, provider in self.providers:
            try:
                iterator = provider.generate_stream(prompt)
                first_chunk = next(iterator, None)
            except Exception as e:
                logger.warning(f"LLM Provider stream {name} failed to initialize: {e}. Trying next provider in chain...")
                last_error = e
                continue

            if first_chunk is not None:
                self.successful_provider = name
                yield first_chunk
                try:
                    for chunk in iterator:
                        yield chunk
                except Exception as e:
                    logger.error(f"LLM Provider {name} failed mid-stream: {e}")
                    raise
                return
        raise RuntimeError(f"All LLM providers in chain failed to stream. Last error: {last_error}")


def get_copilot_provider(context: dict, insights: list[dict], question: str | None = None) -> CopilotProvider:
    """Retrieve the configured or fallback copilot provider list."""
    chain = []
    
    # 1. Try Gemini
    if settings.gemini_api_key:
        try:
            chain.append(("GeminiProvider", GeminiProvider()))
        except Exception as e:
            logger.warning(f"Could not load GeminiProvider: {e}")

    # 2. Try Groq
    if settings.groq_api_key:
        try:
            chain.append(("GroqProvider", GroqProvider()))
        except Exception as e:
            logger.warning(f"Could not load GroqProvider: {e}")

    if chain:
        return MultiProviderChain(chain)
        
    return FallbackProvider(context, insights, question)

