from sqlalchemy import String, Float, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.database import Base


class BacklinkOpportunity(Base):
    __tablename__ = "backlink_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(512), nullable=True)
    anchor: Mapped[str] = mapped_column(String(512), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0–1 relevance score
    opportunity_type: Mapped[str] = mapped_column(String(50), nullable=True)  # competitor_backlink | unlinked_mention
    outreach_email: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="new")  # new | contacted | won | lost
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site", back_populates="backlink_opportunities")
