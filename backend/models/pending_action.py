from sqlalchemy import String, DateTime, func, Text, Integer, SmallInteger, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from backend.database import Base


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Action details
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Types: publish_content | update_meta | add_internal_links | fix_redirect
    #        update_title | create_local_page | update_schema | fix_canonical

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI rationale
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # full data to execute
    diff: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {before, after} for display

    # Status machine: pending -> approved -> executing -> executed | failed
    #                 pending -> rejected
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)  # 1 urgent → 10 low

    source_module: Mapped[str] = mapped_column(String(100), nullable=False, default="atlas_agent")
    content_page_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("content_pages.id", ondelete="SET NULL"), nullable=True)

    # Review
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Execution
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    site = relationship("Site", back_populates="pending_actions")
    user = relationship("User", back_populates="pending_actions", foreign_keys="PendingAction.user_id")
