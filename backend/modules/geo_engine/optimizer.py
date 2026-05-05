"""GEO Engine — scores content for AI answerability and generates schema."""
from __future__ import annotations

import json
from backend.llm import get_llm, ollama_is_available


GEO_SCORE_PROMPT = """You are an expert in Generative Engine Optimization (GEO) — optimizing content so AI systems
(ChatGPT, Perplexity, Google SGE, Claude) cite and surface it in generated answers.

Analyze the following content and return a JSON object with:
{{
  "geo_score": <0-100>,
  "direct_answer": <true|false>,
  "entity_rich": <true|false>,
  "structured_for_llm": <true|false>,
  "issues": ["list of specific GEO weaknesses"],
  "recommendations": ["list of specific improvements"],
  "faq_suggestions": [
    {{"question": "...", "answer": "..."}}
  ],
  "entity_suggestions": ["entity1", "entity2"]
}}

Only return valid JSON. No markdown. No explanation outside the JSON.

Content to analyze:
---
{content}
---
"""

FAQ_SCHEMA_PROMPT = """Generate a valid FAQPage JSON-LD schema for the following Q&A pairs.
Return only the JSON-LD object. No markdown. No explanation.

FAQ items:
{faqs}
"""

HOWTO_SCHEMA_PROMPT = """Generate a valid HowTo JSON-LD schema based on the following content.
Extract the steps automatically. Return only the JSON-LD object. No markdown.

Content:
{content}
"""


class GEOOptimizer:
    def __init__(self, db=None):
        self.llm = get_llm()
        self.db = db

    async def run(self, content: str = "", url: str = "", site_id: int = None) -> dict:
        """Score content for GEO and return recommendations + schemas."""
        if not ollama_is_available():
            return {"url": url, "score": 0, "issues": [], "recommendations": [], "schemas": {}}

        analysis = await self._score_content(content)
        faq_schema = await self._generate_faq_schema(analysis.get("faq_suggestions", []))
        howto_schema = await self._generate_howto_schema(content)

        return {
            "url": url,
            "score": analysis.get("geo_score", 0),
            "analysis": analysis,
            "schemas": {
                "faq": faq_schema,
                "howto": howto_schema,
            },
        }

    async def _score_content(self, content: str) -> dict:
        prompt = GEO_SCORE_PROMPT.format(content=content[:8000])
        try:
            return await self.llm.generate_json_async(prompt, max_tokens=4096)
        except Exception:
            return {"geo_score": 0, "issues": ["Parse error"], "recommendations": [], "faq_suggestions": []}

    async def _generate_faq_schema(self, faqs: list[dict]) -> dict:
        if not faqs:
            return {}
        faq_text = "\n".join(f"Q: {f['question']}\nA: {f['answer']}" for f in faqs)
        prompt = FAQ_SCHEMA_PROMPT.format(faqs=faq_text)
        try:
            return await self.llm.generate_json_async(prompt, max_tokens=2048)
        except Exception:
            return {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f["question"],
                        "acceptedAnswer": {"@type": "Answer", "text": f["answer"]},
                    }
                    for f in faqs
                ],
            }

    async def _generate_howto_schema(self, content: str) -> dict:
        prompt = HOWTO_SCHEMA_PROMPT.format(content=content[:4000])
        try:
            return await self.llm.generate_json_async(prompt, max_tokens=1024)
        except Exception:
            return {}
