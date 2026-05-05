"""Tests for ContentGenerator — mocked LLM responses."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock


MOCK_CONTENT = {
    "title": "Emergency Locksmith London | 24/7 Fast Response",
    "meta_desc": "Need an emergency locksmith in London? Call FastLock for 24/7 service. Arrive in 30 minutes. No call-out fee.",
    "h1": "Emergency Locksmith London",
    "content_html": "<h1>Emergency Locksmith London</h1><p>FastLock provides fast, reliable locksmith services.</p><h2>Why Choose Us</h2><p>We arrive in 30 minutes.</p>",
    "word_count": 850,
    "schema": {"@type": "FAQPage", "mainEntity": []},
    "internal_link_suggestions": ["car locksmith", "lock replacement"],
}


def make_mock_llm():
    llm = MagicMock()
    llm.generate_json.return_value = MOCK_CONTENT
    return llm


def make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    mock_page = MagicMock()
    mock_page.id = 42
    db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 42))
    return db


@pytest.mark.asyncio
async def test_generate_content_returns_expected_keys():
    from backend.modules.content_engine.generator import ContentGenerator
    db = make_mock_db()
    gen = ContentGenerator(db=db)
    gen.llm = make_mock_llm()

    result = await gen.run(
        site_id=1,
        keyword="emergency locksmith london",
        intent="transactional",
        funnel_stage="BOFU",
        page_type="landing",
    )

    assert result["title"] == MOCK_CONTENT["title"]
    assert result["word_count"] == 850
    assert "content_page_id" in result
    assert result["content_html"].startswith("<h1>")


@pytest.mark.asyncio
async def test_generate_content_with_location():
    from backend.modules.content_engine.generator import ContentGenerator
    db = make_mock_db()
    gen = ContentGenerator(db=db)
    gen.llm = make_mock_llm()

    result = await gen.run(
        site_id=1,
        keyword="locksmith",
        intent="commercial",
        funnel_stage="MOFU",
        page_type="blog",
        location="Manchester",
    )

    # LLM was called with the location in the prompt
    call_args = gen.llm.generate_json.call_args
    prompt_text = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
    assert "Manchester" in prompt_text


@pytest.mark.asyncio
async def test_generate_handles_json_parse_error():
    from backend.modules.content_engine.generator import ContentGenerator
    db = make_mock_db()
    gen = ContentGenerator(db=db)

    gen.llm = MagicMock()
    gen.llm.generate_json.side_effect = json.JSONDecodeError("bad", "", 0)

    result = await gen.run(
        site_id=1, keyword="test", intent="informational",
        funnel_stage="TOFU", page_type="blog",
    )

    # Should return fallback content instead of crashing
    assert result["word_count"] == 0
    assert "error" in result["content_html"].lower() or result["title"] == "test"
