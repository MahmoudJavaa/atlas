import asyncio
from backend.celery_app import celery_app
from backend.database import AsyncSessionLocal
from backend.models.audit import AuditLog


@celery_app.task(name="backend.tasks.keyword_tasks.classify_keywords", bind=True, max_retries=3)
def classify_keywords(self, site_id: int, seed_keywords: list[str]):
    """Classify keyword intent and build topic clusters."""
    try:
        result = asyncio.run(_classify_keywords_async(site_id, seed_keywords))
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


async def _classify_keywords_async(site_id: int, seed_keywords: list[str]):
    async with AsyncSessionLocal() as db:
        from backend.modules.keyword_intel.classifier import KeywordClassifier
        classifier = KeywordClassifier(db=db)
        results = await classifier.run(site_id=site_id, seed_keywords=seed_keywords)

        log = AuditLog(
            site_id=site_id,
            module="keyword_intel",
            action="classify_keywords",
            payload={"seed_count": len(seed_keywords), "classified_count": len(results.get("keywords", []))},
        )
        db.add(log)
        await db.commit()
        return results
