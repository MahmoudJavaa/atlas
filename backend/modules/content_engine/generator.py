"""Content Engine — generates SEO content via Claude with proper structure."""
from __future__ import annotations

import json
import re
from sqlalchemy.ext.asyncio import AsyncSession

import anthropic
from backend.config import settings
from backend.models.content import ContentPage


CONTENT_PROMPT = """You are an expert SEO content writer. Generate a complete, publication-ready page.

Target keyword: {keyword}
Intent: {intent}
Funnel stage: {funnel_stage}
Page type: {page_type}
Location: {location}

Requirements:
- H1 that naturally includes the target keyword
- 3-5 H2 sections with H3 subsections where relevant
- NLP entity distribution (mention related entities/brands/places naturally)
- Internal linking placeholders: [INTERNAL_LINK: topic]
- A compelling CTA block near the bottom
- A FAQ section with 5 questions (AEO-ready)
- Minimum 800 words for blog, 500 for landing pages
- Write in UK English

Return a JSON object with:
{{
  "title": "<meta title, 50-60 chars>",
  "meta_desc": "<meta description, 140-160 chars>",
  "h1": "<H1 heading>",
  "content_html": "<full HTML content with proper heading tags>",
  "word_count": <integer>,
  "schema": {{...FAQPage JSON-LD...}},
  "internal_link_suggestions": ["topic1", "topic2"]
}}

Only return valid JSON. No markdown code fences.
"""


class ContentGenerator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def run(
        self,
        site_id: int,
        keyword: str,
        intent: str,
        funnel_stage: str,
        page_type: str,
        location: str | None = None,
    ) -> dict:
        """Generate full content and persist to DB."""
        generated = await self._generate(keyword, intent, funnel_stage, page_type, location or "")

        page = ContentPage(
            site_id=site_id,
            title=generated.get("title", ""),
            meta_desc=generated.get("meta_desc", ""),
            content=generated.get("content_html", ""),
            schema_json=generated.get("schema", {}),
            keyword=keyword,
            intent=intent,
            funnel_stage=funnel_stage,
            page_type=page_type,
            word_count=generated.get("word_count", 0),
            status="draft",
        )
        self.db.add(page)
        await self.db.flush()
        await self.db.refresh(page)

        return {**generated, "content_page_id": page.id}

    async def _generate(self, keyword, intent, funnel_stage, page_type, location) -> dict:
        prompt = CONTENT_PROMPT.format(
            keyword=keyword,
            intent=intent,
            funnel_stage=funnel_stage,
            page_type=page_type,
            location=location or "N/A",
        )
        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=8096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown code fences if Claude wraps in them
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Return minimal fallback
            return {
                "title": keyword,
                "meta_desc": f"Learn about {keyword}.",
                "h1": keyword,
                "content_html": f"<h1>{keyword}</h1><p>Content generation encountered an error. Please retry.</p>",
                "word_count": 0,
                "schema": {},
                "internal_link_suggestions": [],
            }
