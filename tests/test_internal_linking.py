"""Tests for SiloBuilder — mocked crawl data + LLM."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock


MOCK_SILO_PLAN = {
    "pillar_pages": [
        {
            "url": "https://fastlock.co.uk/locksmith-services/",
            "topic": "locksmith services",
            "supporting_pages": [
                "https://fastlock.co.uk/emergency-locksmith/",
                "https://fastlock.co.uk/car-locksmith/",
            ],
        }
    ],
    "orphan_pages": ["https://fastlock.co.uk/old-promo/"],
    "over_linked_pages": [],
    "linking_recommendations": [
        {
            "from_url": "https://fastlock.co.uk/emergency-locksmith/",
            "to_url": "https://fastlock.co.uk/locksmith-services/",
            "anchor_text": "locksmith services",
            "reason": "Supporting page should link to pillar",
        }
    ],
    "cannibalization_risks": [],
}


def make_mock_crawl_data():
    """Create mock CrawlResult rows."""
    rows = []
    for url, title in [
        ("https://fastlock.co.uk/locksmith-services/", "Locksmith Services"),
        ("https://fastlock.co.uk/emergency-locksmith/", "Emergency Locksmith"),
        ("https://fastlock.co.uk/car-locksmith/", "Car Locksmith"),
        ("https://fastlock.co.uk/old-promo/", "Old Promo Page"),
    ]:
        row = MagicMock()
        row.url = url
        row.title = title
        row.word_count = 800
        row.indexable = True
        rows.append(row)
    return rows


@pytest.mark.asyncio
async def test_build_silo_returns_plan():
    from backend.modules.internal_linking.silo import SiloBuilder

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = make_mock_crawl_data()

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    builder = SiloBuilder(db=db)
    builder.llm = MagicMock()
    builder.llm.generate_json.return_value = MOCK_SILO_PLAN

    result = await builder.run(site_id=1)

    assert result["pages_analyzed"] == 4
    assert result["orphan_pages_found"] == 1
    assert len(result["silo_plan"]["pillar_pages"]) == 1
    assert len(result["silo_plan"]["linking_recommendations"]) == 1


@pytest.mark.asyncio
async def test_build_silo_no_crawl_data():
    from backend.modules.internal_linking.silo import SiloBuilder

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    builder = SiloBuilder(db=db)
    result = await builder.run(site_id=1)

    assert "error" in result
    assert "crawl" in result["error"].lower()
