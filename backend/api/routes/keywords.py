"""Keyword Intelligence API routes."""
from __future__ import annotations

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
    language: str = "both"  # "en" | "ar" | "both"
    location_code: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# Image/file noise patterns — seeds matching these are useless for keyword research
_IMG_NOISE = re.compile(
    r"(?:webp|jpeg|jpg|png|gif|svg|avif|scaled|crop|thumb|resize|banner|hero|icon|logo)"
    r"|\b\d{3,4}x\d{3,4}\b"   # dimensions like 1920x1080
    r"|\b(?:1080|1440|1600|1920|2048|2560|3840|720|480|360)\b",  # common px values
    re.IGNORECASE,
)

def _is_clean_seed(phrase: str) -> bool:
    """Return True only if the phrase looks like a real keyword topic (not an image filename)."""
    if _IMG_NOISE.search(phrase):
        return False
    # Must have at least one alphabetic word of length >= 3
    words = phrase.split()
    alpha_words = [w for w in words if re.match(r"[a-zA-Z؀-ۿ]{3,}", w)]
    return len(alpha_words) >= 1


def _extract_seeds_from_site(site_name: str, site_url: str) -> list[str]:
    """Derive keyword seeds from the site name and domain when crawl data is poor."""
    seeds: list[str] = []
    # From domain: strip TLD, split on hyphens/dots
    domain = re.sub(r"https?://(?:www\.)?", "", site_url).split("/")[0]
    domain_parts = re.split(r"[-.]", domain)
    for part in domain_parts:
        if len(part) >= 4 and part not in ("com", "net", "org", "app", "www"):
            seeds.append(part)

    # From site name: split camelCase and spaces
    name_parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", site_name)  # camelCase → words
    for word in name_parts.split():
        word = word.lower().strip()
        if len(word) >= 4:
            seeds.append(word)

    # Build common multi-word combos from the site name words
    words = [s for s in seeds if len(s) >= 4][:5]
    for i in range(len(words)):
        for j in range(i + 1, min(i + 3, len(words))):
            seeds.append(" ".join(words[i:j + 1]))

    return list(dict.fromkeys(seeds))[:20]  # deduplicate preserving order


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
            enriched.append({"keyword": kw, "volume": v.get("volume"), "difficulty": v.get("difficulty"), "language": "en"})

    if ar_kws:
        vol_map = await get_search_volume(ar_kws, language_code="ar")
        for kw in ar_kws:
            v = vol_map.get(kw.lower(), {})
            enriched.append({"keyword": kw, "volume": v.get("volume"), "difficulty": v.get("difficulty"), "language": "ar"})

    if not enriched:
        enriched = [{"keyword": k, "volume": None, "difficulty": None, "language": "en"} for k in data.seed_keywords]

    classifier = KeywordClassifier(db=db)
    return await classifier.run(site_id=data.site_id, seed_keywords=enriched)


