from sqlalchemy import String, DateTime, func, Text, Integer, SmallInteger, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from backend.database import Base


class OnboardingAnalysis(Base):
    __tablename__ = "onboarding_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)

    # Status: queued | crawling | keyword_research | competitor_analysis | planning | complete | failed
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)  # 0–100
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    steps_completed: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    final_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actions_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship
    site = relationship("Site", back_populates="onboarding_analyses")

    @property
    def analysis_id(self) -> int:
        """Alias for id — used by StatusResponse Pydantic model."""
        return self.id
