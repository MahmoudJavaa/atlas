"""Tests for GEOOptimizer — mocked LLM responses."""
import pytest
import json
from unittest.mock import MagicMock, patch


MOCK_GEO_ANALYSIS = {
    "geo_score": 72,
    "direct_answer": True,
    "entity_rich": True,
    "structured_for_llm": False,
    "issues": ["Content lacks clear section headers for LLM parsing"],
    "recommendations": ["Add FAQ section", "Break into shorter paragraphs"],
    "faq_suggestions": [
        {"question": "How much does a locksmith cost?", "answer": "Typically £60-£150 depending on the service."}
    ],
    "entity_suggestions": ["Yale", "Chubb", "British Locksmith Association"],
}

MOCK_FAQ_SCHEMA = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
        {
            "@type": "Question",
            "name": "How much does a locksmith cost?",
            "acceptedAnswer": {"@type": "Answer", "text": "Typically £60-£150 depending on the service."},
        }
    ],
}

MOCK_HOWTO_SCHEMA = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    "name": "How to Find a Locksmith",
    "step": [{"@type": "HowToStep", "text": "Search for local locksmiths"}],
}


def make_mock_llm(responses):
    """Create a mock LLM that returns different responses for sequential generate_json calls."""
    call_count = 0
    def mock_generate_json(prompt, **kwargs):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return responses[idx]
    llm = MagicMock()
    llm.generate_json.side_effect = mock_generate_json
    return llm


@pytest.mark.asyncio
async def test_geo_score_content():
    from backend.modules.geo_engine.optimizer import GEOOptimizer
    optimizer = GEOOptimizer()
    optimizer.llm = make_mock_llm([MOCK_GEO_ANALYSIS, MOCK_FAQ_SCHEMA, MOCK_HOWTO_SCHEMA])

    result = await optimizer.run(
        content="FastLock provides locksmith services in London. We are available 24/7.",
        url="https://fastlock.co.uk/locksmith-london/",
    )

    assert result["url"] == "https://fastlock.co.uk/locksmith-london/"
    assert result["analysis"]["geo_score"] == 72
    assert result["analysis"]["direct_answer"] is True
    assert len(result["analysis"]["faq_suggestions"]) == 1
    assert "schemas" in result


@pytest.mark.asyncio
async def test_faq_schema_fallback():
    from backend.modules.geo_engine.optimizer import GEOOptimizer
    optimizer = GEOOptimizer()

    call_count = 0
    def mock_generate_json(prompt, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MOCK_GEO_ANALYSIS
        else:
            raise json.JSONDecodeError("bad", "", 0)

    optimizer.llm = MagicMock()
    optimizer.llm.generate_json.side_effect = mock_generate_json

    result = await optimizer.run(content="Some content", url="")
    # Should still have a valid schema via the fallback builder
    assert result["schemas"]["faq"]["@type"] == "FAQPage"


@pytest.mark.asyncio
async def test_empty_faq_returns_empty_schema():
    from backend.modules.geo_engine.optimizer import GEOOptimizer
    optimizer = GEOOptimizer()

    no_faq_analysis = {**MOCK_GEO_ANALYSIS, "faq_suggestions": []}
    optimizer.llm = make_mock_llm([no_faq_analysis, MOCK_HOWTO_SCHEMA])

    result = await optimizer.run(content="Some content")
    assert result["schemas"]["faq"] == {}
