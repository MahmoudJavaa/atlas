"""Keyword Intelligence API routes."""
from __future__ import annotations

import asyncio
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.models.keyword import Keyword
from backend.auth import get_current_user

router = APIRouter(
    prefix="/keywords",
    tags=["keywords"],
    dependencies=[Depends(get_current_user)],
)


# ── Request models ────────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    site_id: int
    seed_keywords: list[str]


class ResearchRequest(BaseModel):
    language: str = "both"   # "en" | "ar" | "both"
    location_code: Optional[int] = None


# ── Shared modifier lists ─────────────────────────────────────────────────────

EN_MODS = [
    "what is {t}", "how to {t}", "{t} guide", "{t} tips", "{t} tutorial",
    "best {t}", "top {t}", "affordable {t}", "professional {t}",
    "buy {t}", "{t} price", "{t} cost", "{t} near me", "{t} service",
    "how much does {t} cost", "{t} review", "{t} reviews", "{t} vs",
    "{t} for beginners", "{t} examples", "{t} help", "{t} benefits",
    "{t} company", "{t} online", "{t} in egypt", "{t} in cairo",
    "best {t} egypt", "{t} developer", "{t} project", "{t} investment",
]

AR_MODS = [
    "ما هو {t}", "كيف {t}", "دليل {t}", "نصائح {t}", "أفضل {t}",
    "سعر {t}", "تكلفة {t}", "شراء {t}", "خدمة {t}", "شركة {t}",
    "مميزات {t}", "عروض {t}", "خبراء {t}", "{t} للمبتدئين",
    "{t} في مصر", "{t} في القاهرة", "أفضل {t} مصر", "{t} للبيع",
    "أسعار {t}", "{t} جديد", "مشاريع {t}",
]

EN_STOP = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "day", "get", "has", "him", "his",
    "how", "man", "new", "now", "old", "see", "two", "way", "who", "boy",
    "did", "its", "let", "put", "say", "she", "too", "use", "that", "this",
    "with", "have", "from", "they", "will", "been", "said", "each", "which",
    "their", "time", "there", "would", "make", "like", "into", "than", "more",
    "very", "just", "some", "what", "know", "take", "year", "your", "good",
    "much", "also", "over", "such", "even", "most", "give", "well", "when",
    "here", "then", "both", "does", "come", "could", "other", "were", "those",
    "only", "many", "after", "about", "them", "these", "made", "where",
    "need", "back", "long", "home", "down", "work", "part", "high", "page",
    "same", "life", "next", "last", "read", "more", "click", "view", "open",
    "close", "show", "hide", "type", "size", "copy", "load", "data",
}

AR_STOP = {
    "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "تلك",
    "التي", "الذي", "كان", "كانت", "يكون", "تكون", "قد", "لقد", "أن",
    "إن", "لا", "لم", "لن", "ما", "مما", "أو", "أي", "كل", "بعض",
    "كما", "حتى", "منذ", "بين", "خلال", "حول", "نحو", "ضد", "عند",
    "بعد", "قبل", "فوق", "تحت", "أمام", "وراء", "هنا", "هناك", "الان",
}

# Image / file-name noise — these seeds are useless for keyword research
_IMG_NOISE = re.compile(
    r"\b(?:webp|jpeg|jpg|png|gif|svg|avif|scaled|crop|thumb|resize|banner|hero|icon|logo)\b"
    r"|\b\d{3,4}x\d{3,4}\b"
    r"|\b(?:1080|1440|1600|1920|2048|2560|3840|720|480|360)\b",
    re.IGNORECASE,
)


# ── Module-level helpers ──────────────────────────────────────────────────────

def _is_clean_seed(phrase: str) -> bool:
    """True only when the phrase looks like a real keyword (not an image filename)."""
    if _IMG_NOISE.search(phrase):
        return False
    alpha = [w for w in phrase.split() if re.match(r"[a-zA-Z؀-ۿ]{3,}", w)]
    return len(alpha) >= 1


def _phrases_from_text(text: str, stop: set) -> list[str]:
    words = [w for w in text.split() if len(w) > 3 and w not in stop]
    out: list[str] = []
    for i, w in enumerate(words):
        out.append(w)
        if i + 1 < len(words):
            out.append(f"{words[i]} {words[i+1]}")
        if i + 2 < len(words):
            out.append(f"{words[i]} {words[i+1]} {words[i+2]}")
    return out


