"""Analytics Connector — GSC + GA4 data ingestion."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.keyword import Keyword


class AnalyticsConnector:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def pull_gsc(self, site_id: int, days: int = 28) -> dict:
        """Pull GSC data and persist keywords/positions."""
        service = self._get_gsc_service()
        if not service:
            return {"error": "GSC not configured. Provide OAuth credentials."}

        from backend.models.site import Site
        from sqlalchemy import select
        result = await self.db.execute(select(Site).where(Site.id == site_id))
        site = result.scalar_one_or_none()
        if not site:
            return {"error": "Site not found"}

        end_date = datetime.now(tz=None).date()
        start_date = end_date - timedelta(days=days)

        try:
            response = service.searchanalytics().query(
                siteUrl=site.url,
                body={
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                    "dimensions": ["query", "page"],
                    "rowLimit": 25000,
                },
            ).execute()
        except Exception as e:
            return {"error": str(e)}

        rows = response.get("rows", [])
        keyword_records = []

        for row in rows:
            keys = row.get("keys", [])
            kw = Keyword(
                site_id=site_id,
                keyword=keys[0] if len(keys) > 0 else "",
                url=keys[1] if len(keys) > 1 else None,
                clicks=int(row.get("clicks", 0)),
                impressions=int(row.get("impressions", 0)),
                ctr=float(row.get("ctr", 0.0)),
                position=float(row.get("position", 0.0)),
                date=end_date,
            )
            self.db.add(kw)
            keyword_records.append(kw)

        await self.db.flush()

        # Segment brand vs non-brand
        brand_summary, non_brand_summary = self._segment_brand(rows, site.name)

        return {
            "rows_imported": len(rows),
            "brand_clicks": brand_summary["clicks"],
            "non_brand_clicks": non_brand_summary["clicks"],
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        }

    def _get_gsc_service(self):
        if not settings.google_client_id or not settings.google_client_secret:
            return None
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            # In production, load stored OAuth tokens from DB/Redis
            # For now return None if no tokens stored
            return None
        except ImportError:
            return None

    def _segment_brand(self, rows: list[dict], brand_name: str) -> tuple[dict, dict]:
        brand_terms = brand_name.lower().split()
        brand = {"clicks": 0, "impressions": 0}
        non_brand = {"clicks": 0, "impressions": 0}

        for row in rows:
            query = row.get("keys", [""])[0].lower()
            is_brand = any(term in query for term in brand_terms)
            target = brand if is_brand else non_brand
            target["clicks"] += int(row.get("clicks", 0))
            target["impressions"] += int(row.get("impressions", 0))

        return brand, non_brand

    async def forecast_revenue(
        self,
        current_clicks: int,
        target_clicks: int,
        conversion_rate: float = 0.02,
        avg_order_value: float = 100.0,
    ) -> dict:
        """Simple revenue impact forecast."""
        current_revenue = current_clicks * conversion_rate * avg_order_value
        target_revenue = target_clicks * conversion_rate * avg_order_value
        uplift = target_revenue - current_revenue
        return {
            "current_clicks": current_clicks,
            "target_clicks": target_clicks,
            "current_estimated_revenue": round(current_revenue, 2),
            "target_estimated_revenue": round(target_revenue, 2),
            "revenue_uplift": round(uplift, 2),
            "assumptions": {
                "conversion_rate": conversion_rate,
                "avg_order_value": avg_order_value,
            },
        }

    async def get_performance_summary(self, site_id: int, days: int = 28) -> dict:
        """Get aggregated performance from stored keywords."""
        from sqlalchemy import select, func
        from backend.models.keyword import Keyword
        from datetime import date

        cutoff = datetime.now(tz=None).date() - timedelta(days=days)
        result = await self.db.execute(
            select(
                func.sum(Keyword.clicks).label("total_clicks"),
                func.sum(Keyword.impressions).label("total_impressions"),
                func.avg(Keyword.position).label("avg_position"),
                func.count(Keyword.id).label("keyword_count"),
            ).where(Keyword.site_id == site_id, Keyword.date >= cutoff)
        )
        row = result.one()
        return {
            "total_clicks": int(row.total_clicks or 0),
            "total_impressions": int(row.total_impressions or 0),
            "avg_position": round(float(row.avg_position or 0), 1),
            "keyword_count": int(row.keyword_count or 0),
        }
