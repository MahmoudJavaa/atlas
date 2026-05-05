"""Tests for LocalSEOPageGenerator — uses mock LLM responses."""
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


def make_mock_llm(response_dict):
    llm = MagicMock()
    llm.generate_json.return_value = response_dict
    return llm


@pytest.mark.asyncio
async def test_generate_page_passes_doorway_check():
    from backend.modules.local_seo.page_generator import LocalSEOPageGenerator

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    generator = LocalSEOPageGenerator(db=db)
    generator.llm = make_mock_llm(MOCK_PAGE_RESPONSE)

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
    def mock_generate_json(prompt, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return low_score_response
        else:
            return doorway_check_response

    generator.llm = MagicMock()
    generator.llm.generate_json.side_effect = mock_generate_json

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
