"""Onboarding — domain entry point, auto-analysis, progress polling."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db, AsyncSessionLocal
from backend.models.site import Site
from backend.models.onboarding import OnboardingAnalysis
from backend.models.pending_action import PendingAction
from backend.models.user import User
from backend.auth import get_current_user

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class StartRequest(BaseModel):
    domain: str
    name: str
    cms_type: Optional[str] = "other"


class StatusResponse(BaseModel):
    analysis_id: int
    site_id: int
    status: str
    progress: int
    current_step: Optional[str]
    steps_completed: list
    actions_created: int
    final_report: Optional[str]
    error: Optional[str]

    class Config:
        from_attributes = True


@router.post("/start")
async def start_onboarding(
    data: StartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Normalize domain
    domain = data.domain.strip().rstrip("/")
    if not domain.startswith("http"):
        domain = f"https://{domain}"

    # Check if site already exists for this user
    result = await db.execute(
        select(Site).where(Site.url == domain).where(Site.user_id == current_user.id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # If already exists, just create a new analysis
        site = existing
    else:
        # Create new site
        site = Site(
            url=domain,
            name=data.name,
            cms_type=data.cms_type,
            user_id=current_user.id,
            onboarding_status="pending",
        )
        db.add(site)
        await db.flush()
        await db.refresh(site)

    # Create analysis record
    analysis = OnboardingAnalysis(
        site_id=site.id,
        status="queued",
        progress=0,
        steps_completed=[],
    )
    db.add(analysis)
    await db.flush()
    await db.refresh(analysis)

    # Commit before background task starts (so it can see the records)
    await db.commit()

    # Kick off background analysis
    background_tasks.add_task(run_onboarding_analysis, analysis.id, site.id, current_user.id)

    return {
        "site_id": site.id,
        "analysis_id": analysis.id,
        "status": "queued",
        "message": "Analysis started. Poll /api/onboarding/{analysis_id}/status for progress.",
    }


@router.get("/{analysis_id}/status", response_model=StatusResponse)
async def get_status(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(OnboardingAnalysis).where(OnboardingAnalysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


async def _update_progress(analysis_id: int, progress: int, status: str, step: str):
    """Update onboarding analysis progress in a fresh DB session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(OnboardingAnalysis).where(OnboardingAnalysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
        if analysis:
            analysis.progress = progress
            analysis.status = status
            analysis.current_step = step
            if step and step not in analysis.steps_completed:
                analysis.steps_completed = analysis.steps_completed + [step]
            await db.commit()


async def run_onboarding_analysis(analysis_id: int, site_id: int, user_id: int):
    """
    Full onboarding pipeline — runs in background.
    Steps: crawl → keyword extract → GEO score → competitor → content plan → generate actions
    """
    from backend.modules.technical_seo.crawler import TechnicalSEOCrawler
    from backend.modules.keyword_intel.classifier import KeywordClassifier
    from backend.modules.geo_engine.optimizer import GEOOptimizer
    from backend.modules.competitor_intel.analyzer import CompetitorAnalyzer
    from backend.llm import get_llm
    import httpx, json

    async with AsyncSessionLocal() as db:
        try:
            # ── Step 1: Crawl ────────────────────────────────────────────────
            await _update_progress(analysis_id, 5, "crawling", "crawling")

            result = await db.execute(select(Site).where(Site.id == site_id))
            site = result.scalar_one()

            crawler = TechnicalSEOCrawler(db=db)
            crawl_pages = await crawler.run(
                site_id=site_id,
                start_url=site.url,
                max_pages=30,
            )
            # Normalise: crawler returns list[dict]; wrap into the dict shape the pipeline expects
            crawl_result = {
                "pages_crawled": len(crawl_pages),
                "results": crawl_pages,
            }

            pages_crawled = crawl_result["pages_crawled"]
            await _update_progress(analysis_id, 25, "keyword_research", "site_crawl")

            # ── Step 2: Extract keywords from crawled page titles ─────────────
            seed_keywords = _extract_keywords_from_crawl(crawl_result)

            classifier = KeywordClassifier(db=db)
            try:
                kw_result = await asyncio.wait_for(
                    classifier.run(site_id=site_id, seed_keywords=seed_keywords[:20]),
                    timeout=120.0,
                )
            except Exception:
                kw_result = {"keywords": [], "clusters": {}, "total": 0}
            await _update_progress(analysis_id, 45, "geo_scoring", "keyword_research")

            # ── Step 3: GEO score the homepage ────────────────────────────────
            geo_score_data = None
            try:
                page_content = await _fetch_page_text(site.url)
                if page_content:
                    optimizer = GEOOptimizer(db=db)
                    geo_result = await asyncio.wait_for(
                        optimizer.run(url=site.url, content=page_content, site_id=site_id),
                        timeout=120.0,
                    )
                    geo_score_data = geo_result
            except Exception:
                pass

            await _update_progress(analysis_id, 60, "competitor_analysis", "geo_scoring")

            # ── Step 4: Competitor discovery ──────────────────────────────────
            competitor_data = None
            try:
                analyzer = CompetitorAnalyzer(db=db)
                top_kw = seed_keywords[0] if seed_keywords else site.name
                competitors = await _discover_competitors(top_kw, site.url)
                if competitors:
                    competitor_data = await asyncio.wait_for(
                        analyzer.run(site_id=site_id, competitor_domains=competitors[:2], our_domain=site.url),
                        timeout=120.0,
                    )
            except Exception:
                pass

            await _update_progress(analysis_id, 78, "planning", "competitor_analysis")

            # ── Step 5: Build action plan with LLM (optional — skip if Ollama not ready) ──
            from backend.llm import get_llm, ollama_is_available
            llm = get_llm() if ollama_is_available() else None
            plan = await _build_action_plan(
                llm=llm,
                site_url=site.url,
                site_name=site.name,
                crawl_result=crawl_result,
                keywords=kw_result,
                geo_score=geo_score_data,
                competitor=competitor_data,
            )
            await _update_progress(analysis_id, 90, "creating_actions", "planning")

            # ── Step 6: Create PendingAction records ─────────────────────────
            actions_created = 0
            for action_data in plan.get("actions", []):
                action = PendingAction(
                    site_id=site_id,
                    user_id=user_id,
                    action_type=action_data.get("type", "general"),
                    title=action_data.get("title", "Untitled action"),
                    description=action_data.get("rationale", ""),
                    payload=action_data.get("payload", {}),
                    diff=action_data.get("diff"),
                    priority=action_data.get("priority", 5),
                    source_module="onboarding",
                    status="pending",
                )
                db.add(action)
                actions_created += 1

            await db.flush()

            # Finalize
            result2 = await db.execute(select(OnboardingAnalysis).where(OnboardingAnalysis.id == analysis_id))
            analysis = result2.scalar_one()
            analysis.status = "complete"
            analysis.progress = 100
            analysis.current_step = "complete"
            analysis.actions_created = actions_created
            analysis.completed_at = datetime.now(timezone.utc)
            analysis.final_report = plan.get("summary", "Analysis complete.")
            analysis.steps_completed = ["site_crawl", "keyword_research", "geo_scoring", "competitor_analysis", "planning", "complete"]

            # Update site onboarding status
            site.onboarding_status = "complete"
            await db.commit()

        except Exception as exc:
            async with AsyncSessionLocal() as db2:
                result = await db2.execute(select(OnboardingAnalysis).where(OnboardingAnalysis.id == analysis_id))
                analysis = result.scalar_one_or_none()
                if analysis:
                    analysis.status = "failed"
                    analysis.error = str(exc)
                    await db2.commit()


def _flatten_issues(issues_field) -> list[str]:
    """Normalise issues — crawler returns dict {critical,warning,info} or a flat list."""
    if isinstance(issues_field, dict):
        flat = []
        for v in issues_field.values():
            if isinstance(v, list):
                flat.extend(str(i) for i in v)
        return flat
    if isinstance(issues_field, list):
        return [str(i) for i in issues_field]
    return []


def _extract_keywords_from_crawl(crawl_result: dict) -> list[str]:
    """Pull seed keywords from crawled page titles and meta descriptions."""
    import re
    keywords = set()
    pages = crawl_result.get("results", [])
    for page in pages:
        title = page.get("title", "")
        meta = page.get("meta_desc", "")
        for text in [title, meta]:
            if text:
                # Simple tokenization — remove stop words, keep 2+ word phrases
                words = re.sub(r"[^\w\s-]", " ", text.lower()).split()
                stop = {"the","a","an","and","or","for","in","on","at","to","of","is","it",
                        "this","that","we","you","your","our","are","be","with","from","by","|","-"}
                clean = [w for w in words if w not in stop and len(w) > 2]
                if clean:
                    keywords.add(" ".join(clean[:4]))
    return list(keywords)[:25]


async def _fetch_page_text(url: str) -> str:
    """Fetch homepage text for GEO scoring."""
    import httpx
    from bs4 import BeautifulSoup
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AtlasBot/1.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove scripts and styles
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)[:5000]
    except Exception:
        return ""


