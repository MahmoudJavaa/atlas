from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.database import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cms_type: Mapped[str] = mapped_column(String(50), nullable=True)  # wordpress | shopify | other
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    crawl_results = relationship("CrawlResult", back_populates="site", cascade="all, delete-orphan")
    keywords = relationship("Keyword", back_populates="site", cascade="all, delete-orphan")
    content_pages = relationship("ContentPage", back_populates="site", cascade="all, delete-orphan")
    backlink_opportunities = relationship("BacklinkOpportunity", back_populates="site", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="site", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="site", cascade="all, delete-orphan")
