"""Keyword Intelligence — intent classification + cluster mapping via LLM."""
from __future__ import annotations

import asyncio
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

Rules:
- informational: how-to, what-is, guides, tutorials, tips
- commercial: best X, top X, reviews, comparisons, affordable/cheap/premium
- transactional: buy, price, cost, order, quote, near me, for sale
- navigational: brand names, site navigation keywords

Return a JSON array. Each item must have exactly: keyword, intent, cluster.
Only return valid JSON — no markdown, no explanation.

Keywords:
{keywords}
"""


def _rule_based_classify(keyword: str) -> dict[str, str]:
    """Fast rule-based fallback when LLM is unavailable."""
    kw = keyword.lower()

    transactional_signals = [
        "buy", "order", "price", "cost", "quote", "cheap",
        "near me", "for sale", "hire", "شراء", "سعر", "تكلفة",
        "اشتري", "بسعر", "توصيل",
    ]
    commercial_signals = [
        "best", "top", "review", "compare", "vs", "alternative", "affordable",
        "premium", "professional", "rated", "أفضل", "مقارنة", "تقييم",
    ]
    informational_signals = [
        "how", "what", "why", "when", "guide", "tutorial", "tips", "learn",
        "explained", "examples", "get started", "كيف", "ما هو", "ما هي",
        "لماذا", "دليل", "شرح", "تعلم",
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
        saved_count = await self._save_keywords(site_id, classified)
        cluster_map = self._build_cluster_map(classified)

        return {
            "keywords": classified,
            "clusters": cluster_map,
            "cannibalization_alerts": cannibalisation,
            "total": len(classified),
            "saved": saved_count,
        }

    async def _classify_intent(self, enriched: list[dict]) -> list[dict]:
        """Use LLM (Groq) to classify intent; fall back to rules if LLM unavailable."""
        keyword_list = [item["keyword"] for item in enriched]
        enriched_map = {item["keyword"]: item for item in enriched}

        classified_list: list[dict] = []

        # Lowercase input set for fast membership checks
        input_kws_lower = {kw.lower() for kw in keyword_list}

        if llm_is_available():
            # Process in batches of 60 to stay within LLM token limits
            BATCH = 60
            for i in range(0, len(keyword_list), BATCH):
                batch = keyword_list[i : i + BATCH]
                prompt = INTENT_PROMPT.format(
                    keywords="\n".join(f"- {kw}" for kw in batch)
                )
                try:
                    # 30 s per batch; prevents stalled workers on slow Groq responses
                    batch_result = await asyncio.wait_for(
                        self.llm.generate_json_async(prompt), timeout=30
                    )
                    if isinstance(batch_result, list):
                        # Filter out hallucinated keywords the LLM invented
                        valid = [
                            r for r in batch_result
                            if isinstance(r, dict) and r.get("keyword", "").lower() in input_kws_lower
                        ]
                        classified_list.extend(valid)
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

        # Fill in any keywords the LLM silently dropped from its response
        classified_kws_lower = {item.get("keyword", "").lower() for item in classified_list}
        for kw in keyword_list:
            if kw.lower() not in classified_kws_lower:
                classified_list.append({"keyword": kw, **_rule_based_classify(kw)})

        # Merge volume + difficulty back in (case-insensitive lookup)
        enriched_map_lower = {k.lower(): v for k, v in enriched_map.items()}
        for item in classified_list:
            kw_key = item.get("keyword", "").lower()
            extra = enriched_map_lower.get(kw_key) or enriched_map.get(item.get("keyword", ""), {})
            item.setdefault("volume", extra.get("volume"))
            item.setdefault("difficulty", extra.get("difficulty"))
            item.setdefault("language", extra.get("language", "en"))
            item.setdefault("serp_features", [])

        return classified_list

    async def _detect_cannibalization(self, site_id: int, classified: list[dict]) -> list[dict]:
        """Detect multiple keywords targeting the same URL (requires GSC data)."""
        # URLs are only populated by the GSC sync module — skip the DB round-trip
        # when no keywords have URLs yet (the common case during auto-research).
        count_row = await self.db.execute(
            select(Keyword.id).where(Keyword.site_id == site_id, Keyword.url.isnot(None)).limit(1)
        )
        if count_row.first() is None:
            return []  # no URL data yet — cannibalization check is a post-GSC feature

        existing_stmt = select(Keyword).where(Keyword.site_id == site_id, Keyword.url.isnot(None))
        result = await self.db.execute(existing_stmt)
        existing = result.scalars().all()

        url_keyword_map: dict[str, list[str]] = {}
        for kw in existing:
            if kw.url:
                url_keyword_map.setdefault(kw.url, []).append(kw.keyword)

        return [
            {"url": url, "competing_keywords": kws}
            for url, kws in url_keyword_map.items()
            if len(kws) > 1
        ]

    def _build_cluster_map(self, classified: list[dict]) -> dict[str, list[dict]]:
        clusters: dict[str, list[dict]] = {}
        for item in classified:
            cluster = item.get("cluster", "general")
            clusters.setdefault(cluster, []).append(item)
        return clusters

    async def _save_keywords(self, site_id: int, classified: list[dict]) -> int:
        """Bulk-insert keywords, skipping duplicates via ON CONFLICT DO NOTHING.

        Uses a single INSERT statement so there are no per-row savepoints.
        The DB unique constraint on (site_id, keyword) is the authoritative guard.
        Returns the number of rows actually inserted.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        # In-memory dedup (case-insensitive) to collapse duplicates within this batch
        # before hitting the DB (avoids unnecessary conflict rows).
        seen: set[str] = set()
        rows: list[dict] = []
        for item in classified:
            kw_text = (item.get("keyword") or "").strip()
            if not kw_text or kw_text.lower() in seen:
                continue
            seen.add(kw_text.lower())
            rows.append({
                "site_id":   site_id,
                "keyword":   kw_text,
                "intent":    item.get("intent"),
                "cluster":   item.get("cluster"),
                "volume":    item.get("volume"),
                "difficulty": item.get("difficulty"),
                "language":  item.get("language", "en"),
            })

        if not rows:
            return 0

        stmt = (
            pg_insert(Keyword)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_site_keyword")
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount or 0