async def _discover_competitors(keyword: str, our_url: str) -> list[str]:
    """Use SerpAPI to find competitors for the top keyword."""
    from backend.config import settings
    import httpx
    if not settings.serpapi_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://serpapi.com/search",
                params={"q": keyword, "api_key": settings.serpapi_key, "engine": "google", "num": 10},
            )
            data = resp.json()
            our_domain = our_url.replace("https://", "").replace("http://", "").split("/")[0]
            competitors = []
            for r in data.get("organic_results", []):
                link = r.get("link", "")
                domain = link.replace("https://", "").replace("http://", "").split("/")[0]
                if domain and domain != our_domain and domain not in competitors:
                    competitors.append(domain)
            return competitors[:3]
    except Exception:
        return []


async def _build_action_plan(
    llm,
    site_url: str,
    site_name: str,
    crawl_result: dict,
    keywords: dict,
    geo_score: dict | None,
    competitor: dict | None,
) -> dict:
    """Produce a prioritized action plan. Uses LLM if available, falls back to rule-based."""
    import json

    # Rule-based fallback when Ollama isn't ready yet
    if llm is None:
        return _rule_based_plan(site_url, site_name, crawl_result, keywords)

    issues_summary = []
    for page in crawl_result.get("results", [])[:10]:
        flat = _flatten_issues(page.get("issues", []))
        if flat:
            issues_summary.append({"url": page.get("url"), "issues": flat[:3]})

    kw_list = [
        {"keyword": k.get("keyword"), "intent": k.get("intent")}
        for k in (keywords.get("keywords") or [])[:10]
    ]

    geo_summary = ""
    if geo_score:
        geo_summary = f"GEO Score: {geo_score.get('score', 'N/A')}/100. Issues: {', '.join((geo_score.get('issues') or [])[:3])}"

    competitor_gaps = []
    if competitor and competitor.get("analysis"):
        competitor_gaps = (competitor["analysis"].get("content_gaps") or [])[:5]

    prompt = f"""You are an expert SEO strategist. Based on the audit of {site_name} ({site_url}), create a prioritized action plan.

SITE AUDIT DATA:
- Pages crawled: {crawl_result.get('pages_crawled', 0)}
- Technical issues found: {json.dumps(issues_summary[:5], indent=2)}
- Keywords identified: {json.dumps(kw_list, indent=2)}
- GEO optimization: {geo_summary or 'Not scored'}
- Competitor content gaps: {json.dumps(competitor_gaps, indent=2)}

Generate a JSON action plan with:
1. A brief executive summary (2-3 sentences)
2. A list of 8-15 specific actions the site owner should take

Each action must have:
- type: one of [publish_content, update_meta, add_internal_links, fix_technical, create_local_page, update_schema, improve_geo]
- title: short (under 80 chars), specific action title
- rationale: 1-2 sentence explanation of WHY this matters
- priority: 1 (urgent) to 5 (nice to have)
- payload: relevant data object (e.g. for publish_content: {{keyword, suggested_title, word_count_target}})
- estimated_impact: low | medium | high

Return ONLY valid JSON:
{{
  "summary": "...",
  "actions": [
    {{
      "type": "...",
      "title": "...",
      "rationale": "...",
      "priority": 1,
      "payload": {{}},
      "estimated_impact": "high"
    }}
  ]
}}"""

    try:
        result = llm.generate_json(prompt, max_tokens=4000)
        return result
    except Exception:
        return _rule_based_plan(site_url, site_name, crawl_result, keywords)


