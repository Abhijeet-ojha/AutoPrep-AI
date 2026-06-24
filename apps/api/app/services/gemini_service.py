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
            # General fallback response - aggregates summary, insights, and structured plan
            explanation = generate_health_explanation(self.context)
            resp = f"### 📊 Summary:\n{explanation}\n\n"
            
            if self.insights:
                resp += "### 🔍 Key Quality Insights:\n"
                for ins in self.insights:
                    resp += f"- **{ins['title']}**: {ins['evidence']}\n"
                    resp += f"  *Recommendation:* {ins['recommendation']}\n"
                resp += "\n"
                
            resp += "### 🛠️ Recommended Cleaning Steps:\n"
            plan = get_structured_cleaning_plan(self.context)
            if not plan:
                resp += "1. No quality actions required. The dataset looks clean!\n"
            else:
                for idx, step in enumerate(plan, 1):
                    col_str = f" on column `{step['column']}`" if step['column'] else ""
                    resp += f"{idx}. Run **{step['action']}**{col_str} (Method: `{step['method']}`).\n"
            
            return header + resp


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

