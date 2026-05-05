"""Competitor Intelligence — reverse-engineers competitor ranking pages."""
from __future__ import annotations

import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

import httpx
from bs4 import BeautifulSoup
from backend.llm import get_llm
from backend.config import settings


GAP_ANALYSIS_PROMPT = """You are an SEO competitor analyst.

Given the following competitor page data, explain in JSON why they likely rank highly and what content gaps exist.

Competitor domain: {competitor}
Their top pages:
{pages}

Our domain: {our_domain}
Our keywords we rank for: {our_keywords}

Return JSON:
{{
  "ranking_factors": ["reason1", "reason2"],
  "content_gaps": [
    {{"topic": "...", "suggested_url_slug": "...", "estimated_volume": "low|medium|high"}}
  ],
  "structural_insights": ["insight1"],
  "entity_density_notes": "...",
  "recommended_actions": ["action1", "action2"]
}}

Only valid JSON. No markdown.
"""


class CompetitorAnalyzer:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm()

    async def run(self, site_id: int, competitor_domains: list[str], our_domain: str = "") -> dict:
        """Analyze competitors and return gap report."""
        competitor_data = []

        for domain in competitor_domains:
            pages = await self._get_top_pages(domain)
            competitor_data.append({"domain": domain, "pages": pages})

        our_keywords = await self._get_our_keywords(site_id)
        analysis = await self._analyze_gaps(competitor_data, our_domain, our_keywords)

        return {
            "competitor_data": competitor_data,
            "analysis": analysis,
            "domains_analyzed": competitor_domains,
        }

    async def _get_top_pages(self, domain: str) -> list[dict]:
        """Use SerpAPI to find competitor's top-ranking pages."""
        if not settings.serpapi_key:
            return [{"url": f"https://{domain}/", "title": "Homepage (mock)", "word_count": 1200}]

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": f"site:{domain}",
                        "api_key": settings.serpapi_key,
                        "engine": "google",
                        "num": 10,
                    },
                )
                data = resp.json()
                pages = []
                for result in data.get("organic_results", []):
                    page = {
                        "url": result.get("link", ""),
                        "title": result.get("title", ""),
                        "snippet": result.get("snippet", ""),
                    }
                    details = await self._scrape_page_details(page["url"])
                    page.update(details)
                    pages.append(page)
                return pages
            except Exception:
                return []

    async def _scrape_page_details(self, url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "AtlasBot/1.0"})
                soup = BeautifulSoup(resp.text, "html.parser")
                body = soup.find("body")
                word_count = len(body.get_text().split()) if body else 0
                h2s = [h.get_text(strip=True) for h in soup.find_all("h2")[:5]]
                entities = [e.get_text(strip=True) for e in soup.find_all(["strong", "b"])[:10]]
                return {"word_count": word_count, "h2_headings": h2s, "entities": entities}
        except Exception:
            return {"word_count": 0, "h2_headings": [], "entities": []}

    async def _get_our_keywords(self, site_id: int) -> list[str]:
        from sqlalchemy import select
        from backend.models.keyword import Keyword
        result = await self.db.execute(
            select(Keyword.keyword).where(Keyword.site_id == site_id).limit(50)
        )
        return [row[0] for row in result.fetchall()]

    async def _analyze_gaps(
        self, competitor_data: list[dict], our_domain: str, our_keywords: list[str]
    ) -> dict:
        pages_text = json.dumps(
            [{"domain": c["domain"], "pages": c["pages"][:5]} for c in competitor_data],
            indent=2,
        )[:6000]

        prompt = GAP_ANALYSIS_PROMPT.format(
            competitor=", ".join(c["domain"] for c in competitor_data),
            pages=pages_text,
            our_domain=our_domain or "unknown",
            our_keywords=", ".join(our_keywords[:30]),
        )

        try:
            from backend.llm import ollama_is_available
            if not ollama_is_available():
                raise RuntimeError("Ollama not available")
            return await self.llm.generate_json_async(prompt, max_tokens=3000)
        except Exception:
            return {"content_gaps": [], "ranking_factors": [], "recommended_actions": []}
