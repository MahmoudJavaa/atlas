"""Keyword Intelligence — intent classification + cluster mapping via LLM."""
from __future__ import annotations

import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.llm import get_llm, llm_is_available
from backend.models.keyword import Keyword


INTENT_PROMPT = """You are an SEO keyword intent classifier.

Given the following keywords, classify each one with:
1. intent: one of [informational, commercial, transactional, navigational]
2. cluster: a short topic cluster name (2-5 words, in the same language as the keyword)
3. funnel_stage: one of [TOFU, MOFU, BOFU]

Rules:
- informational: how-to, what-is, guides, tutorials, tips
- commercial: best X, top X, reviews, comparisons, affordable/cheap/premium
- transactional: buy, price, cost, order, quote, near me, for sale
- navigational: brand names, site navigation keywords

Return a JSON array. Each item must have: keyword, intent, cluster, funnel_stage.
Only return valid JSON — no markdown, no explanation.

Keywords:
{keywords}
"""


def _rule_based_classify(keyword: str) -> dict[str, str]:
    """Fast rule-based fallback when LLM is unavailable."""
    kw = keyword.lower()

    transactional_signals = [
        "buy", "order", "price", "cost", "quote", "cheap", "affordable",
        "near me", "for sale", "hire", "get", "شراء", "سعر", "تكلفة",
        "اشتري", "بسعر", "توصيل",
    ]
    commercial_signals = [
        "best", "top", "review", "compare", "vs", "alternative", "affordable",
        "premium", "professional", "rated", "أفضل", "مقارنة", "تقييم",
    ]
    informational_signals = [
        "how", "what", "why", "when", "guide", "tutorial", "tips", "learn",
        "explained", "examples", "كيف", "ما هو", "ما هي", "لماذا", "دليل",
        "شرح", "تعلم",
    ]

    for sig in transactional_signals:
        if sig in kw:
            return {"intent": "transactional", "cluster": "purchase intent", "funnel_stage": "BOFU"}
    for sig in commercial_signals:
        if sig in kw:
            return {"intent": "commercial", "cluster": "commercial research", "funnel_stage": "MOFU"}
    for sig in informational_signals:
        if sig in kw:
            return {"intent": "informational", "cluster": "informational", "funnel_stage": "TOFU"}

    return {"intent": "informational", "cluster": "general", "funnel_stage": "TOFU"}


class KeywordClassifier:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm()

    async def run(self, site_id: int, seed_keywords: list[str]) -> dict[str, Any]:
        """Classify keywords (with enrichment data already merged in) and store in DB."""
        # seed_keywords may be plain strings or dicts with {keyword, volume, difficulty, language}
        enriched = []
        for item in seed_keywords:
            if isinstance(item, dict):
                enriched.append(item)
            else:
                enriched.append({"keyword": item, "volume": None, "difficulty": None, "language": "en"})

        classified = await self._classify_intent(enriched)
        cannibalisation = await self._detect_cannibalization(site_id, classified)
        await self._save_keywords(site_id, classified)
        cluster_map = self._build_cluster_map(classified)

        return {
            "keywords": classified,
            "clusters": cluster_map,
            "cannibalization_alerts": cannibalisation,
            "total": len(classified),
        }

    async def _classify_intent(self, enriched: list[dict]) -> list[dict]:
        """Use LLM (Groq) to classify intent; fall back to rules if LLM unavailable."""
        keyword_list = [item["keyword"] for item in enriched]
        enriched_map = {item["keyword"]: item for item in enriched}

        classified_list: list[dict] = []

        if llm_is_available():
            # Process in batches of 60 to stay within LLM token limits
            BATCH = 60
            for i in range(0, len(keyword_list), BATCH):
                batch = keyword_list[i : i + BATCH]
                prompt = INTENT_PROMPT.format(
                    keywords="\n".join(f"- {kw}" for kw in batch)
                )
                try:
                    batch_result = await self.llm.generate_json_async(prompt)
                    if isinstance(batch_result, list):
                        classified_list.extend(batch_result)
                    else:
                        raise ValueError("LLM returned non-list")
                except Exception:
                    # Rule-based fallback for this batch
                    for kw in batch:
                        classified_list.append({"keyword": kw, **_rule_based_classify(kw)})
        else:
            # Full rule-based fallback
            for kw in keyword_list:
                classified_list.append({"keyword": kw, **_rule_based_classify(kw)})

        # Merge volume + difficulty back in
        for item in classified_list:
            extra = enriched_map.get(item.get("keyword", ""), {})
            item.setdefault("volume", extra.get("volume"))
            item.setdefault("difficulty", extra.get("difficulty"))
            item.setdefault("language", extra.get("language", "en"))
            item.setdefault("serp_features", [])

        return classified_list

    async def _detect_cannibalization(self, site_id: int, classified: list[dict]) -> list[dict]:
        """Detect multiple keywords targeting the same URL."""
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
        """Insert keywords, skipping duplicates that already exist for this site."""
        # Load existing keywords to avoid duplicates
        existing_result = await self.db.execute(
            select(Keyword.keyword).where(Keyword.site_id == site_id)
        )
        existing_set: set[str] = {row[0].lower() for row in existing_result.all()}

        for item in classified:
            kw_text = (item.get("keyword") or "").strip()
            if not kw_text or kw_text.lower() in existing_set:
                continue
            existing_set.add(kw_text.lower())
            try:
                async with self.db.begin_nested():
                    self.db.add(
                        Keyword(
                            site_id=site_id,
                            keyword=kw_text,
                            intent=item.get("intent"),
                            cluster=item.get("cluster"),
                            volume=item.get("volume"),
                            difficulty=item.get("difficulty"),
                            language=item.get("language", "en"),
                        )
                    )
            except Exception:
                pass  # savepoint — only this row rolls back

        await self.db.flush()
