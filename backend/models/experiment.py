from sqlalchemy import String, DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)  # title_change | content_update | schema_add
    hypothesis: Mapped[str] = mapped_column(Text, nullable=True)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=True)
    baseline_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    result_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[str] = mapped_column(String(50), nullable=True)  # positive | neutral | negative
    impact_score: Mapped[float] = mapped_column(default=0.0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    concluded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    site = relationship("Site", back_populates="experiments")
