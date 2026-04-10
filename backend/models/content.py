from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.database import Base


class ContentPage(Base):
    __tablename__ = "content_pages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=True)
    meta_desc: Mapped[str] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    keyword: Mapped[str] = mapped_column(String(512), nullable=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=True)
    funnel_stage: Mapped[str] = mapped_column(String(50), nullable=True)  # TOFU | MOFU | BOFU
    page_type: Mapped[str] = mapped_column(String(50), nullable=True)  # landing | blog | product | local
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft | published | archived
    cms_post_id: Mapped[int] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site", back_populates="content_pages")
