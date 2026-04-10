"""Backlink AI — finds link opportunities and generates outreach emails."""
from __future__ import annotations

import json
import re
from sqlalchemy.ext.asyncio import AsyncSession

import anthropic
import httpx
from backend.config import settings
from backend.models.backlink import BacklinkOpportunity


OUTREACH_PROMPT = """You are an expert link-building outreach specialist.

Write a personalized outreach email to acquire a backlink from the following source.

Source domain: {source_domain}
Source page URL: {source_url}
Our target page: {target_url}
Our topic: {topic}
Reason they should link to us: {reason}

Write a short (150-200 word), natural, non-spammy email. Include:
- Personalised opener referencing their content
- Clear value proposition for the link
- Specific anchor text suggestion
- Professional sign-off

Return JSON: {{"subject": "...", "body": "..."}}
"""

SCORE_PROMPT = """Score this backlink opportunity on relevance (0.0–1.0).

Our domain: {our_domain}
Our topic: {topic}
Opportunity URL: {url}
Page snippet: {snippet}

Return JSON: {{"score": <float 0-1>, "reasoning": "...", "outreach_difficulty": "easy|medium|hard"}}
"""


class BacklinkFinder:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def run(self, site_id: int, target_domain: str, topic: str) -> dict:
        """Find backlink opportunities and generate outreach emails."""
        opportunities = await self._find_opportunities(target_domain, topic)
        scored = await self._score_opportunities(opportunities, target_domain, topic)
        with_emails = await self._generate_outreach(scored, target_domain, topic)
        saved = await self._save_opportunities(site_id, with_emails)

        return {
            "opportunities_found": len(with_emails),
            "opportunities": with_emails,
        }

    async def _find_opportunities(self, target_domain: str, topic: str) -> list[dict]:
        """Use SerpAPI to find competitor backlinks and resource pages."""
        if not settings.serpapi_key:
            # Return mock opportunities for testing
            return [
                {
                    "url": f"https://example.com/{topic.replace(' ', '-')}-resources",
                    "source_domain": "example.com",
                    "title": f"Best {topic} resources",
                    "snippet": f"A curated list of {topic} tools and guides.",
                    "type": "resource_page",
                }
            ]

        opportunities = []
        queries = [
            f'"{topic}" resources OR "useful links" -site:{target_domain}',
            f'"{topic}" intitle:"resources" OR intitle:"links"',
        ]

        async with httpx.AsyncClient(timeout=15) as client:
            for query in queries:
                try:
                    resp = await client.get(
                        "https://serpapi.com/search",
                        params={"q": query, "api_key": settings.serpapi_key, "engine": "google", "num": 10},
                    )
                    data = resp.json()
                    for result in data.get("organic_results", []):
                        from urllib.parse import urlparse
                        opportunities.append({
                            "url": result.get("link", ""),
                            "source_domain": urlparse(result.get("link", "")).netloc,
                            "title": result.get("title", ""),
                            "snippet": result.get("snippet", ""),
                            "type": "competitor_backlink",
                        })
                except Exception:
                    continue

        return opportunities[:20]

    async def _score_opportunities(self, opportunities: list[dict], our_domain: str, topic: str) -> list[dict]:
        scored = []
        for opp in opportunities:
            prompt = SCORE_PROMPT.format(
                our_domain=our_domain,
                topic=topic,
                url=opp["url"],
                snippet=opp.get("snippet", ""),
            )
            try:
                message = self.client.messages.create(
                    model=settings.claude_model,
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = message.content[0].text.strip()
                score_data = json.loads(raw)
                opp["score"] = score_data.get("score", 0.5)
                opp["outreach_difficulty"] = score_data.get("outreach_difficulty", "medium")
                opp["score_reasoning"] = score_data.get("reasoning", "")
            except Exception:
                opp["score"] = 0.5
                opp["outreach_difficulty"] = "medium"
            scored.append(opp)

        return sorted(scored, key=lambda x: x["score"], reverse=True)

    async def _generate_outreach(self, opportunities: list[dict], target_domain: str, topic: str) -> list[dict]:
        for opp in opportunities[:10]:  # Only generate for top 10
            prompt = OUTREACH_PROMPT.format(
                source_domain=opp.get("source_domain", ""),
                source_url=opp["url"],
                target_url=f"https://{target_domain}/{topic.replace(' ', '-')}",
                topic=topic,
                reason=f"We have comprehensive content on {topic} that would add value to your readers.",
            )
            try:
                message = self.client.messages.create(
                    model=settings.claude_model,
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = message.content[0].text.strip()
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
                email_data = json.loads(raw)
                opp["outreach_email"] = email_data
            except Exception:
                opp["outreach_email"] = {"subject": "Link opportunity", "body": ""}
        return opportunities

    async def _save_opportunities(self, site_id: int, opportunities: list[dict]) -> list[int]:
        ids = []
        for opp in opportunities:
            record = BacklinkOpportunity(
                site_id=site_id,
                target_url=opp["url"],
                source_domain=opp.get("source_domain", ""),
                anchor=opp.get("title", ""),
                score=opp.get("score", 0.0),
                opportunity_type=opp.get("type", "unknown"),
                outreach_email=json.dumps(opp.get("outreach_email", {})),
                status="new",
            )
            self.db.add(record)
            await self.db.flush()
            await self.db.refresh(record)
            ids.append(record.id)
        return ids
