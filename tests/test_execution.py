"""Tests for CMSPublisher — mocked DB + HTTP."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime


def make_mock_page():
    page = MagicMock()
    page.id = 1
    page.site_id = 1
    page.title = "Emergency Locksmith London"
    page.meta_desc = "24/7 locksmith service in London."
    page.content = "<h1>Emergency Locksmith London</h1><p>We provide fast locksmith services.</p>"
    page.schema_json = {"@type": "FAQPage"}
    page.word_count = 600
    page.status = "draft"
    page.cms_post_id = None
    return page


def make_mock_site(cms_type="wordpress"):
    site = MagicMock()
    site.id = 1
    site.cms_type = cms_type
    return site


@pytest.mark.asyncio
async def test_dry_run_returns_diff():
    from backend.modules.execution.publisher import CMSPublisher

    page = make_mock_page()
    site = make_mock_site()

    mock_result_page = MagicMock()
    mock_result_page.scalar_one_or_none.return_value = page
    mock_result_site = MagicMock()
    mock_result_site.scalar_one_or_none.return_value = site

    call_count = 0
    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        return mock_result_page if call_count == 1 else mock_result_site

    db = AsyncMock()
    db.execute = mock_execute

    publisher = CMSPublisher(db=db)
    result = await publisher.publish_page(content_page_id=1, dry_run=True)

    assert result["dry_run"] is True
    assert result["cms_type"] == "wordpress"
    assert "diff" in result
    assert result["diff"]["title"] == "Emergency Locksmith London"
    assert result["message"] == "Set dry_run=False to publish."


@pytest.mark.asyncio
async def test_publish_page_not_found():
    from backend.modules.execution.publisher import CMSPublisher

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    publisher = CMSPublisher(db=db)
    result = await publisher.publish_page(content_page_id=999, dry_run=True)

    assert "error" in result
    assert "not found" in result["error"].lower()


def test_build_diff():
    from backend.modules.execution.publisher import CMSPublisher
    publisher = CMSPublisher(db=MagicMock())
    page = make_mock_page()
    diff = publisher._build_diff(page)

    assert diff["title"] == "Emergency Locksmith London"
    assert diff["word_count"] == 600
    assert "content_preview" in diff
    assert len(diff["content_preview"]) > 0