def _rule_based_plan(site_url: str, site_name: str, crawl_result: dict, keywords: dict) -> dict:
    """Generate an action plan without AI, based purely on crawl data."""
    actions = []
    pages = crawl_result.get("results", [])
    pages_crawled = crawl_result.get("pages_crawled", 0)

    for page in pages[:20]:
        issues = _flatten_issues(page.get("issues", []))
        url = page.get("url", site_url)
        for issue in issues:
            if "missing_title" in issue or issue == "no_title":
                actions.append({"type": "update_meta", "title": f"Add missing page title: {url}", "rationale": "Missing titles hurt rankings.", "priority": 1, "payload": {"url": url}, "estimated_impact": "high"})
            elif "missing_h1" in issue or issue == "no_h1":
                actions.append({"type": "update_meta", "title": f"Add H1 heading: {url}", "rationale": "H1 is a primary ranking signal.", "priority": 2, "payload": {"url": url}, "estimated_impact": "high"})
            elif "missing_meta" in issue or "no_meta" in issue:
                actions.append({"type": "update_meta", "title": f"Write meta description: {url}", "rationale": "Meta descriptions improve CTR.", "priority": 2, "payload": {"url": url}, "estimated_impact": "medium"})
            elif any(x in issue for x in ("broken", "4xx", "5xx", "404", "500")):
                actions.append({"type": "fix_technical", "title": f"Fix broken link/error: {url}", "rationale": "Broken pages hurt crawlability.", "priority": 1, "payload": {"url": url, "issue": issue}, "estimated_impact": "high"})
            elif "thin_content" in issue or "low_word" in issue:
                actions.append({"type": "publish_content", "title": f"Expand thin content: {url}", "rationale": "Pages with low word count rank poorly.", "priority": 3, "payload": {"url": url}, "estimated_impact": "medium"})
        if len(actions) >= 15:
            break

    # Add keyword-based suggestions
    for kw in (keywords.get("keywords") or [])[:3]:
        kw_text = kw.get("keyword") if isinstance(kw, dict) else str(kw)
        if kw_text:
            actions.append({"type": "publish_content", "title": f"Create content for: {kw_text}", "rationale": "Targeting this keyword can drive organic traffic.", "priority": 3, "payload": {"keyword": kw_text, "site_url": site_url}, "estimated_impact": "medium"})

    if not actions:
        actions.append({"type": "improve_geo", "title": "Add FAQ schema to homepage", "rationale": "FAQ schema helps AI search engines cite your site.", "priority": 2, "payload": {"url": site_url}, "estimated_impact": "medium"})

    return {
        "summary": f"Audit of {site_name} complete. {pages_crawled} pages analyzed. {len(actions)} action items identified.",
        "actions": actions[:15],
    }
