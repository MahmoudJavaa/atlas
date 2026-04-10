import asyncio
from backend.celery_app import celery_app
from backend.database import AsyncSessionLocal
from backend.models.audit import AuditLog


@celery_app.task(name="backend.tasks.analytics_tasks.pull_gsc_data", bind=True, max_retries=3)
def pull_gsc_data(self, site_id: int, days: int = 28):
    """Pull Google Search Console data for a site."""
    try:
        result = asyncio.run(_pull_gsc_data_async(site_id, days))
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


async def _pull_gsc_data_async(site_id: int, days: int):
    async with AsyncSessionLocal() as db:
        from backend.modules.analytics.connector import AnalyticsConnector
        connector = AnalyticsConnector(db=db)
        result = await connector.pull_gsc(site_id=site_id, days=days)
        log = AuditLog(
            site_id=site_id,
            module="analytics",
            action="pull_gsc_data",
            payload={"days": days},
        )
        db.add(log)
        await db.commit()
        return result
