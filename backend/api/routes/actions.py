"""Approval queue — list, approve, reject pending actions."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.database import get_db
from backend.models.pending_action import PendingAction
from backend.models.user import User
from backend.auth import get_current_user

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionResponse(BaseModel):
    id: int
    site_id: int
    action_type: str
    title: str
    description: Optional[str]
    payload: dict
    diff: Optional[dict]
    status: str
    priority: int
    source_module: str
    review_note: Optional[str]
    executed_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewRequest(BaseModel):
    note: Optional[str] = None


class BulkReviewRequest(BaseModel):
    action_ids: list[int]
    note: Optional[str] = None


@router.get("/{site_id}", response_model=list[ActionResponse])
async def list_actions(
    site_id: int,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(PendingAction).where(PendingAction.site_id == site_id)
    if status:
        stmt = stmt.where(PendingAction.status == status)
    stmt = stmt.order_by(PendingAction.priority, PendingAction.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/count/pending")
async def count_pending(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns total pending actions count across all user's sites (for sidebar badge)."""
    result = await db.execute(
        select(func.count(PendingAction.id))
        .where(PendingAction.user_id == current_user.id)
        .where(PendingAction.status == "pending")
    )
    count = result.scalar_one()
    return {"count": count}


@router.get("/detail/{action_id}", response_model=ActionResponse)
async def get_action(
    action_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.patch("/{action_id}/approve", response_model=ActionResponse)
async def approve_action(
    action_id: int,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        raise HTTPException(status_code=400, detail=f"Action is already {action.status}")

    action.status = "approved"
    action.reviewed_by = current_user.id
    action.reviewed_at = datetime.now(timezone.utc)
    action.review_note = body.note

    # For Phase 1: mark as executed immediately (no CMS yet)
    # In Phase 2 this would dispatch a Celery task
    action.status = "executed"
    action.executed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(action)
    return action


@router.patch("/{action_id}/reject", response_model=ActionResponse)
async def reject_action(
    action_id: int,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        raise HTTPException(status_code=400, detail=f"Action is already {action.status}")

    action.status = "rejected"
    action.reviewed_by = current_user.id
    action.reviewed_at = datetime.now(timezone.utc)
    action.review_note = body.note

    await db.flush()
    await db.refresh(action)
    return action


@router.post("/bulk-approve")
async def bulk_approve(
    body: BulkReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approved = 0
    for action_id in body.action_ids:
        result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
        action = result.scalar_one_or_none()
        if action and action.status == "pending":
            action.status = "executed"
            action.reviewed_by = current_user.id
            action.reviewed_at = datetime.now(timezone.utc)
            action.review_note = body.note
            action.executed_at = datetime.now(timezone.utc)
            approved += 1
    await db.flush()
    return {"approved": approved, "total": len(body.action_ids)}


@router.post("/bulk-reject")
async def bulk_reject(
    body: BulkReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rejected = 0
    for action_id in body.action_ids:
        result = await db.execute(select(PendingAction).where(PendingAction.id == action_id))
        action = result.scalar_one_or_none()
        if action and action.status == "pending":
            action.status = "rejected"
            action.reviewed_by = current_user.id
            action.reviewed_at = datetime.now(timezone.utc)
            action.review_note = body.note
            rejected += 1
    await db.flush()
    return {"rejected": rejected, "total": len(body.action_ids)}
