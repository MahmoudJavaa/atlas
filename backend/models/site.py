from sqlalchemy import String, DateTime, func, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from backend.database import Base


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (
        # Each user can only add the same URL once, but different users can share a URL
        UniqueConstraint("url", "user_id", name="uq_sites_url_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cms_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # wordpress | shopify | other

    # Owner — nullable for backwards compat with pre-auth sites
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    # CMS credentials (per-site, not global env)
    cms_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    cms_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cms_credential: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)  # stored as-is for now

    # Onboarding status
    onboarding_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="sites")
    crawl_results = relationship("CrawlResult", back_populates="site", cascade="all, delete-orphan")
    keywords = relationship("Keyword", back_populates="site", cascade="all, delete-orphan")
    content_pages = relationship("ContentPage", back_populates="site", cascade="all, delete-orphan")
    backlink_opportunities = relationship("BacklinkOpportunity", back_populates="site", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="site", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="site", cascade="all, delete-orphan")
    pending_actions = relationship("PendingAction", back_populates="site", cascade="all, delete-orphan")
    onboarding_analyses = relationship("OnboardingAnalysis", back_populates="site", cascade="all, delete-orphan")