def _seeds_from_site(name: str, url: str) -> list[str]:
    """Derive keyword seeds from site name + domain when crawl data is images-only."""
    seeds: list[str] = []
    domain = re.sub(r"https?://(?:www\.)?", "", url).split("/")[0]
    for part in re.split(r"[-.]", domain):
        if len(part) >= 4 and part not in ("com", "net", "org", "app", "www"):
            seeds.append(part.lower())
    # camelCase split on site name
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    for word in spaced.lower().split():
        if len(word) >= 4:
            seeds.append(word)
    # 2-word combos
    words = list(dict.fromkeys(seeds))[:6]
    for i in range(len(words)):
        for j in range(i + 1, min(i + 3, len(words))):
            seeds.append(" ".join(words[i : j + 1]))
    return list(dict.fromkeys(seeds))[:20]


def _build_template_keywords(seeds: list[str], mods: list[str], lang: str, cap: int = 700) -> list[dict]:
    """Expand seed topics with modifier templates, deduplicate, return list of dicts."""
    raw: list[str] = list(seeds)
    for t in seeds[:30]:
        for mod in mods:
            raw.append(mod.format(t=t))
    seen: set[str] = set()
    result: list[dict] = []
    for k in raw:
        k = k.strip()
        if k and k not in seen and len(k) >= 3:
            seen.add(k)
            result.append({"keyword": k, "volume": None, "difficulty": None, "language": lang})
        if len(result) >= cap:
            break
    return result


