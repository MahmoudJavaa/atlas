"""Tests for CompetitorAnalyzer — mocked SerpAPI + LLM."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock


MOCK_GAP_ANALYSIS = {
    "ranking_factors": ["Strong heading structure", "High entity density", "Comprehensive FAQ sections"],
    "content_gaps": [
        {"topic": "car locksmith", "suggested_url_slug": "/car-locksmith", "estimated_volume": "high"},
        {"topic": "safe cracking", "suggested_url_slug": "/safe-cracking-service", "estimated_volume": "low"},
    ],
    "structural_insights": ["Competitors use H2 for each service type"],
    "entity_density_notes": "Competitors mention brand names like Yale and Chubb frequently.",
    "recommended_actions": ["Create car locksmith landing page", "Add schema to service pages"],
}


@pytest.mark.asyncio
async def test_analyze_competitors_returns_gap_report():
    from backend.modules.competitor_intel.analyzer import CompetitorAnalyzer

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))

    analyzer = CompetitorAnalyzer(db=db)
    analyzer.llm = MagicMock()
    analyzer.llm.generate_json.return_value = MOCK_GAP_ANALYSIS

    result = await analyzer.run(
        site_id=1,
        competitor_domains=["checkatrade.com", "mybuilder.com"],
        our_domain="fastlock.co.uk",
    )

    assert "analysis" in result
    assert len(result["analysis"]["content_gaps"]) == 2
    assert result["analysis"]["content_gaps"][0]["topic"] == "car locksmith"
    assert len(result["domains_analyzed"]) == 2


@pytest.mark.asyncio
async def test_analyze_with_no_serpapi_key():
    from backend.modules.competitor_intel.analyzer import CompetitorAnalyzer

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))

    analyzer = CompetitorAnalyzer(db=db)
    analyzer.llm = MagicMock()
    analyzer.llm.generate_json.return_value = MOCK_GAP_ANALYSIS

    # With no serpapi_key, _get_top_pages should return mock data
    pages = await analyzer._get_top_pages("example.com")
    assert len(pages) == 1
    assert "mock" in pages[0]["title"].lower()


def test_gap_analysis_structure():
    """Verify the expected gap analysis shape."""
    required_keys = ["ranking_factors", "content_gaps", "structural_insights", "recommended_actions"]
    for key in required_keys:
        assert key in MOCK_GAP_ANALYSIS
