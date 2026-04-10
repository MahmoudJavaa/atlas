"""Execution Layer — publishes content to WordPress and Shopify."""
from __future__ import annotations

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import httpx
from backend.config import settings
from backend.models.content import ContentPage


class CMSPublisher:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def publish_page(self, content_page_id: int, dry_run: bool = True) -> dict:
        """Publish a ContentPage to the configured CMS. dry_run=True by default."""
        result = await self.db.execute(
            select(ContentPage).where(ContentPage.id == content_page_id)
        )
        page = result.scalar_one_or_none()
        if not page:
            return {"error": "ContentPage not found"}

        from backend.models.site import Site
        site_result = await self.db.execute(select(Site).where(Site.id == page.site_id))
        site = site_result.scalar_one_or_none()

        cms_type = site.cms_type if site else "wordpress"
        diff = self._build_diff(page)

        if dry_run:
            return {
                "dry_run": True,
                "cms_type": cms_type,
                "diff": diff,
                "message": "Set dry_run=False to publish.",
            }

        if cms_type == "wordpress":
            return await self._publish_wordpress(page, diff)
        elif cms_type == "shopify":
            return await self._publish_shopify(page, diff)
        else:
            return {"error": f"Unknown CMS type: {cms_type}"}

    def _build_diff(self, page: ContentPage) -> dict:
        """Show what would be changed."""
        return {
            "title": page.title,
            "meta_desc": page.meta_desc,
            "content_preview": (page.content or "")[:300] + "...",
            "schema_keys": list((page.schema_json or {}).keys()),
            "word_count": page.word_count,
        }

    async def _publish_wordpress(self, page: ContentPage, diff: dict) -> dict:
        if not settings.wordpress_url or not settings.wordpress_user:
            return {"error": "WordPress credentials not configured"}

        schema_html = ""
        if page.schema_json:
            schema_html = f'<script type="application/ld+json">{json.dumps(page.schema_json)}</script>'

        post_data = {
            "title": page.title,
            "content": (page.content or "") + schema_html,
            "status": "draft",
            "meta": {
                "_yoast_wpseo_metadesc": page.meta_desc,
                "_rank_math_description": page.meta_desc,
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.wordpress_url.rstrip('/')}/wp-json/wp/v2/posts",
                json=post_data,
                auth=(settings.wordpress_user, settings.wordpress_app_password),
            )

        if resp.status_code in (200, 201):
            data = resp.json()
            cms_post_id = data.get("id")
            page.cms_post_id = cms_post_id
            page.status = "published"
            from datetime import datetime
            page.published_at = datetime.utcnow()
            await self.db.flush()
            return {"success": True, "wp_post_id": cms_post_id, "url": data.get("link")}
        else:
            return {"error": f"WordPress API error {resp.status_code}: {resp.text[:200]}"}

    async def _publish_shopify(self, page: ContentPage, diff: dict) -> dict:
        if not settings.shopify_store or not settings.shopify_access_token:
            return {"error": "Shopify credentials not configured"}

        schema_html = ""
        if page.schema_json:
            schema_html = f'<script type="application/ld+json">{json.dumps(page.schema_json)}</script>'

        page_data = {
            "page": {
                "title": page.title,
                "body_html": (page.content or "") + schema_html,
                "published": True,
            }
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://{settings.shopify_store}/admin/api/2024-01/pages.json",
                json=page_data,
                headers={"X-Shopify-Access-Token": settings.shopify_access_token},
            )

        if resp.status_code in (200, 201):
            data = resp.json().get("page", {})
            page.cms_post_id = data.get("id")
            page.status = "published"
            from datetime import datetime
            page.published_at = datetime.utcnow()
            await self.db.flush()
            return {"success": True, "shopify_page_id": data.get("id"), "handle": data.get("handle")}
        else:
            return {"error": f"Shopify API error {resp.status_code}: {resp.text[:200]}"}
