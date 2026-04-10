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


@router.get("/{site_id}")
async def get_keywords(site_id: int, intent: str = None, limit: int = 200, db: AsyncSession = Depends(get_db)):
    stmt = select(Keyword).where(Keyword.site_id == site_id)
    if intent:
        stmt = stmt.where(Keyword.intent == intent)
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
