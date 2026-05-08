"""Google Trends — free relative search interest (0–100) as volume proxy.

Used as a fallback when DataForSEO is not configured or not yet activated.
Google Trends returns relative interest (0=lowest, 100=peak), not absolute
search volume — but it's free, no API key needed, and supports Arabic.

Usage:
    scores = await get_trends_volume(["real estate egypt", "karnak developments"])
    # → {"real estate egypt": 72, "karnak developments": 18}
"""
from __future__ import annotations

import asyncio
from typing import Any


async def get_trends_volume(
    keywords: list[str],
    geo: str = "",        # "" = worldwide, "EG" = Egypt, "SA" = Saudi Arabia
    timeframe: str = "today 12-m",
) -> dict[str, int | None]:
    """Return relative Google Trends interest (0–100) for each keyword.

    Processes in groups of 5 (Google Trends limit per request).
    Returns empty dict on any failure — never raises.
    """
    if not keywords:
        return {}

    try:
        from pytrends.request import TrendReq  # type: ignore
    except ImportError:
        return {}

    scores: dict[str, int | None] = {}

    def _fetch_chunk(chunk: list[str]) -> dict[str, int]:
        try:
            pt = TrendReq(hl="en-US", tz=0, timeout=(10, 25), retries=1, backoff_factor=0.5)
            pt.build_payload(chunk, cat=0, timeframe=timeframe, geo=geo)
            df = pt.interest_over_time()
            if df.empty:
                return {}
            result = {}
            for kw in chunk:
                if kw in df.columns:
                    result[kw] = int(df[kw].mean().round())
            return result
        except Exception:
            return {}

    # Google Trends allows max 5 keywords per request
    CHUNK = 5
    for i in range(0, len(keywords), CHUNK):
        chunk = keywords[i : i + CHUNK]
        try:
            chunk_scores = await asyncio.to_thread(_fetch_chunk, chunk)
            scores.update(chunk_scores)
        except Exception:
            pass
        # Small delay between requests to avoid rate limiting
        if i + CHUNK < len(keywords):
            await asyncio.sleep(1.5)

    return scores


async def estimate_difficulty(keyword: str) -> int | None:
    """Rough keyword difficulty estimate based on word count and common patterns.

    Returns 0–100.  Not accurate but better than nothing when no API is available.
    - Short, generic single words → higher difficulty (more competition)
    - Long-tail phrases → lower difficulty
    - Question phrases → lower difficulty (informational, less commercial comp.)
    """
    kw = keyword.lower().strip()
    words = kw.split()
    n = len(words)

    if n == 1:
        base = 75
    elif n == 2:
        base = 55
    elif n == 3:
        base = 40
    else:
        base = 25  # long-tail → easier

    # Reduce for question/informational signals
    info_signals = {"how", "what", "why", "when", "where", "which", "guide", "tutorial", "tips"}
    if any(w in info_signals for w in words):
        base -= 15

    # Increase for high-competition commercial signals
    commercial_signals = {"best", "buy", "price", "cost", "cheap", "top", "review"}
    if any(w in commercial_signals for w in words):
        base += 10

    return max(0, min(100, base))
