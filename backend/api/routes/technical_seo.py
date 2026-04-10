from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.models.crawl import CrawlResult

router = APIRouter(prefix="/technical-seo", tags=["technical-seo"])


class CrawlRequest(BaseModel):
    site_id: int
    start_url: str
    max_pages: int = 100


@router.post("/crawl")
async def trigger_crawl(data: CrawlRequest, background_tasks: BackgroundTasks):
    """Trigger an async crawl via Celery."""
    from backend.tasks.crawl_tasks import crawl_site
    task = crawl_site.delay(data.site_id, data.start_url, data.max_pages)
    return {"task_id": task.id, "status": "queued"}


@router.post("/crawl/sync")
async def crawl_sync(data: CrawlRequest, db: AsyncSession = Depends(get_db)):
    """Run crawl synchronously (for small sites / testing)."""
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
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get crawl results, optionally filtered by severity."""
    stmt = select(CrawlResult).where(CrawlResult.site_id == site_id).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if severity:
        rows = [r for r in rows if r.issues.get(severity)]

    return [
        {
            "id": r.id,
            "url": r.url,
            "status_code": r.status_code,
            "title": r.title,
            "meta_desc": r.meta_desc,
            "indexable": r.indexable,
            "word_count": r.word_count,
            "severity_score": r.severity_score,
            "issues": r.issues,
            "crawled_at": r.crawled_at,
        }
        for r in rows
    ]


@router.get("/results/{site_id}/summary")
async def get_audit_summary(site_id: int, db: AsyncSession = Depends(get_db)):
    """Get issue summary counts for a site."""
    from sqlalchemy import func
    result = await db.execute(
        select(
            func.count(CrawlResult.id).label("total_pages"),
            func.avg(CrawlResult.severity_score).label("avg_severity"),
        ).where(CrawlResult.site_id == site_id)
    )
    row = result.one()
    return {
        "total_pages": int(row.total_pages or 0),
        "avg_severity_score": round(float(row.avg_severity or 0), 1),
    }
