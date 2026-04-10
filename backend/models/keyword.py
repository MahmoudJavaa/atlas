from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Date, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from backend.database import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    volume: Mapped[int] = mapped_column(Integer, nullable=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=True)  # informational | commercial | transactional | navigational
    cluster: Mapped[str] = mapped_column(String(255), nullable=True)
    position: Mapped[float] = mapped_column(Float, nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    ctr: Mapped[float] = mapped_column(Float, nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site", back_populates="keywords")
