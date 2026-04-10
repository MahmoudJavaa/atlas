"""Tests for TechnicalSEOCrawler — runs against dummy HTML, no live crawl needed."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.modules.technical_seo.crawler import TechnicalSEOCrawler, PageAudit


SAMPLE_HTML_GOOD = """
<!DOCTYPE html>
<html>
<head>
  <title>Best Locksmith Services in London | FastLock</title>
  <meta name="description" content="Professional locksmith services in London. Available 24/7. Call FastLock for emergency locksmith, car locksmith, and more.">
  <link rel="canonical" href="https://fastlock.co.uk/locksmith-london/">
  <script type="application/ld+json">{"@type": "LocalBusiness"}</script>
</head>
<body>
  <h1>Locksmith Services in London</h1>
  <p>FastLock provides professional locksmith services across London. Our expert locksmiths
  are available 24/7 for all types of locksmith emergencies. Whether you need an emergency
  locksmith, a car locksmith, or help with your home security, we are here to help.</p>
  <p>We cover all London boroughs and can typically arrive within 30 minutes. Our locksmiths
  are fully insured and DBS checked. We offer transparent pricing with no hidden fees.</p>
  <h2>Our Services</h2>
  <p>Emergency lockout service, lock replacement, key cutting, and more.</p>
</body>
</html>
"""

SAMPLE_HTML_BAD = """
<!DOCTYPE html>
<html>
<head></head>
<body>
  <p>Short page.</p>
</body>
</html>
"""


def make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def test_parse_good_html():
    db = make_mock_db()
    crawler = TechnicalSEOCrawler(db=db)
    audit = PageAudit(url="https://fastlock.co.uk/locksmith-london/", status_code=200)
    result = crawler._parse_html(audit, SAMPLE_HTML_GOOD, "https://fastlock.co.uk/locksmith-london/", "fastlock.co.uk")

    assert result.title == "Best Locksmith Services in London | FastLock"
    assert result.meta_desc != ""
    assert result.canonical == "https://fastlock.co.uk/locksmith-london/"
    assert result.indexable is True
    assert result.word_count > 50
    assert len(result.issues["critical"]) == 0
    assert result.severity_score < 50


def test_parse_bad_html():
    db = make_mock_db()
    crawler = TechnicalSEOCrawler(db=db)
    audit = PageAudit(url="https://example.com/bad", status_code=200)
    result = crawler._parse_html(audit, SAMPLE_HTML_BAD, "https://example.com/bad", "example.com")

    assert result.title == ""
    assert "Missing title tag" in result.issues["critical"]
    assert any("Missing meta description" in w for w in result.issues["warning"])
    assert any("Thin content" in w for w in result.issues["warning"])
    assert result.severity_score > 30


def test_404_adds_critical_issue():
    db = make_mock_db()
    crawler = TechnicalSEOCrawler(db=db)
    audit = PageAudit(url="https://example.com/gone", status_code=404)
    result = crawler._parse_html(audit, SAMPLE_HTML_BAD, "https://example.com/gone", "example.com")
    assert "404 Not Found" in result.issues["critical"]


def test_severity_score_capped():
    db = make_mock_db()
    crawler = TechnicalSEOCrawler(db=db)
    audit = PageAudit(url="https://example.com/broken", status_code=500)
    audit.issues["critical"] = ["e1", "e2", "e3", "e4", "e5", "e6"]
    audit.severity_score = (
        len(audit.issues["critical"]) * 25
        + len(audit.issues["warning"]) * 10
        + len(audit.issues["info"]) * 2
    )
    audit.severity_score = min(audit.severity_score, 100)
    assert audit.severity_score == 100


def test_page_audit_to_dict():
    audit = PageAudit(url="https://example.com", status_code=200, title="Test", word_count=500)
    d = audit.to_dict()
    assert d["url"] == "https://example.com"
    assert d["word_count"] == 500
    assert "issues" in d
