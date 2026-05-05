"""Quick Audit — no auth required.

POST /api/v1/audit/start  { url, max_pages? }  → { audit_id }
GET  /api/v1/audit/{id}                        → audit state + page results

Works like Screaming Frog: crawls any public domain, extracts SEO data,
returns results as they arrive (client polls every 2 s).
No database, no Celery, no CMS credentials needed.
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

import warnings
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

router = APIRouter(prefix="/api/v1/audit", tags=["quick_audit"])

# In-memory store — audits expire when the server restarts (that's fine)
_audits: dict[str, "AuditState"] = {}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AtlasBot/1.0; +https://atlasseo.app) "
        "AtlasSEOCrawler/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

_IGNORED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".mp4", ".mp3", ".wav",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
}


# ─────────────────────────────────────────────────────────────────────────────
#  Data model
# ─────────────────────────────────────────────────────────────────────────────

class PageResult(dict):
    """Thin dict subclass — keeps IDE happy while staying JSON-serialisable."""


class AuditState:
    def __init__(self, start_url: str, max_pages: int = 200):
        self.id = str(uuid.uuid4())
        self.start_url = start_url
        self.max_pages = max_pages
        self.status = "running"   # running | complete | stopped | error
        self.pages: list[dict] = []
        self.crawled = 0
        self.queued = 0
        self.error: Optional[str] = None
        self._stop = False        # set to True on /stop

    def to_dict(self) -> dict:
        return {
            "audit_id": self.id,
            "start_url": self.start_url,
            "status": self.status,
            "crawled": self.crawled,
            "queued": self.queued,
            "total_issues": sum(len(p.get("issues", [])) for p in self.pages),
            "pages": self.pages,
            "error": self.error,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    url: str
    max_pages: int = 200


@router.post("/start")
async def start_audit(body: StartRequest, background_tasks: BackgroundTasks):
    url = body.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    audit = AuditState(start_url=url, max_pages=min(body.max_pages, 500))
    _audits[audit.id] = audit
    background_tasks.add_task(_run_crawl, audit)
    return {"audit_id": audit.id}


@router.get("/{audit_id}")
async def get_audit(audit_id: str):
    audit = _audits.get(audit_id)
    if not audit:
        return {"error": "Audit not found or expired"}
    return audit.to_dict()


@router.post("/{audit_id}/stop")
async def stop_audit(audit_id: str):
    audit = _audits.get(audit_id)
    if audit:
        audit._stop = True
        audit.status = "stopped"
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
#  Crawler
# ─────────────────────────────────────────────────────────────────────────────

async def _run_crawl(audit: AuditState) -> None:
    visited: set[str] = set()
    queue: list[str] = [audit.start_url]
    base = urlparse(audit.start_url)
    base_domain = base.netloc.lower()

    limits = httpx.Limits(max_connections=8, max_keepalive_connections=5)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            limits=limits,
            headers=_HEADERS,
        ) as client:
            while queue and not audit._stop:
                url = queue.pop(0)

                # Normalise + dedup
                url = url.split("#")[0].rstrip("/") or url
                if url in visited:
                    continue
                if len(visited) >= audit.max_pages:
                    break

                visited.add(url)

                page = await _fetch_page(client, url, base_domain)
                audit.pages.append(page)
                audit.crawled = len(visited)

                # Enqueue new internal links
                for link in page.get("_outlinks_internal", []):
                    norm = link.split("#")[0].rstrip("/") or link
                    if norm and norm not in visited and norm not in queue:
                        queue.append(norm)
                        audit.queued = len(queue)

                # Tiny yield so the event loop can breathe
                await asyncio.sleep(0)

    except Exception as exc:
        audit.error = str(exc)
        audit.status = "error"
        return

    audit.status = "complete" if not audit._stop else "stopped"
    audit.queued = 0


async def _fetch_page(client: httpx.AsyncClient, url: str, base_domain: str) -> dict:
    """Fetch one URL and extract SEO signals."""
    t0 = time.monotonic()
    result: dict = {
        "url": url,
        "status_code": 0,
        "content_type": "",
        "title": "",
        "title_length": 0,
        "meta_description": "",
        "meta_description_length": 0,
        "h1": "",
        "h1_count": 0,
        "h2_count": 0,
        "word_count": 0,
        "internal_links": 0,
        "external_links": 0,
        "images_total": 0,
        "images_missing_alt": 0,
        "response_time_ms": 0,
        "is_indexable": True,
        "canonical": "",
        "redirect_url": "",
        "issues": [],
        "_outlinks_internal": [],   # private: used to build queue, stripped on output
    }

    try:
        resp = await client.get(url)
        result["status_code"] = resp.status_code
        result["response_time_ms"] = int((time.monotonic() - t0) * 1000)
        ct = resp.headers.get("content-type", "").lower()
        result["content_type"] = ct.split(";")[0].strip()

        # Track final redirect destination
        if str(resp.url) != url:
            result["redirect_url"] = str(resp.url)

        # Only parse HTML
        if "text/html" not in ct:
            return result

        if resp.status_code >= 400:
            result["issues"].append(f"status_{resp.status_code}")
            result["is_indexable"] = False
            return result

        soup = BeautifulSoup(resp.text, "html.parser")

        # ── Meta robots / noindex ─────────────────────────────────────────
        robots_meta = soup.find("meta", attrs={"name": re.compile(r"robots", re.I)})
        if robots_meta:
            content_val = (robots_meta.get("content") or "").lower()
            if "noindex" in content_val:
                result["is_indexable"] = False
                result["issues"].append("noindex")

        # ── Title ─────────────────────────────────────────────────────────
        title_tag = soup.find("title")
        title_text = title_tag.get_text().strip() if title_tag else ""
        result["title"] = title_text[:120]
        result["title_length"] = len(title_text)
        if not title_text:
            result["issues"].append("missing_title")
        elif len(title_text) < 10:
            result["issues"].append("title_too_short")
        elif len(title_text) > 60:
            result["issues"].append("title_too_long")

        # ── Meta description ──────────────────────────────────────────────
        meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        desc_text = (meta_desc.get("content") or "").strip() if meta_desc else ""
        result["meta_description"] = desc_text[:200]
        result["meta_description_length"] = len(desc_text)
        if not desc_text:
            result["issues"].append("missing_meta_description")
        elif len(desc_text) > 160:
            result["issues"].append("meta_description_too_long")

        # ── Canonical ─────────────────────────────────────────────────────
        canonical = soup.find("link", rel="canonical")
        if canonical:
            result["canonical"] = (canonical.get("href") or "").strip()

        # ── H1 ────────────────────────────────────────────────────────────
        h1_tags = soup.find_all("h1")
        result["h1_count"] = len(h1_tags)
        result["h1"] = h1_tags[0].get_text().strip()[:100] if h1_tags else ""
        if not h1_tags:
            result["issues"].append("missing_h1")
        elif len(h1_tags) > 1:
            result["issues"].append("multiple_h1")

        # ── H2 ────────────────────────────────────────────────────────────
        result["h2_count"] = len(soup.find_all("h2"))

        # ── Word count (visible text only) ────────────────────────────────
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        body_text = soup.get_text(separator=" ")
        words = [w for w in body_text.split() if w]
        result["word_count"] = len(words)
        if len(words) < 300:
            result["issues"].append("thin_content")

        # ── Images ────────────────────────────────────────────────────────
        imgs = soup.find_all("img")
        result["images_total"] = len(imgs)
        result["images_missing_alt"] = sum(
            1 for i in imgs if not (i.get("alt") or "").strip()
        )
        if result["images_missing_alt"] > 0:
            result["issues"].append(f"images_missing_alt_{result['images_missing_alt']}")

        # ── Links ─────────────────────────────────────────────────────────
        internal_links: list[str] = []
        external_count = 0
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            abs_href = urljoin(url, href)
            parsed = urlparse(abs_href)
            # Skip non-http and files
            if parsed.scheme not in ("http", "https"):
                continue
            ext = "." + abs_href.rsplit(".", 1)[-1].lower().split("?")[0] if "." in abs_href.rsplit("/", 1)[-1] else ""
            if ext in _IGNORED_EXTENSIONS:
                continue
            if parsed.netloc.lower().endswith(base_domain) or parsed.netloc.lower() == base_domain:
                internal_links.append(abs_href)
            else:
                external_count += 1

        result["internal_links"] = len(internal_links)
        result["external_links"] = external_count
        result["_outlinks_internal"] = list(set(internal_links))

    except httpx.TimeoutException:
        result["status_code"] = 0
        result["issues"].append("timeout")
        result["response_time_ms"] = int((time.monotonic() - t0) * 1000)
    except Exception as exc:
        result["status_code"] = 0
        result["issues"].append("crawl_error")
        result["error_detail"] = str(exc)[:200]

    return result
