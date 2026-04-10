from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


class ForecastRequest(BaseModel):
    current_clicks: int
    target_clicks: int
    conversion_rate: float = 0.02
    avg_order_value: float = 100.0


@router.get("/performance/{site_id}")
async def get_performance(site_id: int, days: int = 28, db: AsyncSession = Depends(get_db)):
    from backend.modules.analytics.connector import AnalyticsConnector
    connector = AnalyticsConnector(db=db)
    return await connector.get_performance_summary(site_id=site_id, days=days)


@router.post("/forecast")
async def revenue_forecast(data: ForecastRequest, db: AsyncSession = Depends(get_db)):
    from backend.modules.analytics.connector import AnalyticsConnector
    connector = AnalyticsConnector(db=db)
    return await connector.forecast_revenue(
        current_clicks=data.current_clicks,
        target_clicks=data.target_clicks,
        conversion_rate=data.conversion_rate,
        avg_order_value=data.avg_order_value,
    )


@router.post("/pull-gsc/{site_id}")
async def pull_gsc(site_id: int, days: int = 28):
    from backend.tasks.analytics_tasks import pull_gsc_data
    task = pull_gsc_data.delay(site_id, days)
    return {"task_id": task.id, "status": "queued"}


@router.get("/oauth/callback")
async def gsc_oauth_callback(code: str = None, error: str = None):
    if error:
        return {"error": error}
    # In production: exchange code for tokens and store in DB
    return {"message": "OAuth callback received", "code": code[:10] + "..." if code else None}