@router.post("/auto-research/{site_id}")
async def auto_research(
    site_id: int,
    req: ResearchRequest = ResearchRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Auto-research keywords using DataForSEO for real volume + difficulty.

    Language options:
      "en"   — English keywords only
      "ar"   — Arabic keywords only
      "both" — English + Arabic (default)

    Falls back to template-based generation when DataForSEO returns nothing.
    """
    from backend.models.crawl import CrawlResult
    from backend.models.site import Site
    from backend.modules.keyword_intel.classifier import KeywordClassifier
    from backend.modules.keyword_intel.dataforseo import get_keyword_ideas, _is_configured

    # ── Fetch site ────────────────────────────────────────────────────────────
    site_result = await db.execute(select(Site).where(Site.id == site_id))
    site = site_result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # ── Fetch crawl data for seed extraction ──────────────────────────────────
    crawl_result = await db.execute(
        select(CrawlResult).where(CrawlResult.site_id == site_id).limit(200)
    )
    pages = crawl_result.scalars().all()
    if not pages:
        raise HTTPException(
            status_code=422,
            detail="No crawl data found. Run a site crawl first (Technical SEO tab).",
        )

    # ── Stop word lists ───────────────────────────────────────────────────────
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

    # ── Extract seed topics from page titles + meta ───────────────────────────
    def _clean(text: str) -> str:
        text = re.sub(r"\s*[-|•·|]\s*.{0,40}$", "", text)      # strip brand suffix
        text = re.sub(r"[^\w\s؀-ۿ]", " ", text)
        return text.strip().lower()

    def _phrases(text: str, stop: set) -> list[str]:
        words = [w for w in text.split() if len(w) > 3 and w not in stop]
        out: list[str] = []
        for i, w in enumerate(words):
            out.append(w)
            if i + 1 < len(words):
                out.append(f"{words[i]} {words[i+1]}")
            if i + 2 < len(words):
                out.append(f"{words[i]} {words[i+1]} {words[i+2]}")
        return out

    en_topics: set[str] = set()
    ar_topics: set[str] = set()
    for page in pages:
        for text in [page.title or "", (page.meta_desc or "")[:200]]:
            cleaned = _clean(text)
            if re.search(r"[؀-ۿ]", cleaned):
                ar_topics.update(_phrases(cleaned, AR_STOP))
            else:
                en_topics.update(_phrases(cleaned, EN_STOP))

    # Filter out image noise (file names, pixel dimensions, format names)
    en_seeds = [t for t in en_topics if len(t) >= 4 and _is_clean_seed(t)][:40]
    ar_seeds = [t for t in ar_topics if len(t) >= 3 and _is_clean_seed(t)][:40]

    # ── Fallback: derive seeds from site name + domain ────────────────────────
    # (needed when all crawl content is images with no real text)
    if len(en_seeds) < 5:
        site_url = getattr(site, "url", "") or ""
        site_name = getattr(site, "name", "") or ""
        fallback_seeds = _extract_seeds_from_site(site_name, site_url)
        en_seeds = list(dict.fromkeys(en_seeds + fallback_seeds))[:40]

    # ── Language flags ────────────────────────────────────────────────────────
    do_en = req.language in ("en", "both")
    do_ar = req.language in ("ar", "both")

    use_dataforseo = _is_configured()
    new_keywords: list[dict] = []

    # ── Template modifier lists (used as fallback) ────────────────────────────
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

    def _run_template_fallback(seeds_en: list[str], seeds_ar: list[str]) -> list[dict]:
        result: list[dict] = []
        if do_en and seeds_en:
            kws_raw: list[str] = list(seeds_en)
            for t in seeds_en[:30]:
                for mod in EN_MODS:
                    kws_raw.append(mod.format(t=t))
            seen_t: set[str] = set()
            for k in kws_raw:
                k = k.strip()
                if k and k not in seen_t and len(k) >= 4:
                    seen_t.add(k)
                    result.append({"keyword": k, "volume": None, "difficulty": None, "language": "en"})
            result = result[:700]

        if do_ar and seeds_ar:
            kws_ar: list[str] = list(seeds_ar)
            for t in seeds_ar[:20]:
                for mod in AR_MODS:
                    kws_ar.append(mod.format(t=t))
            seen_ar: set[str] = set()
            for k in kws_ar:
                k = k.strip()
                if k and k not in seen_ar and len(k) >= 3:
                    seen_ar.add(k)
                    result.append({"keyword": k, "volume": None, "difficulty": None, "language": "ar"})
        return result

    if use_dataforseo:
        # ── Real keyword data from DataForSEO ─────────────────────────────────
        if do_en and en_seeds:
            en_ideas = await get_keyword_ideas(
                en_seeds,
                language_code="en",
                location_code=req.location_code,
                limit=700,
            )
            new_keywords.extend(en_ideas[:700])

        if do_ar:
            seeds_for_ar = ar_seeds if ar_seeds else en_seeds[:20]
            ar_ideas = await get_keyword_ideas(
                seeds_for_ar,
                language_code="ar",
                location_code=req.location_code,
                limit=400,
            )
            new_keywords.extend(ar_ideas[:400])

        # If DataForSEO returned nothing (bad seeds / API issue), fall back to templates
        if not new_keywords:
            new_keywords = _run_template_fallback(en_seeds, ar_seeds)
            use_dataforseo = False  # tell frontend we used fallback

    else:
        # ── No DataForSEO: template-based generation ──────────────────────────
        new_keywords = _run_template_fallback(en_seeds, ar_seeds)

    if not new_keywords:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Could not generate keywords. Seeds found: {len(en_seeds)} EN, "
                f"{len(ar_seeds)} AR. Check that the site crawl has real page content."
            ),
        )

    # ── Remove keywords already in DB ─────────────────────────────────────────
    existing_result = await db.execute(
        select(Keyword.keyword).where(Keyword.site_id == site_id)
    )
    existing_set: set[str] = {row[0].lower() for row in existing_result.all()}
    fresh = [kw for kw in new_keywords if kw["keyword"].lower() not in existing_set]

    # ── Classify intent + save in batches ─────────────────────────────────────
    classifier = KeywordClassifier(db=db)
    BATCH = 60
    total_added = 0

    for i in range(0, len(fresh), BATCH):
        batch = fresh[i : i + BATCH]
        try:
            await classifier.run(site_id=site_id, seed_keywords=batch)
            total_added += len(batch)
        except Exception:
            pass

    # ── Return all keywords for this site ─────────────────────────────────────
    all_kws_result = await db.execute(
        select(Keyword).where(Keyword.site_id == site_id).order_by(
            Keyword.volume.desc().nullslast(), Keyword.id
        ).limit(2000)
    )
    all_kws = all_kws_result.scalars().all()

    return {
        "new_keywords_added": total_added,
        "total": len(all_kws),
        "used_dataforseo": use_dataforseo,
        "keywords": [_kw_dict(k) for k in all_kws],
    }


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
    """Delete all keywords for a site so research can be re-run from scratch."""
    result = await db.execute(
        sql_delete(Keyword).where(Keyword.site_id == site_id)
    )
    await db.flush()
    return {"deleted": result.rowcount}
