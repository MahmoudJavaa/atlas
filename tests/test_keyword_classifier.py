"""Tests for KeywordClassifier — mocked LLM + SerpAPI."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock


MOCK_CLASSIFICATION = [
    {"keyword": "locksmith london", "intent": "commercial", "cluster": "locksmith services", "funnel_stage": "BOFU"},
    {"keyword": "how to pick a lock", "intent": "informational", "cluster": "diy locksmith", "funnel_stage": "TOFU"},
    {"keyword": "buy lock picks", "intent": "transactional", "cluster": "locksmith tools", "funnel_stage": "BOFU"},
]


def make_mock_llm():
    llm = MagicMock()
    llm.generate_json.return_value = MOCK_CLASSIFICATION
    return llm


@pytest.mark.asyncio
async def test_classify_intent_returns_structured_data():
    from backend.modules.keyword_intel.classifier import KeywordClassifier

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    db.add = MagicMock()
    db.flush = AsyncMock()

    classifier = KeywordClassifier(db=db)
    classifier.llm = make_mock_llm()

    result = await classifier._classify_intent(
        [{"keyword": kw, "volume": None, "serp_features": []} for kw in
         ["locksmith london", "how to pick a lock", "buy lock picks"]]
    )

    assert len(result) == 3
    intents = {r["intent"] for r in result}
    assert "commercial" in intents
    assert "informational" in intents
    assert "transactional" in intents


def test_build_cluster_map():
    from backend.modules.keyword_intel.classifier import KeywordClassifier
    from unittest.mock import MagicMock

    classifier = KeywordClassifier(db=MagicMock())
    cluster_map = classifier._build_cluster_map(MOCK_CLASSIFICATION)

    assert "locksmith services" in cluster_map
    assert "diy locksmith" in cluster_map
    assert len(cluster_map["locksmith services"]) == 1


@pytest.mark.asyncio
async def test_enrich_via_serp_fallback_no_key():
    from backend.modules.keyword_intel.classifier import KeywordClassifier
    from unittest.mock import patch

    db = AsyncMock()
    classifier = KeywordClassifier(db=db)

    with patch("backend.modules.keyword_intel.classifier.settings") as mock_settings:
        mock_settings.serpapi_key = ""
        result = await classifier._enrich_via_serp(["test keyword"])

    assert len(result) == 1
    assert result[0]["keyword"] == "test keyword"
    assert result[0]["volume"] is None
