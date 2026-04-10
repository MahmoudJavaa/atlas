import asyncio
from backend.celery_app import celery_app
from backend.database import AsyncSessionLocal
from backend.models.audit import AuditLog


@celery_app.task(name="backend.tasks.content_tasks.generate_content", bind=True, max_retries=3)
def generate_content(self, site_id: int, keyword: str, intent: str, funnel_stage: str,
                     page_type: str, location: str = None):
    """Generate SEO content via Claude."""
    try:
        result = asyncio.run(_generate_content_async(site_id, keyword, intent, funnel_stage, page_type, location))
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


async def _generate_content_async(site_id, keyword, intent, funnel_stage, page_type, location):
    async with AsyncSessionLocal() as db:
        from backend.modules.content_engine.generator import ContentGenerator
        generator = ContentGenerator(db=db)
        result = await generator.run(
            site_id=site_id,
            keyword=keyword,
            intent=intent,
            funnel_stage=funnel_stage,
            page_type=page_type,
            location=location,
        )
        log = AuditLog(
            site_id=site_id,
            module="content_engine",
            action="generate_content",
            payload={"keyword": keyword, "page_type": page_type},
        )
        db.add(log)
        await db.commit()
        return result


@celery_app.task(name="backend.tasks.content_tasks.publish_content", bind=True, max_retries=3)
def publish_content(self, site_id: int, content_page_id: int, dry_run: bool = True):
    """Publish a content page to the CMS."""
    try:
        result = asyncio.run(_publish_content_async(site_id, content_page_id, dry_run))
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


async def _publish_content_async(site_id, content_page_id, dry_run):
    async with AsyncSessionLocal() as db:
        from backend.modules.execution.publisher import CMSPublisher
        publisher = CMSPublisher(db=db)
        result = await publisher.publish_page(content_page_id=content_page_id, dry_run=dry_run)
        log = AuditLog(
            site_id=site_id,
            module="execution",
            action="publish_content",
            payload={"content_page_id": content_page_id, "dry_run": dry_run},
        )
        db.add(log)
        await db.commit()
        return result
