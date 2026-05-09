"""Keyword volume estimation — free sources when DataForSEO is not available.

Priority order tried by get_trends_volume():
  1. SerpAPI Google Trends  — uses existing SERPAPI_KEY, proxied (no IP blocks)
  2. pytrends direct        — free but often blocked on cloud server IPs
  3. Returns empty dict     — difficulty estimates still run regardless

Volume values are relative interest (0–100), not absolute search counts.
Display them as-is; once DataForSEO is active, Refresh Volumes upgrades to real numbers.
"""
from __future__ import annotations

import asyncio
import httpx
from typing import Any

from backend.config import settings


async def _serpapi_trends(
    keywords: list[str],
    geo: str = "",
) -> dict[str, int]:
    """Fetch Google Trends interest via SerpAPI (proxied — works from cloud servers)."""
    if not settings.serpapi_key:
        return {}

    scores: dict[str, int] = {}
    # SerpAPI Trends allows up to 5 comparison keywords per request
    CHUNK = 5

    async with httpx.AsyncClient(timeout=12) as client:
        for i in range(0, len(keywords), CHUNK):
            chunk = keywords[i : i + CHUNK]
            # Build comma-separated query for multi-keyword comparison
            q = ",".join(chunk)
            params = {
                "engine": "google_trends",
                "q": q,
                "data_type": "TIMESERIES",
                "date": "today 12-m",
                "api_key": settings.serpapi_key,
            }
            if geo:
                params["geo"] = geo

            try:
                resp = await client.get("https://serpapi.com/search", params=params)
                data = resp.json()
                timeline = data.get("interest_over_time", {}).get("timeline_data", [])
                if not timeline:
                    continue

                # Average interest per keyword across all time points
                # Use lowercase keys to handle SerpAPI case normalisation
                sums: dict[str, list[int]] = {kw.lower(): [] for kw in chunk}
                kw_lower_to_orig: dict[str, str] = {kw.lower(): kw for kw in chunk}
                for point in timeline:
                    for val in point.get("values", []):
                        kw_key = val.get("query", "").lower()
                        v = val.get("extracted_value", 0)
                        if kw_key in sums:
                            sums[kw_key].append(int(v) if v else 0)

                for kw_key, vals in sums.items():
                    if vals:
                        orig = kw_lower_to_orig.get(kw_key, kw_key)
                        scores[orig] = round(sum(vals) / len(vals))
            except Exception:
                pass

            if i + CHUNK < len(keywords):
                await asyncio.sleep(0.5)

    return scores


async def _pytrends_direct(
    keywords: list[str],
    geo: str = "",
) -> dict[str, int]:
    """Fetch Google Trends via pytrends (direct — may be blocked on cloud IPs)."""
    try:
        from pytrends.request import TrendReq  # type: ignore
    except ImportError:
        return {}

    scores: dict[str, int] = {}
    CHUNK = 5

    def _fetch(chunk: list[str]) -> dict[str, int]:
        try:
            pt = TrendReq(hl="en-US", tz=0, timeout=(10, 20), retries=1, backoff_factor=0.5)
            pt.build_payload(chunk, cat=0, timeframe="today 12-m", geo=geo)
            df = pt.interest_over_time()
            if df.empty:
                return {}
            return {kw: int(df[kw].mean().round()) for kw in chunk if kw in df.columns}
        except Exception:
            return {}

    for i in range(0, len(keywords), CHUNK):
        chunk = keywords[i : i + CHUNK]
        try:
            result = await asyncio.to_thread(_fetch, chunk)
            scores.update(result)
        except Exception:
            pass
        if i + CHUNK < len(keywords):
            await asyncio.sleep(1.5)

    return scores


async def get_trends_volume(
    keywords: list[str],
    geo: str = "",
) -> dict[str, int]:
    """Return relative Google Trends interest (0–100) per keyword.

    Tries SerpAPI first (proxied, reliable), then pytrends direct.
    Returns empty dict on total failure — never raises.
    """
    if not keywords:
        return {}

    # Try SerpAPI first (proxied residential IPs — won't be blocked)
    scores = await _serpapi_trends(keywords, geo=geo)
    if scores:
        return scores

    # Fallback: direct pytrends (free but cloud IPs often blocked)
    return await _pytrends_direct(keywords, geo=geo)


def estimate_difficulty(keyword: str) -> int:
    """Rule-based keyword difficulty estimate (0–100).

    Based on word count and search intent signals.
    - 1 word  → ~75 (very competitive generic terms)
    - 2 words → ~55 (medium competition)
    - 3 words → ~40 (lower competition)
    - 4+ words → ~25 (long-tail, easiest)
    Informational signals (-15), commercial signals (+10).
    """
    kw = keyword.lower().strip()
    words = kw.split()
    n = len(words)

    base = 75 if n == 1 else 55 if n == 2 else 40 if n == 3 else 25

    info_signals = {
        # English
        "how", "what", "why", "when", "where", "which", "guide", "tutorial",
        "tips", "learn", "explained", "examples", "definition", "meaning",
        # Arabic
        "كيف", "ما", "لماذا", "متى", "أين", "دليل", "شرح", "نصائح",
        "تعلم", "مقال", "معنى", "تعريف", "طريقة",
    }
    if any(w in info_signals for w in words):
        base -= 15

    commercial_signals = {
        # English
        "best", "buy", "price", "cost", "cheap", "top", "review", "reviews",
        "compare", "vs", "alternative", "affordable", "premium",
        # Arabic
        "أفضل", "شراء", "سعر", "تكلفة", "عروض", "خصم", "مراجعة",
        "مقارنة", "رخيص", "احسن",
    }
    if any(w in commercial_signals for w in words):
        base += 10

    return max(0, min(100, base))
