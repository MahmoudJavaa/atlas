"""Internal Linking & Silo Builder — builds topic clusters and linking recommendations."""
from __future__ import annotations

import json
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import anthropic
from backend.config import settings
from backend.models.crawl import CrawlResult
from backend.models.keyword import Keyword


SILO_PROMPT = """You are an SEO internal linking expert.

Given the following pages from a website, build a topic silo structure and internal linking plan.

Pages:
{pages}

Return JSON:
{{
  "pillar_pages": [
    {{"url": "...", "topic": "...", "supporting_pages": ["url1", "url2"]}}
  ],
  "orphan_pages": ["url1", "url2"],
  "over_linked_pages": ["url1"],
  "linking_recommendations": [
    {{
      "from_url": "...",
      "to_url": "...",
      "anchor_text": "...",
      "reason": "..."
    }}
  ],
  "cannibalization_risks": [
    {{"urls": ["url1", "url2"], "topic": "..."}}
  ]
}}

Only valid JSON.
"""


class SiloBuilder:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def run(self, site_id: int) -> dict:
        """Build silo structure from crawl data."""
        pages = await self._get_crawl_data(site_id)
        if not pages:
            return {"error": "No crawl data found. Run a crawl first."}

        silo_plan = await self._build_silo_with_claude(pages)
        orphan_count = len(silo_plan.get("orphan_pages", []))

        return {
            "pages_analyzed": len(pages),
            "orphan_pages_found": orphan_count,
            "silo_plan": silo_plan,
        }

    async def _get_crawl_data(self, site_id: int) -> list[dict]:
        result = await self.db.execute(
            select(CrawlResult).where(CrawlResult.site_id == site_id).limit(500)
        )
        crawls = result.scalars().all()
        return [
            {"url": c.url, "title": c.title, "word_count": c.word_count, "indexable": c.indexable}
            for c in crawls
            if c.indexable
        ]

    async def _build_silo_with_claude(self, pages: list[dict]) -> dict:
        pages_text = json.dumps(pages[:100], indent=2)  # Limit for context window
        prompt = SILO_PROMPT.format(pages=pages_text)

        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "pillar_pages": [],
                "orphan_pages": [],
                "over_linked_pages": [],
                "linking_recommendations": [],
                "cannibalization_risks": [],
            }
