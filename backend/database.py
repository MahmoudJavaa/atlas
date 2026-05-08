from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup, then apply any missing column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_columns(conn)


async def _migrate_columns(conn):
    """Idempotent column additions — safe to run on every startup."""
    migrations = [
        # crawl_results columns added in v2
        "ALTER TABLE crawl_results ADD COLUMN IF NOT EXISTS crawl_run_id VARCHAR(64)",
        "ALTER TABLE crawl_results ADD COLUMN IF NOT EXISTS h1_count INTEGER",
        "ALTER TABLE crawl_results ADD COLUMN IF NOT EXISTS response_time_ms INTEGER",
        "ALTER TABLE crawl_results ADD COLUMN IF NOT EXISTS redirect_url VARCHAR(2048)",
        "ALTER TABLE crawl_results ADD COLUMN IF NOT EXISTS page_depth INTEGER DEFAULT 0",
    ]
    for sql in migrations:
        try:
            await conn.execute(__import__("sqlalchemy").text(sql))
        except Exception:
            pass  # column already exists or table not yet created
