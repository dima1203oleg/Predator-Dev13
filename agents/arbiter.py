"""
Arbiter Agent: Multi-LLM voting for final decision
Uses 5 models: Gemma2-27B, Claude-Sonnet, GPT-4o, Mistral-Large, LLaMA-70B
"""

import json
import logging
import os
from typing import Any

from agents.base_agent import AgentContext, BaseAgent

logger = logging.getLogger(__name__)


class ArbiterAgent(BaseAgent):
    """
    Final decision maker using multi-LLM voting

    Strategy:
    1. Submit query + context to 5 LLMs
    2. Collect responses
    3. Vote + weighted consensus (by model reputation)
    4. Return final answer with confidence score
    """

    def __init__(self, **kwargs):
        super().__init__(name="Arbiter", **kwargs)

        # Voting models (from model_registry.yaml)
        self.voting_models = [
            {"name": "gemma2:27b", "weight": 1.2},  # Local, fast
            {"name": "claude-3-sonnet", "weight": 1.5},  # Best reasoning
            {"name": "gpt-4o", "weight": 1.4},  # Balanced
            {"name": "mistral-large", "weight": 1.3},  # Multilingual
            {"name": "llama3.1:70b", "weight": 1.2},  # Local, powerful
        ]

        logger.info("ArbiterAgent initialized with 5-model voting")

    def _execute_impl(self, context: AgentContext) -> dict[str, Any]:
        """
        Execute multi-LLM voting

        Returns:
            {
                "final_answer": str,
                "confidence": float (0-1),
                "votes": [...],  # Individual LLM responses
                "consensus": str  # Voting summary
            }
        """
        # Build prompt from context
        prompt = self._build_prompt(context)

        # Collect votes from 5 LLMs
        votes = []
        for model_config in self.voting_models:
            try:
                response = self._query_llm(model_config["name"], prompt)
                votes.append(
                    {
                        "model": model_config["name"],
                        "response": response,
                        "weight": model_config["weight"],
                    }
                )
            except Exception as e:
                logger.warning(f"Model {model_config['name']} failed: {e}")

        if not votes:
            return {
                "final_answer": "Помилка: жоден LLM не відповів",
                "confidence": 0.0,
                "votes": [],
                "consensus": "failed",
            }

        # Calculate consensus
        consensus_result = self._calculate_consensus(votes)

        return consensus_result

    def _build_prompt(self, context: AgentContext) -> str:
        """Build prompt from agent results"""
        # Get results from previous agents
        retriever = context.results.get("Retriever", {})
        miner = context.results.get("Miner", {})

        prompt = f"""Ти - експерт-аналітик митних даних України. Проаналізуй наступну інформацію:

ЗАПИТ КОРИСТУВАЧА:
{context.query}

ДАНІ (з Retriever):
- Знайдено записів: {retriever.get('total_count', 0)}
- Топ-5 компаній: {[r.get('company_name') for r in retriever.get('merged', [])[:5]]}

АНАЛІЗ (з Miner):
- Аномалій: {len(miner.get('anomalies', []))}
- Корупційних прапорців: {len(miner.get('corruption_flags', []))}
- Інсайти: {miner.get('insights', [])}

ЗАВДАННЯ:
1. Дай чітку відповідь на запит користувача
2. Вкажи ключові ризики (якщо є)
3. Дай рекомендації (якщо потрібно)

Формат відповіді: JSON
{{
    "answer": "string (відповідь)",
    "risks": ["string", ...] (або []),
    "recommendations": ["string", ...] (або [])
}}
"""
        return prompt

    def _query_llm(self, model_name: str, prompt: str) -> dict[str, Any]:
        """Query single LLM (Ollama or API)"""
        try:
            # Check if Ollama model
            if (
                ":" in model_name
                or model_name.startswith("llama")
                or model_name.startswith("gemma")
            ):
                return self._query_ollama(model_name, prompt)
            else:
                return self._query_api(model_name, prompt)
        except Exception as e:
            logger.error(f"LLM query failed for {model_name}: {e}")
            raise

    def _query_ollama(self, model: str, prompt: str) -> dict[str, Any]:
        """Query Ollama local model"""
        import requests

        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        response = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=60,
        )

        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "{}")

            # Parse JSON response
            try:
                parsed = json.loads(response_text)
                return parsed
            except json.JSONDecodeError:
                # Response text wasn't valid JSON; return raw answer structure
                return {"answer": response_text, "risks": [], "recommendations": []}
        else:
            raise Exception(f"Ollama error: {response.status_code}")

    def _query_api(self, model: str, prompt: str) -> dict[str, Any]:
        """Query API models (Claude, GPT-4, Mistral)"""
        # Claude
        if "claude" in model:
            import anthropic

            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

            message = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            return json.loads(response_text)

        # GPT-4
        elif "gpt" in model:
            import openai

            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )

            return json.loads(response.choices[0].message.content)

        # Mistral
        elif "mistral" in model:
            import requests

            response = requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
                timeout=60,
            )

            return json.loads(response.json()["choices"][0]["message"]["content"])

        else:
            raise ValueError(f"Unknown API model: {model}")

    def _calculate_consensus(self, votes: list[dict]) -> dict[str, Any]:
        """Calculate weighted consensus from votes"""
        # Aggregate answers
        all_answers = []
        all_risks = []
        all_recommendations = []

        for vote in votes:
            response = vote["response"]
            weight = vote["weight"]

            # Collect weighted items
            answer = response.get("answer", "")
            if answer:
                all_answers.append((answer, weight))

            all_risks.extend(response.get("risks", []))
            all_recommendations.extend(response.get("recommendations", []))

        # Select best answer (highest weighted)
        if all_answers:
            final_answer = max(all_answers, key=lambda x: x[1])[0]
        else:
            final_answer = "Не вдалося отримати консенсус"

        # Deduplicate risks/recommendations
        unique_risks = list(set(all_risks))[:5]  # Top 5
        unique_recommendations = list(set(all_recommendations))[:5]

        # Calculate confidence (% of models that responded)
        confidence = len(votes) / len(self.voting_models)

        return {
            "final_answer": final_answer,
            "confidence": round(confidence, 2),
            "risks": unique_risks,
            "recommendations": unique_recommendations,
            "votes": [
                {"model": v["model"], "answer_preview": v["response"].get("answer", "")[:100]}
                for v in votes
            ],
            "consensus": f"{len(votes)}/{len(self.voting_models)} models agreed",
        }


# ========== TEST ==========
if __name__ == "__main__":
    agent = ArbiterAgent()

    ctx = AgentContext(
        user_id="test", query="Чи є ризики у цій компанії?", session_id="test", trace_id="test"
    )

    # Mock previous results
    ctx.results["Retriever"] = {"total_count": 150, "merged": [{"company_name": "TestCorp"}]}
    ctx.results["Miner"] = {
        "anomalies": [{"z_score": 4.5}],
        "corruption_flags": [{"pattern": "Демпінг"}],
        "insights": ["Знайдено підозрілі патерни"],
    }

    result = agent.execute(ctx)
    print(f"Final Answer: {result['result']['final_answer']}")
    print(f"Confidence: {result['result']['confidence']}")
