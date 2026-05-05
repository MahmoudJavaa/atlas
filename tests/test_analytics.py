"""Tests for AnalyticsConnector — no live API needed."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_forecast_revenue():
    from backend.modules.analytics.connector import AnalyticsConnector

    db = AsyncMock()
    connector = AnalyticsConnector(db=db)

    result = await connector.forecast_revenue(
        current_clicks=1000,
        target_clicks=2000,
        conversion_rate=0.02,
        avg_order_value=100.0,
    )

    assert result["current_estimated_revenue"] == 2000.0  # 1000 * 0.02 * 100
    assert result["target_estimated_revenue"] == 4000.0   # 2000 * 0.02 * 100
    assert result["revenue_uplift"] == 2000.0
    assert result["assumptions"]["conversion_rate"] == 0.02


@pytest.mark.asyncio
async def test_forecast_zero_clicks():
    from backend.modules.analytics.connector import AnalyticsConnector

    db = AsyncMock()
    connector = AnalyticsConnector(db=db)

    result = await connector.forecast_revenue(
        current_clicks=0, target_clicks=500,
        conversion_rate=0.03, avg_order_value=50.0,
    )

    assert result["current_estimated_revenue"] == 0.0
    assert result["target_estimated_revenue"] == 750.0
    assert result["revenue_uplift"] == 750.0


def test_segment_brand():
    from backend.modules.analytics.connector import AnalyticsConnector

    connector = AnalyticsConnector(db=MagicMock())
    rows = [
        {"keys": ["fastlock locksmith london"], "clicks": 50, "impressions": 500},
        {"keys": ["locksmith near me"], "clicks": 100, "impressions": 1000},
        {"keys": ["fastlock reviews"], "clicks": 30, "impressions": 200},
        {"keys": ["emergency locksmith"], "clicks": 80, "impressions": 900},
    ]

    brand, non_brand = connector._segment_brand(rows, "FastLock")

    assert brand["clicks"] == 80        # 50 + 30
    assert non_brand["clicks"] == 180   # 100 + 80
    assert brand["impressions"] == 700  # 500 + 200


@pytest.mark.asyncio
async def test_pull_gsc_no_credentials():
    from backend.modules.analytics.connector import AnalyticsConnector

    db = AsyncMock()
    connector = AnalyticsConnector(db=db)

    result = await connector.pull_gsc(site_id=1, days=28)
    assert "error" in result
    assert "not configured" in result["error"].lower() or "OAuth" in result["error"]
