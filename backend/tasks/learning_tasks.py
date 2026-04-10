import asyncio
from backend.celery_app import celery_app
from backend.database import AsyncSessionLocal
from backend.models.audit import AuditLog
from sqlalchemy import select
from backend.models.site import Site


@celery_app.task(name="backend.tasks.learning_tasks.run_learning_loop", bind=True, max_retries=2)
def run_learning_loop(self, site_id: int):
    """Run the learning loop for a single site."""
    try:
        result = asyncio.run(_run_learning_loop_async(site_id))
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="backend.tasks.learning_tasks.run_learning_loop_all_sites")
def run_learning_loop_all_sites():
    """Beat task: run learning loop across all sites."""
    result = asyncio.run(_run_all_sites_async())
    return result


async def _run_learning_loop_async(site_id: int):
    async with AsyncSessionLocal() as db:
        from backend.modules.learning_loop.optimizer import LearningLoopOptimizer
        optimizer = LearningLoopOptimizer(db=db)
        report = await optimizer.run(site_id=site_id)
        log = AuditLog(
            site_id=site_id,
            module="learning_loop",
            action="run_learning_loop",
            payload={"experiments_evaluated": report.get("experiments_evaluated", 0)},
        )
        db.add(log)
        await db.commit()
        return report


async def _run_all_sites_async():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Site))
        sites = result.scalars().all()
    for site in sites:
        run_learning_loop.delay(site.id)
    return {"sites_triggered": len(sites)}
