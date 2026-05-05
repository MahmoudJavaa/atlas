"""Tests for AtlasAgent — mocked Gemini function-calling loop."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

import google.generativeai as genai


def make_fn_call_response(tool_name, tool_args):
    """Simulate a Gemini response that calls a function."""
    fn_call = MagicMock()
    fn_call.name = tool_name
    fn_call.args = tool_args

    part = MagicMock()
    part.function_call = fn_call
    part.text = ""

    # Make hasattr checks work correctly
    type(part).function_call = property(lambda self: fn_call)

    candidate = MagicMock()
    candidate.content.parts = [part]

    response = MagicMock()
    response.candidates = [candidate]
    return response


def make_text_response(text):
    """Simulate a Gemini response that ends with text (no function calls)."""
    part = MagicMock()
    part.text = text
    # No function_call
    fc = MagicMock()
    fc.name = ""
    part.function_call = fc

    candidate = MagicMock()
    candidate.content.parts = [part]

    response = MagicMock()
    response.candidates = [candidate]
    return response


@pytest.mark.asyncio
async def test_agent_executes_crawl_tool():
    from backend.modules.technical_seo.crawler import TechnicalSEOCrawler
    from backend.agents.atlas_agent import AtlasAgent

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    agent = AtlasAgent(db=db)

    # Mock the chat interface
    mock_chat = MagicMock()
    mock_chat.send_message.side_effect = [
        make_fn_call_response("crawl_site", {"site_id": 1, "start_url": "http://localhost:8000/docs", "max_pages": 1}),
        make_text_response("Crawl complete. Found 4 issues on the docs page."),
    ]
    agent.model = MagicMock()
    agent.model.start_chat.return_value = mock_chat

    # Mock the crawler to avoid actual HTTP call
    original_run = TechnicalSEOCrawler.run

    async def mock_run(self, **kwargs):
        return [{"url": "http://localhost:8000/docs", "issues": {"warning": ["Missing H1"]}, "severity_score": 20}]

    TechnicalSEOCrawler.run = mock_run
    try:
        result = await agent.run(goal="Crawl the site", site_id=1)
    finally:
        TechnicalSEOCrawler.run = original_run

    assert result["final_report"] == "Crawl complete. Found 4 issues on the docs page."
    assert len(result["audit_trail"]) == 1
    assert result["audit_trail"][0]["tool"] == "crawl_site"


@pytest.mark.asyncio
async def test_agent_max_iterations():
    from backend.agents.atlas_agent import AtlasAgent

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    agent = AtlasAgent(db=db)

    # Simulate model always calling a tool (infinite loop scenario)
    mock_chat = MagicMock()
    mock_chat.send_message.return_value = make_fn_call_response(
        "crawl_site", {"site_id": 1, "start_url": "http://test.com"}
    )
    agent.model = MagicMock()
    agent.model.start_chat.return_value = mock_chat

    # Mock the crawler
    import backend.modules.technical_seo.crawler as crawler_mod
    original_run = crawler_mod.TechnicalSEOCrawler.run

    async def mock_run(self, **kwargs):
        return []

    crawler_mod.TechnicalSEOCrawler.run = mock_run
    try:
        result = await agent.run(goal="Test max iterations", site_id=1)
    finally:
        crawler_mod.TechnicalSEOCrawler.run = original_run

    assert "error" in result
    assert "Max iterations" in result["error"]


@pytest.mark.asyncio
async def test_agent_handles_unknown_tool():
    from backend.agents.atlas_agent import AtlasAgent

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    agent = AtlasAgent(db=db)
    result = await agent._execute_tool("nonexistent_tool", {}, site_id=1)

    assert "error" in result
    assert "Unknown tool" in result["error"]


def test_tool_declarations_has_all_11():
    from backend.agents.atlas_agent import TOOL_DECLARATIONS
    # TOOL_DECLARATIONS is a list with one Tool containing all FunctionDeclarations
    fn_declarations = TOOL_DECLARATIONS[0].function_declarations
    tool_names = [fd.name for fd in fn_declarations]
    expected = [
        "crawl_site", "classify_keywords", "score_geo_answerability",
        "generate_content", "analyze_competitors", "build_silo",
        "generate_local_page", "find_backlink_opportunities",
        "pull_analytics", "publish_to_cms", "run_learning_loop",
    ]
    assert tool_names == expected
    assert len(fn_declarations) == 11