def _kw_dict(k: Keyword) -> dict:
    return {
        "id": k.id,
        "keyword": k.keyword,
        "intent": k.intent,
        "cluster": k.cluster,
        "volume": k.volume,
        "difficulty": k.difficulty,
        "language": k.language or "en",
        "position": k.position,
        "clicks": k.clicks,
        "impressions": k.impressions,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/classify/sync")
async def classify_sync(data: ClassifyRequest, db: AsyncSession = Depends(get_db)):
    """Classify custom seed keywords, enrich with real volume data, and save."""
    from backend.modules.keyword_intel.classifier import KeywordClassifier
    from backend.modules.keyword_intel.dataforseo import get_search_volume

    def _detect_lang(kw: str) -> str:
        return "ar" if re.search(r"[؀-ۿ]", kw) else "en"

    en_kws = [k for k in data.seed_keywords if _detect_lang(k) == "en"]
    ar_kws = [k for k in data.seed_keywords if _detect_lang(k) == "ar"]

    enriched: list[dict] = []

    if en_kws:
        vol_map = await get_search_volume(en_kws, language_code="en")
        for kw in en_kws:
            v = vol_map.get(kw.lower(), {})
            enriched.append({"keyword": kw, "volume": v.get("volume"),
                             "difficulty": v.get("difficulty"), "language": "en"})

    if ar_kws:
        vol_map = await get_search_volume(ar_kws, language_code="ar")
        for kw in ar_kws:
            v = vol_map.get(kw.lower(), {})
            enriched.append({"keyword": kw, "volume": v.get("volume"),
                             "difficulty": v.get("difficulty"), "language": "ar"})

    if not enriched:
        enriched = [{"keyword": k, "volume": None, "difficulty": None, "language": "en"}
                    for k in data.seed_keywords]

    classifier = KeywordClassifier(db=db)
    return await classifier.run(site_id=data.site_id, seed_keywords=enriched)


@router.post("/auto-research/{site_id}")
async def auto_research(
    site_id: int,
    req: ResearchRequest = ResearchRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Auto-research keywords (DataForSEO for real data, templates as fallback)."""
    from backend.models.crawl import CrawlResult
    from backend.models.site import Site
    from backend.modules.keyword_intel.classifier import KeywordClassifier
    from backend.modules.keyword_intel.dataforseo import get_keyword_ideas, _is_configured

    # ── Site ─────────────────────────────────────────────────────────────────
    site_row = await db.execute(select(Site).where(Site.id == site_id))
    site = site_row.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # ── Crawl pages ──────────────────────────────────────────────────────────
    crawl_row = await db.execute(
        select(CrawlResult).where(CrawlResult.site_id == site_id).limit(200)
    )
    pages = crawl_row.scalars().all()
    if not pages:
        raise HTTPException(
            status_code=422,
            detail="No crawl data found. Run a site crawl first (Technical SEO tab).",
        )

    # ── Extract seeds from page titles + meta descriptions ───────────────────
    def _clean(text: str) -> str:
        text = re.sub(r"\s*[-|•·|]\s*.{0,40}$", "", text)
        text = re.sub(r"[^\w\s؀-ۿ]", " ", text)
        return text.strip().lower()

    en_topics: set[str] = set()
    ar_topics: set[str] = set()

    for page in pages:
        for raw_text in [page.title or "", (page.meta_desc or "")[:200]]:
            cleaned = _clean(raw_text)
            if not cleaned:
                continue
            if re.search(r"[؀-ۿ]", cleaned):
                ar_topics.update(_phrases_from_text(cleaned, AR_STOP))
            else:
                en_topics.update(_phrases_from_text(cleaned, EN_STOP))

    en_seeds = [t for t in en_topics if len(t) >= 4 and _is_clean_seed(t)][:40]
    ar_seeds = [t for t in ar_topics if len(t) >= 3 and _is_clean_seed(t)][:40]

    # If crawl gave too few clean EN seeds, derive from site name + domain
    if len(en_seeds) < 5:
        fallback = _seeds_from_site(getattr(site, "name", "") or "", getattr(site, "url", "") or "")
        seen_s: set[str] = set(en_seeds)
        for s in fallback:
            if s not in seen_s:
                seen_s.add(s)
                en_seeds.append(s)
        en_seeds = en_seeds[:40]

    do_en = req.language in ("en", "both")
    do_ar = req.language in ("ar", "both")
    use_dataforseo = _is_configured()
    new_keywords: list[dict] = []

    # ── Attempt DataForSEO (real volume + difficulty) ─────────────────────────
    if use_dataforseo:
        if do_en and en_seeds:
            en_ideas = await get_keyword_ideas(
                en_seeds,
                language_code="en",
                location_code=req.location_code,
                limit=700,
            )
            new_keywords.extend(en_ideas[:700])

        if do_ar:
            ar_idea_seeds = ar_seeds if ar_seeds else en_seeds[:20]
            ar_ideas = await get_keyword_ideas(
                ar_idea_seeds,
                language_code="ar",
                location_code=req.location_code,
                limit=400,
            )
            new_keywords.extend(ar_ideas[:400])

    # ── Template fallback (always runs if DataForSEO returned nothing) ────────
    if not new_keywords:
        use_dataforseo = False
        if do_en and en_seeds:
            new_keywords.extend(_build_template_keywords(en_seeds, EN_MODS, "en", 700))
        if do_ar and ar_seeds:
            new_keywords.extend(_build_template_keywords(ar_seeds, AR_MODS, "ar", 400))

    if not new_keywords:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Could not generate keywords — seeds: {len(en_seeds)} EN, "
                f"{len(ar_seeds)} AR. Check that the site crawl has real page content."
            ),
        )

    # ── Skip keywords already in DB ───────────────────────────────────────────
    existing_row = await db.execute(
        select(Keyword.keyword).where(Keyword.site_id == site_id)
    )
    existing_set: set[str] = {r[0].lower() for r in existing_row.all()}
    fresh = [kw for kw in new_keywords if kw["keyword"].lower() not in existing_set]

    # ── Classify intent + save in batches ─────────────────────────────────────
    classifier = KeywordClassifier(db=db)
    total_added = 0
    for i in range(0, len(fresh), 60):
        batch = fresh[i : i + 60]
        try:
            await classifier.run(site_id=site_id, seed_keywords=batch)
            total_added += len(batch)
        except Exception:
            pass

    # ── Return all keywords for this site ─────────────────────────────────────
    all_kws_row = await db.execute(
        select(Keyword)
        .where(Keyword.site_id == site_id)
        .order_by(Keyword.volume.desc().nullslast(), Keyword.id)
        .limit(2000)
    )
    all_kws = all_kws_row.scalars().all()

    return {
        "new_keywords_added": total_added,
        "total": len(all_kws),
        "used_dataforseo": use_dataforseo,
        "keywords": [_kw_dict(k) for k in all_kws],
    }


@router.post("/refresh-volumes/{site_id}")
async def refresh_volumes(site_id: int, db: AsyncSession = Depends(get_db)):
    """Re-fetch search volume + difficulty for all existing keywords.

    Priority:
      1. DataForSEO — real Google Ads volume + competition index (requires paid account)
      2. Google Trends — free relative interest (0–100) as volume proxy + rule-based KD estimate

    Safe to call any time — never deletes or reclassifies, only updates volume/difficulty.
    """
    from backend.modules.keyword_intel.dataforseo import get_search_volume, _is_configured
    from backend.modules.keyword_intel.trends import get_trends_volume, estimate_difficulty

    result = await db.execute(
        select(Keyword).where(Keyword.site_id == site_id).limit(2000)
    )
    kws = result.scalars().all()
    if not kws:
        return {"updated": 0, "total": 0, "source": "none"}

    en_kws = [k for k in kws if (k.language or "en") == "en"]
    ar_kws = [k for k in kws if k.language == "ar"]
    updated = 0
    source = "none"

    if _is_configured():
        # ── DataForSEO: real volume + difficulty ──────────────────────────────
        source = "dataforseo"
        for bucket, lang in [(en_kws, "en"), (ar_kws, "ar")]:
            if not bucket:
                continue
            texts = [k.keyword for k in bucket]
            vol_map = await get_search_volume(texts, language_code=lang)
            for kw in bucket:
                data = vol_map.get(kw.keyword.lower(), {})
                if data.get("volume") is not None:
                    kw.volume = data["volume"]
                    updated += 1
                if data.get("difficulty") is not None:
                    kw.difficulty = data["difficulty"]
    else:
        # ── Free fallback: rule-based difficulty + optional Google Trends ─────
        source = "estimated"

        # Step 1: Always set rule-based difficulty instantly (works everywhere)
        for kw in kws:
            if kw.difficulty is None:
                kw.difficulty = await estimate_difficulty(kw.keyword)
                updated += 1

        # Step 2: Try Google Trends for relative volume (may be blocked on cloud)
        try:
            en_texts = [k.keyword for k in en_kws if k.volume is None][:30]
            ar_texts = [k.keyword for k in ar_kws if k.volume is None][:20]

            if en_texts:
                en_scores = await asyncio.wait_for(
                    get_trends_volume(en_texts, geo=""), timeout=45
                )
                en_map = {k.keyword: k for k in en_kws}
                for keyword, score in en_scores.items():
                    if score and keyword in en_map and en_map[keyword].volume is None:
                        en_map[keyword].volume = score
                if en_scores:
                    source = "google_trends"

            if ar_texts:
                ar_scores = await asyncio.wait_for(
                    get_trends_volume(ar_texts, geo="SA"), timeout=45
                )
                ar_map = {k.keyword: k for k in ar_kws}
                for keyword, score in ar_scores.items():
                    if score and keyword in ar_map and ar_map[keyword].volume is None:
                        ar_map[keyword].volume = score
        except Exception:
            pass  # Trends failed — difficulty estimates still saved

    await db.flush()
    return {"updated": updated, "total": len(kws), "source": source}


@router.get("/{site_id}")
async def get_keywords(
    site_id: int,
    intent: Optional[str] = None,
    cluster: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = 2000,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Keyword).where(Keyword.site_id == site_id)
    if intent:
        stmt = stmt.where(Keyword.intent == intent)
    if cluster:
        stmt = stmt.where(Keyword.cluster == cluster)
    if language:
        stmt = stmt.where(Keyword.language == language)
    stmt = stmt.order_by(Keyword.volume.desc().nullslast(), Keyword.id).limit(limit)
    result = await db.execute(stmt)
    return [_kw_dict(k) for k in result.scalars().all()]


@router.delete("/{site_id}")
async def delete_keywords(site_id: int, db: AsyncSession = Depends(get_db)):
    """Delete all keywords for this site to allow a fresh research run."""
    result = await db.execute(sql_delete(Keyword).where(Keyword.site_id == site_id))
    await db.flush()
    return {"deleted": result.rowcount}
