"""DataForSEO — real keyword volume + difficulty for EN and AR keywords.

Sign-up is free at https://dataforseo.com
Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables.

Endpoints used:
  POST /v3/keywords_data/google_ads/keywords_for_keywords/live
    → Given seed keywords, returns up to N related keywords with search_volume +
      competition_index (0–100, acts as keyword difficulty).

  POST /v3/keywords_data/google_ads/search_volume/live
    → Exact volume lookup for a known list of keywords.
"""
from __future__ import annotations

import base64
from typing import Any

import httpx

from backend.config import settings

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

    # DataForSEO accepts up to 20 seed keywords per request
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(seed_keywords), 20):
            chunk = seed_keywords[i : i + 20]
            payload = [
                {
                    "keywords": chunk,
                    "language_code": language_code,
                    "location_code": loc,
                    "limit": limit,
                    "include_seed_keyword": True,
                    "order_by": ["search_volume,desc"],
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
                for task in data.get("tasks", []):
                    for res in task.get("result") or []:
                        for item in res.get("items") or []:
                            kw = (item.get("keyword") or "").strip()
                            if not kw:
                                continue
                            results.append(
                                {
                                    "keyword": kw,
                                    "volume": item.get("search_volume"),
                                    "difficulty": item.get("competition_index"),
                                    "cpc": item.get("cpc"),
                                    "language": language_code,
                                }
                            )
            except Exception:
                pass  # don't abort entire research on one chunk failure

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

    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(keywords), 700):
            chunk = keywords[i : i + 700]
            payload = [
                {
                    "keywords": chunk,
                    "language_code": language_code,
                    "location_code": loc,
                }
            ]
            try:
                resp = await client.post(
                    f"{_BASE}/keywords_data/google_ads/search_volume/live",
                    json=payload,
                    headers=_auth(),
                )
                resp.raise_for_status()
                data = resp.json()
                for task in data.get("tasks", []):
                    for res in task.get("result") or []:
                        kw = (res.get("keyword") or "").strip().lower()
                        if kw:
                            volume_map[kw] = {
                                "volume": res.get("search_volume"),
                                "difficulty": res.get("competition_index"),
                                "cpc": res.get("cpc"),
                            }
            except Exception:
                pass

    return volume_map
