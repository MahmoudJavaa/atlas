"""Local SEO Engine — generates CMS-ready local service pages."""
from __future__ import annotations

import json
import re
from sqlalchemy.ext.asyncio import AsyncSession

import anthropic
from backend.config import settings


LOCAL_PAGE_PROMPT = """You are an expert local SEO content writer. Generate a complete local service page.

Service: {service}
Location: {location}
Business name: {business_name}
Tone: professional, trustworthy, locally specific

IMPORTANT: This must NOT be a doorway page. It must include genuine locally-specific content angles
(local landmarks, local context, specific service relevance to the area, local customer pain points).

Generate a JSON object with:
{{
  "title": "<meta title max 60 chars, include service + location>",
  "meta_desc": "<meta description 140-160 chars>",
  "post_content": "<full HTML page content with these sections: Hero, Why Choose Us, How It Works, Services, Coverage Area, Reviews, FAQ, CTA>",
  "word_count": <integer>,
  "local_specificity_notes": ["note about how content is locally specific"],
  "schema": {{
    "faq_schema": {{...FAQPage JSON-LD...}},
    "local_business_schema": {{
      "@context": "https://schema.org",
      "@type": "LocalBusiness",
      "name": "{business_name}",
      "areaServed": {{
        "@type": "GeoCircle",
        "geoMidpoint": {{"@type": "GeoCoordinates", "latitude": 0, "longitude": 0}},
        "geoRadius": "10000"
      }}
    }}
  }},
  "doorway_score": <0-100, 100=clearly not doorway, 0=likely doorway>,
  "doorway_check_notes": "explanation"
}}

Only return valid JSON. No markdown.
"""

DOORWAY_CHECK_PROMPT = """Rate this content on a scale of 0-100 for local page quality.
100 = excellent, genuinely locally specific, not a doorway page.
0 = pure template/doorway, no genuine local value.

Content preview:
{content_preview}

Return JSON: {{"score": <int>, "reasoning": "..."}}
"""


class LocalSEOPageGenerator:
    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def run(
        self,
        service: str,
        location: str,
        business_name: str,
        site_id: int | None = None,
    ) -> dict:
        """Generate a local SEO page with doorway check."""
        result = await self._generate_page(service, location, business_name)

        # Enforce doorway check — must score >= 60
        doorway_score = result.get("doorway_score", 0)
        if doorway_score < 60:
            doorway_check = await self._doorway_check(result.get("post_content", ""))
            result["doorway_check"] = doorway_check
            if doorway_check.get("score", 0) < 60:
                result["publish_blocked"] = True
                result["publish_blocked_reason"] = "Content failed doorway page check. Improve local specificity before publishing."
                return result

        result["publish_blocked"] = False

        # Persist if site_id provided
        if site_id and self.db:
            from backend.models.content import ContentPage
            page = ContentPage(
                site_id=site_id,
                title=result.get("title", ""),
                meta_desc=result.get("meta_desc", ""),
                content=result.get("post_content", ""),
                schema_json=result.get("schema", {}),
                keyword=f"{service} {location}",
                page_type="local",
                word_count=result.get("word_count", 0),
                status="draft",
            )
            self.db.add(page)
            await self.db.flush()
            await self.db.refresh(page)
            result["content_page_id"] = page.id

        return result

    async def _generate_page(self, service: str, location: str, business_name: str) -> dict:
        prompt = LOCAL_PAGE_PROMPT.format(
            service=service,
            location=location,
            business_name=business_name,
        )
        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=8096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "title": f"{service} in {location}",
                "meta_desc": f"Professional {service} services in {location}. Call {business_name} today.",
                "post_content": f"<h1>{service} in {location}</h1><p>Content generation error. Please retry.</p>",
                "word_count": 0,
                "schema": {},
                "doorway_score": 0,
            }

    async def _doorway_check(self, content: str) -> dict:
        prompt = DOORWAY_CHECK_PROMPT.format(content_preview=content[:2000])
        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"score": 50, "reasoning": "Could not parse doorway check result."}
