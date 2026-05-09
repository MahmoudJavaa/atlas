"""DataForSEO — real keyword volume + difficulty for EN and AR keywords.

Sign-up is free at https://dataforseo.com
Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables.

Endpoints used:
  POST /v3/keywords_data/google_ads/keywords_for_keywords/live
    → Given seed keywords, returns up to N related keywords with search_volume +
      competition_index (0–100, acts as keyword difficulty).

  POST /v3/keywords_data/google_ads/search_volume/live
    → Exact volume lookup for a known list of keywords.

Error codes:
  40104 — account not verified / insufficient funds (returned as HTTP 200 body).
           Detected explicitly; treated as "not configured" so callers fall back cleanly.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import httpx

from backend.config import settings

log = logging.getLogger(__name__)

_BASE = "https://api.dataforseo.com/v3"

# DataForSEO location codes (most used SEO markets)
_LOCATION: dict[str, int] = {
    "en":    2840,   # United States
    "en-gb": 2826,   # United Kingdom
    "en-au": 2036,   # Australia
    "ar":    2682,   # Saudi Arabia (largest Arabic-speaking SEO market)
    "ar-ae": 2784,   # UAE
    "ar-eg": 2818,   # Egypt
}


def _is_configured() -> bool:
    return bool(settings.dataforseo_login and settings.dataforseo_password)


def _auth() -> dict[str, str]:
    token = base64.b64encode(
        f"{settings.dataforseo_login}:{settings.dataforseo_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


async def get_keyword_ideas(
    seed_keywords: list[str],
    language_code: str = "en",
    location_code: int | None = None,
    limit: int = 700,
) -> list[dict[str, Any]]:
    """Return related keyword ideas with real search_volume + difficulty (0–100).

    Falls back to empty list if DataForSEO credentials are not configured.
    """
    if not _is_configured() or not seed_keywords:
        return []

    loc = location_code or _LOCATION.get(language_code, 2840)
    results: list[dict] = []

    async def _fetch_chunk(client: httpx.AsyncClient, chunk: list[str]) -> list[dict]:
        payload = [
            {
                "keywords": chunk,
                "language_code": language_code,
                "location_code": loc,
                "limit": limit,
                "include_seed_keyword": True,
            }
        ]
        try:
            resp = await client.post(
                f"{_BASE}/keywords_data/google_ads/keywords_for_keywords/live",
                json=payload,
                headers=_auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            chunk_results: list[dict] = []
            for task in data.get("tasks", []):
                # 40104 = account not verified / insufficient funds (HTTP 200 body error)
                if task.get("status_code") == 40104:
                    log.warning("DataForSEO 40104: account not verified or insufficient funds")
                    return []
                for res in task.get("result") or []:
                    for item in res.get("items") or []:
                        kw = (item.get("keyword") or "").strip()
                        if not kw:
                            continue
                        chunk_results.append(
                            {
                                "keyword": kw,
                                "volume": item.get("search_volume"),
                                "difficulty": item.get("competition_index"),
                                "cpc": item.get("cpc"),
                                "language": language_code,
                            }
                        )
            return chunk_results
        except Exception:
            return []  # don't abort entire research on one chunk failure

    # DataForSEO accepts up to 20 seed keywords per request — run chunks in parallel
    chunks = [seed_keywords[i : i + 20] for i in range(0, len(seed_keywords), 20)]
    async with httpx.AsyncClient(timeout=30) as client:
        chunk_results = await asyncio.gather(*[_fetch_chunk(client, c) for c in chunks])
    for cr in chunk_results:
        results.extend(cr)

    # Deduplicate (keep highest-volume entry per keyword)
    seen: dict[str, dict] = {}
    for item in results:
        key = item["keyword"].lower()
        if key not in seen or (item.get("volume") or 0) > (seen[key].get("volume") or 0):
            seen[key] = item

    # Sort by volume descending
    return sorted(seen.values(), key=lambda x: x.get("volume") or 0, reverse=True)


async def get_search_volume(
    keywords: list[str],
    language_code: str = "en",
    location_code: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch exact search volume + difficulty for a known list of keywords.

    Returns a dict keyed by lowercase keyword.
    """
    if not _is_configured() or not keywords:
        return {}

    loc = location_code or _LOCATION.get(language_code, 2840)
    volume_map: dict[str, dict] = {}

    async def _fetch_volume_chunk(client: httpx.AsyncClient, chunk: list[str]) -> dict[str, dict]:
        payload = [{"keywords": chunk, "language_code": language_code, "location_code": loc}]
        try:
            resp = await client.post(
                f"{_BASE}/keywords_data/google_ads/search_volume/live",
                json=payload,
                headers=_auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            result: dict[str, dict] = {}
            for task in data.get("tasks", []):
                if task.get("status_code") == 40104:
                    log.warning("DataForSEO 40104: account not verified or insufficient funds")
                    return {}
                for res in task.get("result") or []:
                    kw = (res.get("keyword") or "").strip().lower()
                    if kw:
                        result[kw] = {
                            "volume": res.get("search_volume"),
                            "difficulty": res.get("competition_index"),
                            "cpc": res.get("cpc"),
                        }
            return result
        except Exception:
            return {}

    chunks = [keywords[i : i + 700] for i in range(0, len(keywords), 700)]
    async with httpx.AsyncClient(timeout=30) as client:
        chunk_maps = await asyncio.gather(*[_fetch_volume_chunk(client, c) for c in chunks])
    for cm in chunk_maps:
        volume_map.update(cm)

    return volume_map
