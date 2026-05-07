from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.database import Base


class CrawlResult(Base):
    __tablename__ = "crawl_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    crawl_run_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)  # groups one crawl run
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=True)
    meta_desc: Mapped[str] = mapped_column(Text, nullable=True)
    canonical: Mapped[str] = mapped_column(String(2048), nullable=True)
    indexable: Mapped[bool] = mapped_column(Boolean, default=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=True)
    h1_count: Mapped[int] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    redirect_url: Mapped[str] = mapped_column(String(2048), nullable=True)
    page_depth: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    issues: Mapped[dict] = mapped_column(JSON, default=dict)  # {critical: [], warning: [], info: []}
    severity_score: Mapped[int] = mapped_column(Integer, default=0)  # 0–100
    crawled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site", back_populates="crawl_results")
