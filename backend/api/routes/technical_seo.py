import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from pydantic import BaseModel
from typing import Optional
from collections import defaultdict


def _normalize_issue(msg: str) -> str:
    """Collapse dynamic numbers so 'Title too long (72 chars)' groups with '(65 chars)'."""
    msg = re.sub(r"\(\d+ chars?\)", "", msg)          # "(72 chars)"
    msg = re.sub(r"\(\d+\)", "", msg)                  # "(2)" in "Multiple H1 tags (2)"
    msg = re.sub(r"\d+ image\(s\)", "images", msg)    # "9 image(s)" → "images"
    msg = re.sub(r"\d+ words?\b", "N words", msg)     # "245 words" → "N words"
    msg = re.sub(r"\d+ms\b", "Nms", msg)              # "3200ms" → "Nms"
    return msg.strip().rstrip(".")

from backend.database import get_db
from backend.models.crawl import CrawlResult
from backend.auth import get_current_user

router = APIRouter(
    prefix="/technical-seo",
    tags=["technical-seo"],
    dependencies=[Depends(get_current_user)],
)


class CrawlRequest(BaseModel):
    site_id: int
    start_url: str
    max_pages: int = 100


@router.post("/crawl/sync")
async def crawl_sync(data: CrawlRequest, db: AsyncSession = Depends(get_db)):
    """Run crawl synchronously. Deletes old results and replaces with fresh data."""
    from backend.modules.technical_seo.crawler import TechnicalSEOCrawler
    crawler = TechnicalSEOCrawler(db=db)
    results = await crawler.run(
        site_id=data.site_id,
        start_url=data.start_url,
        max_pages=data.max_pages,
    )
    return {"pages_crawled": len(results), "results": results}


@router.get("/results/{site_id}")
async def get_crawl_results(
    site_id: int,
    severity: Optional[str] = None,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db),
):
    """Get crawl results for a site, sorted by severity score descending."""
    stmt = (
        select(CrawlResult)
        .where(CrawlResult.site_id == site_id)
        .order_by(CrawlResult.severity_score.desc(), CrawlResult.url)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()

    if severity:
        rows = [r for r in rows if r.issues.get(severity)]

    return [
        {
            "id": r.id,
            "url": r.url,
            "status_code": r.status_code,
            "title": r.title,
            "meta_desc": r.meta_desc,
            "canonical": r.canonical,
            "redirect_url": r.redirect_url,
            "indexable": r.indexable,
            "word_count": r.word_count,
            "h1_count": r.h1_count,
            "response_time_ms": r.response_time_ms,
            "page_depth": r.page_depth,
            "severity_score": r.severity_score,
            "issues": r.issues,
            "crawled_at": r.crawled_at,
        }
        for r in rows
    ]


@router.get("/results/{site_id}/summary")
async def get_audit_summary(site_id: int, db: AsyncSession = Depends(get_db)):
    """Summary stats + per-issue-type breakdown (how many pages affected)."""

    # Totals
    agg = (await db.execute(
        select(
            func.count(CrawlResult.id).label("total_pages"),
            func.avg(CrawlResult.severity_score).label("avg_severity"),
            func.max(CrawlResult.crawled_at).label("last_crawled"),
        ).where(CrawlResult.site_id == site_id)
    )).one()

    # All issue dicts
    pages = (await db.execute(
        select(CrawlResult.issues).where(CrawlResult.site_id == site_id)
    )).scalars().all()

    critical_count = warning_count = info_count = clean_count = 0
    issue_frequency: dict[str, int] = defaultdict(int)

    for issues in pages:
        if not isinstance(issues, dict):
            continue
        has_issue = False
        for severity in ("critical", "warning", "info"):
            for msg in issues.get(severity, []):
                if not msg.startswith("_"):
                    normalized = _normalize_issue(msg)
                    issue_frequency[normalized] += 1
                    has_issue = True
        if issues.get("critical"):
            critical_count += 1
        if issues.get("warning"):
            warning_count += 1
        if issues.get("info"):
            info_count += 1
        if not has_issue:
            clean_count += 1

    # Top issues sorted by frequency
    top_issues = sorted(
        [{"issue": k, "pages_affected": v} for k, v in issue_frequency.items()],
        key=lambda x: x["pages_affected"],
        reverse=True,
    )

    return {
        "total_pages": int(agg.total_pages or 0),
        "avg_severity_score": round(float(agg.avg_severity or 0), 1),
        "last_crawled": agg.last_crawled.isoformat() if agg.last_crawled else None,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "clean_count": clean_count,
        "top_issues": top_issues[:50],
    }
