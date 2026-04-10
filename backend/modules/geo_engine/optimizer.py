"""GEO Engine — scores content for AI answerability and generates schema."""
from __future__ import annotations

import json
import anthropic
from backend.config import settings


GEO_SCORE_PROMPT = """You are an expert in Generative Engine Optimization (GEO) — optimizing content so AI systems
(ChatGPT, Perplexity, Google SGE, Claude) cite and surface it in generated answers.

Analyze the following content and return a JSON object with:
{
  "geo_score": <0-100>,
  "direct_answer": <true|false>,  // Does it directly answer a question in the first 2 sentences?
  "entity_rich": <true|false>,    // Does it mention specific entities (brands, people, places, data)?
  "structured_for_llm": <true|false>,  // Is it chunked into clear sections an LLM can extract?
  "issues": ["list of specific GEO weaknesses"],
  "recommendations": ["list of specific improvements"],
  "faq_suggestions": [
    {"question": "...", "answer": "..."}
  ],
  "entity_suggestions": ["entity1", "entity2"]
}

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
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def run(self, content: str, url: str = "") -> dict:
        """Score content for GEO and return recommendations + schemas."""
        analysis = await self._score_content(content)
        faq_schema = await self._generate_faq_schema(analysis.get("faq_suggestions", []))
        howto_schema = await self._generate_howto_schema(content)

        return {
            "url": url,
            "analysis": analysis,
            "schemas": {
                "faq": faq_schema,
                "howto": howto_schema,
            },
        }

    async def _score_content(self, content: str) -> dict:
        prompt = GEO_SCORE_PROMPT.format(content=content[:8000])  # Trim for context window
        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"geo_score": 0, "issues": ["Parse error"], "recommendations": [], "faq_suggestions": []}

    async def _generate_faq_schema(self, faqs: list[dict]) -> dict:
        if not faqs:
            return {}
        faq_text = "\n".join(f"Q: {f['question']}\nA: {f['answer']}" for f in faqs)
        prompt = FAQ_SCHEMA_PROMPT.format(faqs=faq_text)
        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Build minimal valid schema as fallback
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
        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
