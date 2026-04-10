import asyncio
from backend.celery_app import celery_app
from backend.database import AsyncSessionLocal
from backend.models.audit import AuditLog


@celery_app.task(name="backend.tasks.crawl_tasks.crawl_site", bind=True, max_retries=3)
def crawl_site(self, site_id: int, start_url: str, max_pages: int = 100):
    """Crawl a site and store audit results."""
    try:
        from backend.modules.technical_seo.crawler import TechnicalSEOCrawler
        result = asyncio.run(_crawl_site_async(site_id, start_url, max_pages))
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


async def _crawl_site_async(site_id: int, start_url: str, max_pages: int):
    async with AsyncSessionLocal() as db:
        from backend.modules.technical_seo.crawler import TechnicalSEOCrawler
        crawler = TechnicalSEOCrawler(db=db)
        results = await crawler.run(site_id=site_id, start_url=start_url, max_pages=max_pages)

        log = AuditLog(
            site_id=site_id,
            module="technical_seo",
            action="crawl_site",
            payload={"start_url": start_url, "pages_crawled": len(results)},
        )
        db.add(log)
        await db.commit()
        return {"pages_crawled": len(results), "results": results}
