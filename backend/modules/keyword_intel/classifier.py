"""Keyword Intelligence — intent classification + cluster mapping via Claude + SerpAPI."""
from __future__ import annotations

import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import anthropic
from backend.config import settings
from backend.models.keyword import Keyword


INTENT_PROMPT = """You are an SEO keyword intent classifier.

Given the following keywords, classify each one with:
1. intent: one of [informational, commercial, transactional, navigational]
2. cluster: a short topic cluster name (2-5 words)
3. funnel_stage: one of [TOFU, MOFU, BOFU]

Return a JSON array where each item has: keyword, intent, cluster, funnel_stage.
Only return valid JSON — no markdown, no explanation.

Keywords:
{keywords}
"""


class KeywordClassifier:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def run(self, site_id: int, seed_keywords: list[str]) -> dict[str, Any]:
        """Classify keywords and store in DB. Returns structured keyword map."""
        # Enrich via SerpAPI if key available
        enriched = await self._enrich_via_serp(seed_keywords)

        # Classify intent via Claude
        classified = await self._classify_intent(enriched)

        # Detect cannibalization
        cannibalisation = await self._detect_cannibalization(site_id, classified)

        # Persist to DB
        await self._save_keywords(site_id, classified)

        # Build cluster map
        cluster_map = self._build_cluster_map(classified)

        return {
            "keywords": classified,
            "clusters": cluster_map,
            "cannibalization_alerts": cannibalisation,
            "total": len(classified),
        }

    async def _enrich_via_serp(self, keywords: list[str]) -> list[dict]:
        """Optionally enrich via SerpAPI — falls back to raw keywords if no key."""
        if not settings.serpapi_key:
            return [{"keyword": kw, "volume": None, "serp_features": []} for kw in keywords]

        import httpx
        enriched = []
        async with httpx.AsyncClient(timeout=10) as client:
            for kw in keywords:
                try:
                    resp = await client.get(
                        "https://serpapi.com/search",
                        params={"q": kw, "api_key": settings.serpapi_key, "engine": "google", "num": 10},
                    )
                    data = resp.json()
                    features = [k for k in data.get("search_information", {}).keys()]
                    enriched.append({
                        "keyword": kw,
                        "volume": None,
                        "serp_features": features,
                        "related": [r.get("query", "") for r in data.get("related_searches", [])[:5]],
                        "paa": [p.get("question", "") for p in data.get("related_questions", [])[:5]],
                    })
                except Exception:
                    enriched.append({"keyword": kw, "volume": None, "serp_features": []})
        return enriched

    async def _classify_intent(self, enriched: list[dict]) -> list[dict]:
        """Use Claude to classify intent for all keywords."""
        keyword_list = [item["keyword"] for item in enriched]
        prompt = INTENT_PROMPT.format(keywords="\n".join(f"- {kw}" for kw in keyword_list))

        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        try:
            classified_list = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: return unclassified
            classified_list = [
                {"keyword": kw, "intent": "informational", "cluster": "general", "funnel_stage": "TOFU"}
                for kw in keyword_list
            ]

        # Merge enrichment data back in
        enriched_map = {item["keyword"]: item for item in enriched}
        for item in classified_list:
            extra = enriched_map.get(item["keyword"], {})
            item["volume"] = extra.get("volume")
            item["serp_features"] = extra.get("serp_features", [])
            item["related"] = extra.get("related", [])
            item["paa"] = extra.get("paa", [])

        return classified_list

    async def _detect_cannibalization(self, site_id: int, classified: list[dict]) -> list[dict]:
        """Check if multiple DB keywords point to the same URL for similar terms."""
        alerts = []
        existing_stmt = select(Keyword).where(Keyword.site_id == site_id, Keyword.url.isnot(None))
        result = await self.db.execute(existing_stmt)
        existing = result.scalars().all()

        url_keyword_map: dict[str, list[str]] = {}
        for kw in existing:
            if kw.url:
                url_keyword_map.setdefault(kw.url, []).append(kw.keyword)

        for url, kws in url_keyword_map.items():
            if len(kws) > 1:
                alerts.append({"url": url, "competing_keywords": kws})

        return alerts

    def _build_cluster_map(self, classified: list[dict]) -> dict[str, list[dict]]:
        clusters: dict[str, list[dict]] = {}
        for item in classified:
            cluster = item.get("cluster", "general")
            clusters.setdefault(cluster, []).append(item)
        return clusters

    async def _save_keywords(self, site_id: int, classified: list[dict]):
        for item in classified:
            kw = Keyword(
                site_id=site_id,
                keyword=item["keyword"],
                intent=item.get("intent"),
                cluster=item.get("cluster"),
                volume=item.get("volume"),
            )
            self.db.add(kw)
        await self.db.flush()
