from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db
from backend.api.routes import sites, technical_seo, keywords, content, analytics, agent
from backend.api.routes import auth, actions, onboarding
from backend.api.routes import quick_audit


async def _ensure_local_admin():
    """Create a default local admin account on first run so the user never
    has to register manually when running Atlas as a desktop app."""
    from sqlalchemy import select
    from backend.database import AsyncSessionLocal
    from backend.models.user import User
    from backend.auth import hash_password

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "admin@atlas.local"))
        if result.scalar_one_or_none() is None:
            admin = User(
                email="admin@atlas.local",
                full_name="Atlas Admin",
                password_hash=hash_password("atlas"),
                plan="pro",
                is_active=True,
            )
            db.add(admin)
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _ensure_local_admin()
    yield


app = FastAPI(
    title="Atlas SEO Agent API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Public — no auth required ─────────────────────────────────────────────────
app.include_router(quick_audit.router)   # Quick Audit (Screaming-Frog style)

# ── Auth ──────────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api")

# ── Authenticated features ────────────────────────────────────────────────────
app.include_router(onboarding.router, prefix="/api")
app.include_router(actions.router, prefix="/api")
app.include_router(sites.router, prefix="/api")
app.include_router(technical_seo.router, prefix="/api")
app.include_router(keywords.router, prefix="/api")
app.include_router(content.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(agent.router, prefix="/api")


@app.get("/health")
async def health():
    from backend.llm import llm_is_available
    return {
        "status": "ok",
        "version": "2.0.0",
        "ai_ready": llm_is_available(),
    }
