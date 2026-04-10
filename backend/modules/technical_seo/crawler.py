"""Technical SEO Crawler — uses Playwright for JS rendering + BeautifulSoup for parsing."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.crawl import CrawlResult


@dataclass
class PageAudit:
    url: str
    status_code: int = 0
    title: str = ""
    meta_desc: str = ""
    canonical: str = ""
    indexable: bool = True
    word_count: int = 0
    issues: dict = field(default_factory=lambda: {"critical": [], "warning": [], "info": []})
    severity_score: int = 0

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "title": self.title,
            "meta_desc": self.meta_desc,
            "canonical": self.canonical,
            "indexable": self.indexable,
            "word_count": self.word_count,
            "issues": self.issues,
            "severity_score": self.severity_score,
        }


class TechnicalSEOCrawler:
    """Crawls a site, audits each page, stores results in DB."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.visited: set[str] = set()

    async def run(self, site_id: int, start_url: str, max_pages: int = 100) -> list[dict]:
        """Main entry point. Returns list of audit dicts."""
        try:
            from playwright.async_api import async_playwright
            results = await self._crawl_with_playwright(site_id, start_url, max_pages)
        except ImportError:
            # Fallback to requests-based crawl (no JS rendering) for testing
            import httpx
            results = await self._crawl_with_httpx(site_id, start_url, max_pages)
        return results

    async def _crawl_with_playwright(self, site_id: int, start_url: str, max_pages: int) -> list[dict]:
        from playwright.async_api import async_playwright

        results = []
        queue = [start_url]
        base_domain = urlparse(start_url).netloc

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="AtlasBot/1.0 (+https://atlas.local/bot)"
            )
            page = await context.new_page()

            while queue and len(self.visited) < max_pages:
                url = queue.pop(0)
                if url in self.visited:
                    continue
                self.visited.add(url)

                audit = await self._audit_page_playwright(page, url, base_domain)
                results.append(audit.to_dict())

                # Persist to DB
                await self._save_result(site_id, audit)

                # Enqueue discovered links
                for link in audit.issues.get("_discovered_links", []):
                    if link not in self.visited and urlparse(link).netloc == base_domain:
                        queue.append(link)

            await browser.close()
        return results

    async def _audit_page_playwright(self, page, url: str, base_domain: str) -> PageAudit:
        audit = PageAudit(url=url)
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            audit.status_code = response.status if response else 0
            html = await page.content()
        except Exception as e:
            audit.issues["critical"].append(f"Page load failed: {e}")
            audit.severity_score = 100
            return audit

        return self._parse_html(audit, html, url, base_domain)

    async def _crawl_with_httpx(self, site_id: int, start_url: str, max_pages: int) -> list[dict]:
        import httpx
        results = []
        queue = [start_url]
        base_domain = urlparse(start_url).netloc

        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            while queue and len(self.visited) < max_pages:
                url = queue.pop(0)
                if url in self.visited:
                    continue
                self.visited.add(url)

                audit = PageAudit(url=url)
                try:
                    resp = await client.get(url)
                    audit.status_code = resp.status_code
                    html = resp.text
                except Exception as e:
                    audit.issues["critical"].append(f"Request failed: {e}")
                    audit.severity_score = 100
                    results.append(audit.to_dict())
                    await self._save_result(site_id, audit)
                    continue

                audit = self._parse_html(audit, html, url, base_domain)
                results.append(audit.to_dict())
                await self._save_result(site_id, audit)

                for link in audit.issues.pop("_discovered_links", []):
                    if link not in self.visited and urlparse(link).netloc == base_domain:
                        queue.append(link)

        return results

    def _parse_html(self, audit: PageAudit, html: str, url: str, base_domain: str) -> PageAudit:
        soup = BeautifulSoup(html, "html.parser")

        # Status code checks
        if audit.status_code == 404:
            audit.issues["critical"].append("404 Not Found")
        elif audit.status_code >= 500:
            audit.issues["critical"].append(f"Server error {audit.status_code}")
        elif 300 <= audit.status_code < 400:
            audit.issues["warning"].append(f"Redirect {audit.status_code}")

        # Title
        title_tag = soup.find("title")
        audit.title = title_tag.get_text(strip=True) if title_tag else ""
        if not audit.title:
            audit.issues["critical"].append("Missing title tag")
        elif len(audit.title) > 60:
            audit.issues["warning"].append(f"Title too long ({len(audit.title)} chars)")
        elif len(audit.title) < 30:
            audit.issues["warning"].append(f"Title too short ({len(audit.title)} chars)")

        # Meta description
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        audit.meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
        if not audit.meta_desc:
            audit.issues["warning"].append("Missing meta description")
        elif len(audit.meta_desc) > 160:
            audit.issues["info"].append(f"Meta description too long ({len(audit.meta_desc)} chars)")

        # Canonical
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        audit.canonical = canonical_tag.get("href", "").strip() if canonical_tag else ""
        if not audit.canonical:
            audit.issues["warning"].append("Missing canonical tag")

        # Indexability
        robots_meta = soup.find("meta", attrs={"name": re.compile("robots", re.I)})
        if robots_meta:
            content = robots_meta.get("content", "").lower()
            if "noindex" in content:
                audit.indexable = False
                audit.issues["info"].append("Page is noindex")

        # Word count
        body = soup.find("body")
        if body:
            text = body.get_text(separator=" ", strip=True)
            audit.word_count = len(text.split())
        if audit.word_count < 300:
            audit.issues["warning"].append(f"Thin content ({audit.word_count} words)")

        # Schema
        schema_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
        if not schema_tags:
            audit.issues["info"].append("No structured data (JSON-LD) found")

        # H1
        h1_tags = soup.find_all("h1")
        if not h1_tags:
            audit.issues["warning"].append("Missing H1 tag")
        elif len(h1_tags) > 1:
            audit.issues["warning"].append(f"Multiple H1 tags ({len(h1_tags)})")

        # Images without alt
        imgs_no_alt = [img for img in soup.find_all("img") if not img.get("alt")]
        if imgs_no_alt:
            audit.issues["info"].append(f"{len(imgs_no_alt)} image(s) missing alt text")

        # Discover internal links
        discovered = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            full_url = urljoin(url, href).split("#")[0].split("?")[0]
            if urlparse(full_url).netloc == base_domain and full_url.startswith("http"):
                discovered.append(full_url)
        audit.issues["_discovered_links"] = list(set(discovered))

        # Calculate severity score
        score = (
            len(audit.issues["critical"]) * 25
            + len(audit.issues["warning"]) * 10
            + len(audit.issues["info"]) * 2
        )
        audit.severity_score = min(score, 100)
        return audit

    async def _save_result(self, site_id: int, audit: PageAudit):
        issues = {k: v for k, v in audit.issues.items() if k != "_discovered_links"}
        crawl_result = CrawlResult(
            site_id=site_id,
            url=audit.url,
            status_code=audit.status_code,
            title=audit.title,
            meta_desc=audit.meta_desc,
            canonical=audit.canonical,
            indexable=audit.indexable,
            word_count=audit.word_count,
            issues=issues,
            severity_score=audit.severity_score,
        )
        self.db.add(crawl_result)
        await self.db.flush()
