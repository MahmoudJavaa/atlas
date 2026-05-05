"""Tests for BacklinkFinder — mocked SerpAPI + LLM."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock


MOCK_SCORE = {"score": 0.8, "reasoning": "Highly relevant resource page", "outreach_difficulty": "easy"}
MOCK_EMAIL = {"subject": "Content collaboration opportunity", "body": "Hi, I noticed your great article on locksmith resources..."}


@pytest.mark.asyncio
async def test_find_backlinks_returns_opportunities():
    from backend.modules.backlink_ai.finder import BacklinkFinder

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 1))

    finder = BacklinkFinder(db=db)

    call_count = 0
    def mock_generate_json(prompt, **kwargs):
        nonlocal call_count
        call_count += 1
        if "Score" in prompt or "score" in prompt.lower():
            return MOCK_SCORE
        else:
            return MOCK_EMAIL

    finder.llm = MagicMock()
    finder.llm.generate_json.side_effect = mock_generate_json

    result = await finder.run(
        site_id=1,
        target_domain="fastlock.co.uk",
        topic="locksmith",
    )

    assert result["opportunities_found"] >= 1
    assert result["opportunities"][0]["score"] == 0.8


@pytest.mark.asyncio
async def test_find_opportunities_no_serpapi():
    from backend.modules.backlink_ai.finder import BacklinkFinder

    db = AsyncMock()
    finder = BacklinkFinder(db=db)

    # Without SerpAPI key, returns mock opportunity
    opps = await finder._find_opportunities("fastlock.co.uk", "locksmith")
    assert len(opps) == 1
    assert opps[0]["type"] == "resource_page"


def test_score_and_email_structure():
    """Verify mock structures match expected schema."""
    assert 0 <= MOCK_SCORE["score"] <= 1
    assert MOCK_SCORE["outreach_difficulty"] in ("easy", "medium", "hard")
    assert "subject" in MOCK_EMAIL
    assert "body" in MOCK_EMAIL
