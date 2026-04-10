from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import get_db

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRequest(BaseModel):
    goal: str
    site_id: int


@router.post("/run")
async def run_agent(data: AgentRequest, db: AsyncSession = Depends(get_db)):
    """Run the Atlas master agent with a high-level goal."""
    from backend.agents.atlas_agent import AtlasAgent
    agent = AtlasAgent(db=db)
    result = await agent.run(goal=data.goal, site_id=data.site_id)
    return result


@router.get("/audit-log/{site_id}")
async def get_audit_log(site_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from backend.models.audit import AuditLog
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.site_id == site_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "module": l.module,
            "action": l.action,
            "status": l.status,
            "created_at": l.created_at,
        }
        for l in logs
    ]
