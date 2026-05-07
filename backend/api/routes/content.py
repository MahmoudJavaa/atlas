from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.models.content import ContentPage
from backend.auth import get_current_user

router = APIRouter(prefix="/content", tags=["content"], dependencies=[Depends(get_current_user)])


class GenerateRequest(BaseModel):
    site_id: int
    keyword: str
    intent: str
    funnel_stage: str
    page_type: str
    location: Optional[str] = None


class LocalPageRequest(BaseModel):
    site_id: int
    service: str
    location: str
    business_name: str


class PublishRequest(BaseModel):
    content_page_id: int
    dry_run: bool = True


@router.post("/generate")
async def generate_content(data: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate content synchronously."""
    from backend.modules.content_engine.generator import ContentGenerator
    generator = ContentGenerator(db=db)
    result = await generator.run(
        site_id=data.site_id,
        keyword=data.keyword,
        intent=data.intent,
        funnel_stage=data.funnel_stage,
        page_type=data.page_type,
        location=data.location,
    )
    return result


@router.post("/local-page")
async def generate_local_page(data: LocalPageRequest, db: AsyncSession = Depends(get_db)):
    """Generate a local SEO page with doorway check."""
    from backend.modules.local_seo.page_generator import LocalSEOPageGenerator
    generator = LocalSEOPageGenerator(db=db)
    result = await generator.run(
        service=data.service,
        location=data.location,
        business_name=data.business_name,
        site_id=data.site_id,
    )
    return result


@router.post("/publish")
async def publish_content(data: PublishRequest, db: AsyncSession = Depends(get_db)):
    """Publish a content page to the CMS."""
    from backend.modules.execution.publisher import CMSPublisher
    publisher = CMSPublisher(db=db)
    result = await publisher.publish_page(
        content_page_id=data.content_page_id,
        dry_run=data.dry_run,
    )
    return result


@router.get("/{site_id}")
async def list_content(site_id: int, status: str = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(ContentPage).where(ContentPage.site_id == site_id)
    if status:
        stmt = stmt.where(ContentPage.status == status)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    pages = result.scalars().all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "keyword": p.keyword,
            "status": p.status,
            "page_type": p.page_type,
            "word_count": p.word_count,
            "published_at": p.published_at,
            "created_at": p.created_at,
        }
        for p in pages
    ]


@router.get("/page/{content_page_id}")
async def get_content_page(content_page_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContentPage).where(ContentPage.id == content_page_id))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Content page not found")
    return {
        "id": page.id,
        "title": page.title,
        "meta_desc": page.meta_desc,
        "content": page.content,
        "schema_json": page.schema_json,
        "keyword": page.keyword,
        "status": page.status,
        "word_count": page.word_count,
    }
