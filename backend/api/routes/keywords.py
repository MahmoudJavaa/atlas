import re
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database import get_db
from backend.models.keyword import Keyword

router = APIRouter(prefix="/keywords", tags=["keywords"])


class ClassifyRequest(BaseModel):
    site_id: int
    seed_keywords: list[str]


@router.post("/classify")
async def classify_keywords(data: ClassifyRequest):
    """Queue keyword classification task."""
    from backend.tasks.keyword_tasks import classify_keywords as task
    t = task.delay(data.site_id, data.seed_keywords)
    return {"task_id": t.id, "status": "queued"}


@router.post("/classify/sync")
async def classify_sync(data: ClassifyRequest, db: AsyncSession = Depends(get_db)):
    """Classify keywords synchronously."""
    from backend.modules.keyword_intel.classifier import KeywordClassifier
    classifier = KeywordClassifier(db=db)
    result = await classifier.run(site_id=data.site_id, seed_keywords=data.seed_keywords)
    return result


@router.post("/auto-research/{site_id}")
async def auto_research(site_id: int, db: AsyncSession = Depends(get_db)):
    """
    Auto-generate 1000+ keywords from the site's crawl data.
    Extracts topics from page titles/meta, expands with modifier templates,
    classifies intent, deduplicates, and saves to DB.
    """
    from backend.models.crawl import CrawlResult
    from backend.models.site import Site
    from backend.modules.keyword_intel.classifier import KeywordClassifier

    # Get site info
    site_result = await db.execute(select(Site).where(Site.id == site_id))
    site = site_result.scalar_one_or_none()
    if not site:
        return {"error": "Site not found", "keywords": [], "total": 0}

    # Get crawl results for topic extraction
    crawl_result = await db.execute(
        select(CrawlResult).where(CrawlResult.site_id == site_id).limit(200)
    )
    pages = crawl_result.scalars().all()

    if not pages:
        return {
            "error": "No crawl data found. Run a site crawl first.",
            "keywords": [],
            "total": 0,
        }

    # ── Step 1: Extract base topics from page titles + meta ──────────────────
    topics: set[str] = set()

    def clean_text(text: str) -> str:
        """Strip brand suffix, punctuation, lowercase."""
        text = re.sub(r"\s*[-|•·|]\s*.{0,40}$", "", text)  # remove "Brand Name" suffix
        text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
        return text.strip().lower()

    def extract_phrases(text: str) -> list[str]:
        words = text.split()
        words = [w for w in words if len(w) > 3 and w not in STOP_WORDS]
        phrases = []
        for i, w in enumerate(words):
            phrases.append(w)
            if i + 1 < len(words):
                phrases.append(f"{words[i]} {words[i+1]}")
            if i + 2 < len(words):
                phrases.append(f"{words[i]} {words[i+1]} {words[i+2]}")
        return phrases

    for page in pages:
        if page.title:
            topics.update(extract_phrases(clean_text(page.title)))
        if page.meta_desc:
            topics.update(extract_phrases(clean_text(page.meta_desc[:200])))

    # Limit base topics to meaningful ones (3+ chars)
    base_topics = [t for t in topics if len(t) >= 4][:60]

    if not base_topics:
        return {"error": "Could not extract topics from crawl data.", "keywords": [], "total": 0}

    # ── Step 2: Expand with modifier templates ───────────────────────────────
    MODIFIERS = [
        # Informational
        "what is {t}",
        "how to {t}",
        "{t} guide",
        "{t} tips",
        "{t} tutorial",
        "{t} explained",
        "{t} for beginners",
        "{t} examples",
        "best {t} practices",
        # Commercial
        "best {t}",
        "top {t}",
        "affordable {t}",
        "cheap {t}",
        "premium {t}",
        "professional {t}",
        "expert {t}",
        "trusted {t}",
        "local {t}",
        # Transactional
        "buy {t}",
        "get {t}",
        "{t} for sale",
        "{t} price",
        "{t} cost",
        "{t} quote",
        "order {t}",
        "{t} near me",
        "{t} online",
        "{t} service",
        "{t} company",
        "{t} provider",
        # Questions / long-tail
        "how much does {t} cost",
        "where to get {t}",
        "is {t} worth it",
        "how long does {t} take",
        "what does {t} include",
        "{t} vs",
        "why {t}",
        "when to {t}",
        # Reviews / comparison
        "{t} review",
        "{t} reviews",
        "best {t} 2024",
        "best {t} 2025",
        "{t} comparison",
        "{t} alternatives",
        # Local / service
        "{t} specialist",
        "find {t}",
        "{t} help",
        "{t} support",
        "{t} benefits",
        "{t} problems",
        "{t} solutions",
    ]

    seed_keywords: list[str] = list(base_topics)  # include bare topics too
    for topic in base_topics[:40]:
        for mod in MODIFIERS:
            seed_keywords.append(mod.format(t=topic))

    # Deduplicate preserving order
    seen: set[str] = set()
    unique_seeds: list[str] = []
    for kw in seed_keywords:
        kw = kw.strip()
        if kw and kw not in seen and len(kw) >= 4:
            seen.add(kw)
            unique_seeds.append(kw)

    unique_seeds = unique_seeds[:1200]  # cap at 1200

    # ── Step 3: Remove keywords that already exist in DB ────────────────────
    existing_result = await db.execute(
        select(Keyword.keyword).where(Keyword.site_id == site_id)
    )
    existing_kws: set[str] = {row[0].lower() for row in existing_result.all()}
    new_seeds = [kw for kw in unique_seeds if kw.lower() not in existing_kws]

    # ── Step 4: Classify + save in batches ───────────────────────────────────
    classifier = KeywordClassifier(db=db)
    BATCH = 60
    total_classified = 0

    for i in range(0, len(new_seeds), BATCH):
        batch = new_seeds[i : i + BATCH]
        try:
            await classifier.run(site_id=site_id, seed_keywords=batch)
            total_classified += len(batch)
        except Exception:
            pass  # don't fail entire research if one batch errors

    # ── Step 5: Return everything saved for this site ────────────────────────
    all_kws_result = await db.execute(
        select(Keyword).where(Keyword.site_id == site_id).limit(1500)
    )
    all_kws = all_kws_result.scalars().all()

    return {
        "new_keywords_added": total_classified,
        "total": len(all_kws),
        "keywords": [
            {
                "id": k.id,
                "keyword": k.keyword,
                "intent": k.intent,
                "cluster": k.cluster,
                "volume": k.volume,
                "position": k.position,
                "clicks": k.clicks,
                "impressions": k.impressions,
            }
            for k in all_kws
        ],
    }


@router.get("/{site_id}")
async def get_keywords(
    site_id: int,
    intent: str = None,
    cluster: str = None,
    limit: int = 1500,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Keyword).where(Keyword.site_id == site_id)
    if intent:
        stmt = stmt.where(Keyword.intent == intent)
    if cluster:
        stmt = stmt.where(Keyword.cluster == cluster)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    keywords = result.scalars().all()
    return [
        {
            "id": k.id,
            "keyword": k.keyword,
            "intent": k.intent,
            "cluster": k.cluster,
            "volume": k.volume,
            "position": k.position,
            "clicks": k.clicks,
            "impressions": k.impressions,
        }
        for k in keywords
    ]


# ── Common English stop words (to avoid useless topic phrases) ───────────────
STOP_WORDS = {
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
    "same", "life", "next", "last",
}
