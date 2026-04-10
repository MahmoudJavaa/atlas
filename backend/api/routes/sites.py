from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database import get_db
from backend.models.site import Site

router = APIRouter(prefix="/sites", tags=["sites"])


class SiteCreate(BaseModel):
    url: str
    name: str
    cms_type: str | None = None


class SiteResponse(BaseModel):
    id: int
    url: str
    name: str
    cms_type: str | None

    class Config:
        from_attributes = True


@router.get("/", response_model=list[SiteResponse])
async def list_sites(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Site))
    return result.scalars().all()


@router.post("/", response_model=SiteResponse)
async def create_site(data: SiteCreate, db: AsyncSession = Depends(get_db)):
    site = Site(url=data.url, name=data.name, cms_type=data.cms_type)
    db.add(site)
    await db.flush()
    await db.refresh(site)
    return site


@router.delete("/{site_id}")
async def delete_site(site_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    await db.delete(site)
    return {"deleted": True}
