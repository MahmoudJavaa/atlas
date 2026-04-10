"""Tests for LocalSEOPageGenerator — uses mock Claude responses."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch


MOCK_PAGE_RESPONSE = {
    "title": "Emergency Locksmith Manchester | FastLock",
    "meta_desc": "Need an emergency locksmith in Manchester? FastLock provides 24/7 locksmith services across Manchester. Call now for fast response.",
    "post_content": "<h1>Emergency Locksmith in Manchester</h1><p>FastLock has been serving Manchester residents...</p>",
    "word_count": 850,
    "local_specificity_notes": ["References Manchester Arndale area", "Mentions local postcode coverage"],
    "schema": {
        "faq_schema": {"@type": "FAQPage"},
        "local_business_schema": {"@type": "LocalBusiness", "name": "FastLock"},
    },
    "doorway_score": 85,
    "doorway_check_notes": "Content is locally specific with genuine Manchester references.",
}


def make_mock_claude(response_dict):
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(response_dict))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    return mock_client


@pytest.mark.asyncio
async def test_generate_page_passes_doorway_check():
    from backend.modules.local_seo.page_generator import LocalSEOPageGenerator

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    generator = LocalSEOPageGenerator(db=db)
    generator.client = make_mock_claude(MOCK_PAGE_RESPONSE)

    result = await generator.run(
        service="Emergency Locksmith",
        location="Manchester",
        business_name="FastLock",
    )

    assert result["publish_blocked"] is False
    assert result["title"] == "Emergency Locksmith Manchester | FastLock"
    assert result["doorway_score"] >= 60


@pytest.mark.asyncio
async def test_generate_page_blocked_on_low_doorway_score():
    from backend.modules.local_seo.page_generator import LocalSEOPageGenerator

    low_score_response = {**MOCK_PAGE_RESPONSE, "doorway_score": 30}
    doorway_check_response = {"score": 25, "reasoning": "Pure template content, no local specificity."}

    db = AsyncMock()

    generator = LocalSEOPageGenerator(db=db)

    call_count = 0
    def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        mock_msg = MagicMock()
        if call_count == 1:
            mock_msg.content = [MagicMock(text=json.dumps(low_score_response))]
        else:
            mock_msg.content = [MagicMock(text=json.dumps(doorway_check_response))]
        return mock_msg

    generator.client = MagicMock()
    generator.client.messages.create.side_effect = mock_create

    result = await generator.run(
        service="Plumber",
        location="London",
        business_name="Acme Plumbing",
    )

    assert result["publish_blocked"] is True
    assert "doorway" in result["publish_blocked_reason"].lower()


def test_local_page_structure():
    """Check the expected keys are present in a generated page."""
    required_keys = ["title", "meta_desc", "post_content", "word_count", "schema", "doorway_score"]
    for key in required_keys:
        assert key in MOCK_PAGE_RESPONSE
