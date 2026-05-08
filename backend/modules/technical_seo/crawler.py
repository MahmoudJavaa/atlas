"""Technical SEO Crawler — httpx-based with comprehensive SEO checks."""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.crawl import CrawlResult

# File extensions to skip (binaries, media, docs)
_IGNORED_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".mp4", ".mp3", ".wav", ".avi", ".mov", ".webm",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".rar",
    ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf", ".eot",
}

# Tracking/analytics query params to strip before deduplication
_STRIP_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "_ga", "_gid", "ref", "mc_cid", "mc_eid",
}


def _should_skip(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in _IGNORED_EXT)


def _strip_tracking_params(url: str) -> str:
    """Remove known tracking query params so /page?utm_source=a and ?utm_source=b dedup."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in params.items() if k.lower() not in _STRIP_PARAMS}
    new_query = urlencode(filtered, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _normalize_url(url: str) -> str:
    """Strip trailing slash (except bare domain) and tracking params."""
    url = url.rstrip("/") or url
    return _strip_tracking_params(url)


@dataclass
class PageAudit:
    url: str
    status_code: int = 0
    title: str = ""
    meta_desc: str = ""
    canonical: str = ""
    redirect_url: str = ""
    indexable: bool = True
    word_count: int = 0
    h1_count: int = 0
    response_time_ms: int = 0
    page_depth: int = 0
    issues: dict = field(default_factory=lambda: {"critical": [], "warning": [], "info": [], "_links": []})
    severity_score: int = 0

    def to_dict(self) -> dict:
        issues_clean = {k: v for k, v in self.issues.items() if not k.startswith("_")}
        return {
            "url": self.url,
            "status_code": self.status_code,
            "title": self.title,
            "meta_desc": self.meta_desc,
            "canonical": self.canonical,
            "redirect_url": self.redirect_url,
            "indexable": self.indexable,
            "word_count": self.word_count,
            "h1_count": self.h1_count,
            "response_time_ms": self.response_time_ms,
            "page_depth": self.page_depth,
            "issues": issues_clean,
            "severity_score": self.severity_score,
        }


class TechnicalSEOCrawler:
    """Crawls a site, audits each page with 25+ SEO checks, stores results in DB."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.visited: set[str] = set()
        self.crawl_run_id: str = uuid.uuid4().hex

    async def run(self, site_id: int, start_url: str, max_pages: int = 100) -> list[dict]:
        """Main entry point — deletes old results, runs crawl, flags duplicates."""
        from sqlalchemy import delete
        await self.db.execute(delete(CrawlResult).where(CrawlResult.site_id == site_id))
        await self.db.flush()

        results = await self._crawl_with_httpx(site_id, start_url, max_pages)

        # Post-crawl: detect duplicate titles / meta descriptions across pages
        await self._flag_duplicates(site_id, results)

        await self.db.commit()
        return results

    async def _crawl_with_httpx(self, site_id: int, start_url: str, max_pages: int) -> list[dict]:
        import httpx
        import ssl
        import certifi

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        results: list[dict] = []

        # Normalise start URL
        start_url = _normalize_url(start_url)

        # Queue: (url, depth) — deque for O(1) popleft
        queue: deque[tuple[str, int]] = deque([(start_url, 0)])
        queued: set[str] = {start_url}
        base_domain = urlparse(start_url).netloc
        # Accept both www and non-www variants
        alt_domain = base_domain[4:] if base_domain.startswith("www.") else f"www.{base_domain}"

        # Fetch robots.txt once
        disallowed = await self._fetch_robots(start_url)

        async with httpx.AsyncClient(
            follow_redirects=False,          # ← Disabled so we detect 3xx ourselves
            timeout=20,
            verify=ssl_ctx,
            headers={"User-Agent": "AtlasBot/2.0 SEO-Auditor (+https://atlas.app/bot)"},
        ) as client:
            while queue and len(self.visited) < max_pages:
                url, depth = queue.popleft()
                if url in self.visited or _should_skip(url):
                    continue
                self.visited.add(url)

                audit = PageAudit(url=url, page_depth=depth)

                # Check robots.txt disallow
                path = urlparse(url).path or "/"
                if any(path.startswith(d) for d in disallowed):
                    audit.issues["info"].append("Blocked by robots.txt")
                    audit.severity_score = 2
                    results.append(audit.to_dict())
                    await self._save_result(site_id, audit)
                    continue

                try:
                    t0 = time.monotonic()
                    resp = await client.get(url)
                    audit.response_time_ms = int((time.monotonic() - t0) * 1000)
                    audit.status_code = resp.status_code
                except httpx.TimeoutException:
                    audit.issues["critical"].append("Request timeout (>20s)")
                    audit.severity_score = 100
                    results.append(audit.to_dict())
                    await self._save_result(site_id, audit)
                    continue
                except httpx.ConnectError:
                    audit.issues["critical"].append("Connection failed")
                    audit.severity_score = 100
                    results.append(audit.to_dict())
                    await self._save_result(site_id, audit)
                    continue
                except Exception as e:
                    audit.issues["critical"].append(f"Request failed: {type(e).__name__}")
                    audit.severity_score = 100
                    results.append(audit.to_dict())
                    await self._save_result(site_id, audit)
                    continue

                # ── Handle redirects (3xx) ──────────────────────────────────
                if 300 <= audit.status_code < 400:
                    location = resp.headers.get("location", "")
                    if location:
                        dest = _normalize_url(urljoin(url, location))
                        audit.redirect_url = dest
                        dest_netloc = urlparse(dest).netloc
                        # Queue the destination if it's on the same domain
                        if dest not in self.visited and dest not in queued and dest_netloc in (base_domain, alt_domain):
                            queue.append((dest, depth))
                            queued.add(dest)
                    audit.issues["warning"].append(f"Redirect {audit.status_code}")
                    audit.severity_score = 10
                    results.append(audit.to_dict())
                    await self._save_result(site_id, audit)
                    await asyncio.sleep(0.15)
                    continue

                # ── Only parse HTML content ─────────────────────────────────
                content_type = resp.headers.get("content-type", "")
                if "html" not in content_type:
                    audit.issues["info"].append(f"Non-HTML response ({content_type.split(';')[0].strip()})")
                    audit.severity_score = 2
                    results.append(audit.to_dict())
                    await self._save_result(site_id, audit)
                    await asyncio.sleep(0.15)
                    continue

                html = resp.text

                # Politeness delay
                await asyncio.sleep(0.15)

                audit = self._parse_html(audit, html, url, base_domain, alt_domain)
                results.append(audit.to_dict())
                await self._save_result(site_id, audit)

                # Enqueue discovered links
                for link in audit.issues.pop("_links", []):
                    link = _normalize_url(link)
                    netloc = urlparse(link).netloc
                    if link not in self.visited and link not in queued and netloc in (base_domain, alt_domain):
                        queue.append((link, depth + 1))
                        queued.add(link)

        return results

    def _parse_html(self, audit: PageAudit, html: str, url: str, base_domain: str, alt_domain: str = "") -> PageAudit:
        soup = BeautifulSoup(html, "html.parser")

        # ── HTTPS check ───────────────────────────────────────────────────────
        if url.startswith("http://"):
            audit.issues["critical"].append("Page served over HTTP (not HTTPS)")

        # ── Status code errors ────────────────────────────────────────────────
        sc = audit.status_code
        if sc == 404:
            audit.issues["critical"].append("404 Not Found")
        elif sc == 410:
            audit.issues["critical"].append("410 Gone")
        elif sc >= 500:
            audit.issues["critical"].append(f"Server error {sc}")

        # Skip content checks for error pages
        if sc >= 400:
            n_crit = len(audit.issues["critical"])
            audit.severity_score = min(n_crit * 30, 100)
            audit.issues["_links"] = []
            return audit

        # ── Response time ─────────────────────────────────────────────────────
        if audit.response_time_ms > 3000:
            audit.issues["critical"].append(f"Slow page load ({audit.response_time_ms}ms)")
        elif audit.response_time_ms > 1500:
            audit.issues["warning"].append(f"Page load slow ({audit.response_time_ms}ms)")

        # ── Title ─────────────────────────────────────────────────────────────
        title_tag = soup.find("title")
        audit.title = title_tag.get_text(strip=True) if title_tag else ""
        if not audit.title:
            audit.issues["critical"].append("Missing title tag")
        elif len(audit.title) > 60:
            audit.issues["warning"].append(f"Title too long ({len(audit.title)} chars)")
        elif len(audit.title) < 30:
            audit.issues["warning"].append(f"Title too short ({len(audit.title)} chars)")

        # ── Meta description ──────────────────────────────────────────────────
        meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        audit.meta_desc = meta_tag.get("content", "").strip() if meta_tag else ""
        if not audit.meta_desc:
            audit.issues["warning"].append("Missing meta description")
        elif len(audit.meta_desc) > 160:
            audit.issues["warning"].append(f"Meta description too long ({len(audit.meta_desc)} chars)")
        elif len(audit.meta_desc) < 70:
            audit.issues["info"].append(f"Meta description too short ({len(audit.meta_desc)} chars)")

        # ── Canonical ─────────────────────────────────────────────────────────
        canon_tag = soup.find("link", attrs={"rel": "canonical"})
        audit.canonical = canon_tag.get("href", "").strip() if canon_tag else ""
        if not audit.canonical:
            audit.issues["warning"].append("Missing canonical tag")
        else:
            # Resolve relative canonicals before comparing
            canon_abs = urljoin(url, audit.canonical)
            canon_norm = canon_abs.rstrip("/")
            url_norm = url.rstrip("/")
            canon_netloc = urlparse(canon_abs).netloc
            url_netloc = urlparse(url).netloc
            if canon_norm != url_norm and canon_netloc not in (url_netloc, base_domain, alt_domain):
                audit.issues["info"].append("Canonical points to different domain")
            elif canon_norm != url_norm:
                audit.issues["info"].append("Canonical points to different URL (canonicalized away)")

        # ── Robots / indexability ─────────────────────────────────────────────
        robots_meta = soup.find("meta", attrs={"name": re.compile(r"robots", re.I)})
        if robots_meta:
            content = robots_meta.get("content", "").lower()
            if "noindex" in content:
                audit.indexable = False
                audit.issues["warning"].append("Noindex tag — page excluded from search")
            if "nofollow" in content:
                audit.issues["info"].append("Nofollow tag — links not passed")

        # ── Word count (strip chrome elements for accuracy) ───────────────────
        body = soup.find("body")
        if body:
            for el in body.find_all(["script", "style", "nav", "footer", "header", "aside"]):
                el.decompose()
            text = body.get_text(separator=" ", strip=True)
            audit.word_count = len(text.split())
        if audit.word_count < 300:
            audit.issues["warning"].append(f"Thin content ({audit.word_count} words)")

        # ── Headings ──────────────────────────────────────────────────────────
        h1_tags = soup.find_all("h1")
        audit.h1_count = len(h1_tags)
        if not h1_tags:
            audit.issues["warning"].append("Missing H1 tag")
        elif len(h1_tags) > 1:
            audit.issues["warning"].append(f"Multiple H1 tags ({len(h1_tags)})")

        h2_tags = soup.find_all("h2")
        if not h2_tags and audit.word_count > 500:
            audit.issues["info"].append("No H2 subheadings on long page")

        # ── Images ────────────────────────────────────────────────────────────
        all_imgs = soup.find_all("img")
        # alt="" is valid for decorative images — only flag absent alt attribute
        missing_alt = [img for img in all_imgs if img.get("alt") is None]
        if missing_alt:
            audit.issues["info"].append(f"{len(missing_alt)} image(s) missing alt text")

        # ── Viewport / mobile-friendly ────────────────────────────────────────
        viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        if not viewport:
            audit.issues["warning"].append("Missing viewport meta tag (not mobile-friendly)")

        # ── Structured data ───────────────────────────────────────────────────
        schema_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
        if not schema_tags:
            audit.issues["info"].append("No structured data (JSON-LD) found")

        # ── Open Graph ────────────────────────────────────────────────────────
        og_title = soup.find("meta", attrs={"property": "og:title"})
        og_desc  = soup.find("meta", attrs={"property": "og:description"})
        og_image = soup.find("meta", attrs={"property": "og:image"})
        missing_og = []
        if not og_title:  missing_og.append("og:title")
        if not og_desc:   missing_og.append("og:description")
        if not og_image:  missing_og.append("og:image")
        if missing_og:
            audit.issues["info"].append(f"Missing Open Graph tags: {', '.join(missing_og)}")

        # ── Page depth warning ────────────────────────────────────────────────
        if audit.page_depth > 4:
            audit.issues["warning"].append(f"Page buried deep ({audit.page_depth} clicks from home)")

        # ── Discover internal links ───────────────────────────────────────────
        _netloc = urlparse(url).netloc
        _alt = _netloc[4:] if _netloc.startswith("www.") else f"www.{_netloc}"
        discovered: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            full = urljoin(url, href).split("#")[0]
            full = _normalize_url(full)
            full_netloc = urlparse(full).netloc
            if full_netloc in (_netloc, _alt) and full.startswith("http"):
                discovered.add(full)
        audit.issues["_links"] = list(discovered)

        # ── Severity score ────────────────────────────────────────────────────
        n_crit = len(audit.issues["critical"])
        n_warn = len(audit.issues["warning"])
        n_info = len(audit.issues["info"])
        audit.severity_score = min(n_crit * 30 + n_warn * 10 + n_info * 2, 100)

        return audit

    async def _flag_duplicates(self, site_id: int, results: list[dict]):
        """After full crawl, mark pages that share identical title or meta_desc."""
        from sqlalchemy import update, select

        title_map: dict[str, list[int]] = defaultdict(list)
        meta_map:  dict[str, list[int]] = defaultdict(list)

        stmt = select(CrawlResult).where(
            CrawlResult.site_id == site_id,
            CrawlResult.crawl_run_id == self.crawl_run_id,
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        for row in rows:
            if row.title:
                title_map[row.title.strip().lower()].append(row.id)
            if row.meta_desc:
                meta_map[row.meta_desc.strip().lower()].append(row.id)

        dup_title_ids = {rid for ids in title_map.values() if len(ids) > 1 for rid in ids}
        dup_meta_ids  = {rid for ids in meta_map.values()  if len(ids) > 1 for rid in ids}

        for row in rows:
            extra: list[tuple[str, str]] = []
            if row.id in dup_title_ids:
                extra.append(("warning", "Duplicate title tag"))
            if row.id in dup_meta_ids:
                extra.append(("warning", "Duplicate meta description"))

            if extra:
                issues = dict(row.issues)
                for severity, msg in extra:
                    if msg not in issues.get(severity, []):
                        issues.setdefault(severity, []).append(msg)
                score = min(
                    len(issues.get("critical", [])) * 30
                    + len(issues.get("warning", [])) * 10
                    + len(issues.get("info", [])) * 2,
                    100,
                )
                await self.db.execute(
                    update(CrawlResult)
                    .where(CrawlResult.id == row.id)
                    .values(issues=issues, severity_score=score)
                )

    async def _fetch_robots(self, start_url: str) -> list[str]:
        """Fetch robots.txt and return disallowed paths for * or AtlasBot."""
        import httpx
        disallowed: list[str] = []
        try:
            parsed = urlparse(start_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 200:
                    current_ua_matches = False
                    for line in resp.text.splitlines():
                        line = line.strip()
                        if line.lower().startswith("user-agent:"):
                            ua = line.split(":", 1)[1].strip()
                            current_ua_matches = ua in ("*", "AtlasBot")
                        elif current_ua_matches and line.lower().startswith("disallow:"):
                            path = line.split(":", 1)[1].strip()
                            if path:
                                disallowed.append(path)
        except Exception:
            pass
        return disallowed

    async def _save_result(self, site_id: int, audit: PageAudit):
        """Save one page audit to DB. Errors are swallowed so crawl continues."""
        issues_clean = {k: v for k, v in audit.issues.items() if not k.startswith("_")}
        row = CrawlResult(
            site_id=site_id,
            crawl_run_id=self.crawl_run_id,
            url=audit.url,
            status_code=audit.status_code,
            title=audit.title,
            meta_desc=audit.meta_desc,
            canonical=audit.canonical,
            redirect_url=audit.redirect_url or None,
            indexable=audit.indexable,
            word_count=audit.word_count,
            h1_count=audit.h1_count,
            response_time_ms=audit.response_time_ms or None,
            page_depth=audit.page_depth,
            issues=issues_clean,
            severity_score=audit.severity_score,
        )
        try:
            self.db.add(row)
            await self.db.flush()
        except Exception:
            # Don't let one bad row kill the whole crawl
            await self.db.rollback()
