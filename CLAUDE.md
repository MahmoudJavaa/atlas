# Atlas SEO Agent — CLAUDE.md

Comprehensive guide for AI assistants working in this codebase.

## Project Overview

Atlas is a full-stack autonomous SEO platform. It crawls websites, researches keywords, generates content, and publishes changes to WordPress/Shopify — all driven by an LLM agent. The stack is:

- **Backend:** Python 3.12, FastAPI, Celery, PostgreSQL, Redis
- **Frontend:** TypeScript, Next.js 14 (App Router), Tailwind CSS
- **LLM:** Groq cloud API (primary) or Ollama local Docker (fallback)
- **Deployment:** Docker Compose (local/desktop), Railway (cloud)

---

## Directory Structure

```
atlas/
├── backend/              # FastAPI + Celery Python application
│   ├── agents/           # Atlas autonomous agent (function-calling loop)
│   ├── api/routes/       # FastAPI route handlers (one file per domain)
│   ├── models/           # SQLAlchemy ORM models
│   ├── modules/          # Feature modules (11 SEO modules)
│   ├── tasks/            # Celery task definitions
│   ├── config.py         # Pydantic Settings (all env vars)
│   ├── database.py       # Async SQLAlchemy engine + session
│   ├── llm.py            # Unified LLM client (Groq / Ollama)
│   ├── auth.py           # JWT helpers + password hashing
│   ├── celery_app.py     # Celery app + queue routing
│   ├── main.py           # FastAPI app factory + middleware
│   ├── start.py          # Production entrypoint (reads PORT env)
│   ├── requirements.txt  # Python dependencies
│   ├── pytest.ini        # asyncio_mode = auto, testpaths = ../tests
│   └── Dockerfile        # Python 3.12 + Playwright browsers
├── frontend/             # Next.js dashboard
│   ├── app/              # App Router pages and API proxy
│   ├── components/       # React components (layout, auth, ui)
│   ├── contexts/         # AuthContext (JWT state)
│   ├── lib/              # api.ts, auth.ts utilities
│   ├── package.json
│   └── Dockerfile        # Node 20 Alpine multi-stage build
├── tests/                # pytest test suite (one file per module)
├── installer/            # Windows desktop installer (Inno Setup)
├── ollama/               # Ollama container entrypoint script
├── docker-compose.yml    # Full 7-service stack
├── railway.toml          # Railway.app deployment config
└── .env.example          # Environment variable template
```

### Backend modules (`backend/modules/`)

| Module | Purpose |
|---|---|
| `technical_seo/` | Playwright crawler + 20+ audit checks (H1, meta, speed, etc.) |
| `keyword_intel/` | Intent classifier + cluster builder (English + Arabic) |
| `geo_engine/` | AI answerability scoring for geographic queries |
| `content_engine/` | LLM-powered SEO content generation |
| `competitor_intel/` | SERP gap analysis via SerpAPI + LLM |
| `internal_linking/` | Silo architecture + orphan page detector |
| `local_seo/` | Location-based page generator with doorway-page check |
| `backlink_ai/` | Opportunity finder + email template generation |
| `analytics/` | Google Search Console + GA4 connector (OAuth2) |
| `execution/` | WordPress + Shopify automated publisher |
| `learning_loop/` | Weekly performance evaluator + optimizer |

---

## Development Setup

### Fastest path — Docker Compose

```bash
cp .env.example .env
# Add GROQ_API_KEY to .env (or leave blank to use Ollama fallback)
docker compose up --build
```

Services:
- API: http://localhost:8000 (auto-reloads on backend/ changes)
- Frontend: http://localhost:3000
- Ollama: http://localhost:11434 (downloads llama3.2:3b on first run, takes ~15 min)

A default admin account is created automatically on first run:
- Email: `admin@atlas.local`
- Password: `atlas`

### Local backend (without Docker)

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
# Requires a running PostgreSQL and Redis (or override DATABASE_URL/REDIS_URL)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Local frontend (without Docker)

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## Running Tests

```bash
# From the repo root
pytest tests/ -v
```

Tests use `pytest-asyncio` with `asyncio_mode = auto` — all async test functions work without any decorator. Tests mock external services (LLM, SerpAPI, etc.) — they do not require live credentials.

Test files mirror module names: `tests/test_<module>.py`.

---

## Environment Variables

All settings live in `backend/config.py` as a Pydantic `Settings` class. The `.env` file at the repo root is loaded automatically.

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Recommended | Groq cloud LLM (free tier, 14,400 req/day). Omit to use Ollama. |
| `GROQ_MODEL` | No | Default: `llama-3.3-70b-versatile` |
| `DATABASE_URL` | Yes | PostgreSQL connection string (async: `postgresql+asyncpg://...`) |
| `REDIS_URL` | Yes | Redis connection string |
| `OLLAMA_URL` | No | Default: `http://ollama:11434` |
| `SECRET_KEY` | Yes (prod) | JWT signing secret — **must be changed in production** |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins. Default: `http://localhost:3000` |
| `SERPAPI_KEY` | Optional | SERP scraping for competitor intel |
| `SCRAPINGBEE_KEY` | Optional | Web scraping fallback |
| `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD` | Optional | Real keyword volume/difficulty data |
| `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` | Optional | GSC + GA4 OAuth integration |
| `WORDPRESS_URL` + `WORDPRESS_USER` + `WORDPRESS_APP_PASSWORD` | Optional | WordPress publisher |
| `SHOPIFY_STORE` + `SHOPIFY_ACCESS_TOKEN` | Optional | Shopify publisher |
| `DEBUG` | No | Default: `false` |

---

## Key Conventions

### Python (backend)

- **Async-first.** All database access, HTTP calls, and FastAPI route handlers use `async/await`. Use `asyncio.to_thread()` to wrap blocking calls (e.g. `httpx.Client`, Playwright).
- **Dependency injection for DB sessions.** Routes receive `db: AsyncSession = Depends(get_db)`.
- **Pydantic schemas separate from ORM models.** SQLAlchemy models live in `backend/models/`. Request/response schemas are defined inline in route files or in a `schemas.py` sibling.
- **One router per domain.** Each file in `backend/api/routes/` maps to one feature area and is registered in `backend/main.py`.
- **Module interface.** Each module in `backend/modules/` exports its public functions via `__init__.py`. Keep module internals private.
- **LLM calls via `get_llm()`.** Never instantiate `GroqClient` or `LLMClient` directly outside `llm.py`. Always call `get_llm()` to get the active backend.
- **Celery for heavy work.** Crawling, content generation, and analytics pulls are dispatched to workers via tasks in `backend/tasks/`. Synchronous route variants (`/sync` endpoints) run the work inline for simpler testing.
- **Snake_case** for all Python names. Type hints required on function signatures.

### TypeScript (frontend)

- **App Router only.** All pages are under `frontend/app/*/page.tsx`. No Pages Router.
- **API proxy.** The frontend never calls the backend directly from the browser — requests go through `frontend/app/api/[...path]/route.ts`, which proxies to `NEXT_PUBLIC_API_URL`.
- **Auth via context.** JWT is stored and managed in `contexts/AuthContext.tsx`. Use `useAuth()` hook in components.
- **Tailwind dark theme.** Base background is `bg-gray-950`. Stick to the existing dark palette.
- **PascalCase** for React components and their files. `camelCase` for utilities and hooks.
- **TanStack React Query** for server state. Do not use `useEffect` + `useState` combos for data fetching.

### Database

- Timestamps: `DateTime(timezone=True)` with `server_default=func.now()`.
- All user data has a `user_id` FK with `CASCADE` delete.
- Add indexes on columns used in `WHERE` clauses or `JOIN`s.
- Use SQLAlchemy `relationship()` with explicit `cascade="all, delete-orphan"` for owned collections.

### LLM usage

`backend/llm.py` exports two classes and a factory:

```python
from backend.llm import get_llm

llm = get_llm()
text = llm.generate("Your prompt here")
data = llm.generate_json("Return JSON with keys: foo, bar")
data = await llm.generate_json_async("...")   # async variant
```

Priority: Groq (if `GROQ_API_KEY` set) → Ollama (local Docker).

The `generate_json` / `generate_json_async` methods strip markdown fences and extract the first JSON object/array from the response automatically.

---

## API Structure

```
POST /quick-audit            # Public — no auth — Screaming Frog style audit

POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me

GET  /api/sites/
POST /api/sites/
DELETE /api/sites/{id}

POST /api/technical-seo/crawl/sync
GET  /api/technical-seo/results/{site_id}

POST /api/keywords/classify/sync
GET  /api/keywords/{site_id}

POST /api/content/generate
POST /api/content/local-page
POST /api/content/publish      # dry_run=true by default
POST /api/content/approve

GET  /api/analytics/performance/{site_id}
POST /api/analytics/forecast
GET  /api/analytics/oauth/callback

POST /api/agent/run
GET  /api/agent/audit-log/{site_id}

POST /api/onboarding/start
GET  /api/actions/{site_id}

GET  /health                   # Returns {"status":"ok","ai_ready":bool}
```

All authenticated endpoints require `Authorization: Bearer <jwt>` header.

---

## Celery Task Queues

Five queues with dedicated workers:

| Queue | Purpose |
|---|---|
| `crawl` | Playwright web crawls |
| `keyword` | Keyword research + clustering |
| `content` | LLM content generation |
| `analytics` | GSC/GA4 data pulls |
| `learning` | Weekly performance eval |

Start the worker locally:

```bash
celery -A backend.celery_app worker --loglevel=info -Q crawl,keyword,content,analytics,learning
```

Start the scheduler (periodic tasks):

```bash
celery -A backend.celery_app beat --loglevel=info
```

---

## Design Decisions

- **Dry run by default.** All CMS publishing requires explicit `dry_run=False` — the default is `True` to prevent accidental publishes.
- **Doorway page guard.** Local SEO pages must pass an AI scoring check (≥ 60/100) before they can be published.
- **Immutable audit log.** Every agent action writes to `AuditLog` — never update or delete these rows.
- **Approval queue.** Agent-proposed changes land in `PendingAction` and must be approved via the UI before execution.
- **Modular SEO modules.** Each module is self-contained with clear inputs/outputs. They do not call each other directly.
- **User-scoped data.** Sites, keywords, content, and actions all belong to a `User` via FK — no cross-user data leakage.
- **Ollama as free fallback.** When no `GROQ_API_KEY` is set, the system uses a local `llama3.2:3b` model so it works fully offline/free.

---

## Common Workflows

### Add a new API endpoint

1. Add route handler to the appropriate file in `backend/api/routes/`.
2. If the handler needs a new DB operation, add it to the relevant model file or create a helper function.
3. Register the router in `backend/main.py` if it's a new file.
4. Add a corresponding test in `tests/test_<module>.py`.

### Add a new SEO module

1. Create `backend/modules/<name>/` with `__init__.py` and logic files.
2. Export the public interface from `__init__.py`.
3. Add a Celery task in `backend/tasks/` if the work is long-running.
4. Add an API route in `backend/api/routes/`.
5. Add tests in `tests/test_<name>.py`.

### Update the database schema

1. Modify the SQLAlchemy model in `backend/models/`.
2. Atlas uses `init_db()` on startup (which calls `Base.metadata.create_all`) — no migrations framework is in use currently. For production data, add Alembic or handle schema changes manually.

### Frontend — add a new page

1. Create `frontend/app/<route>/page.tsx`.
2. Use `useAuth()` from `contexts/AuthContext` to guard the route.
3. Call the backend via the API proxy in `lib/api.ts` using Axios.
4. Wrap data fetching in TanStack `useQuery`.

---

## Deployment

### Railway (cloud)

- Backend: `railway.toml` points to `backend/Dockerfile`. Health check at `/health`.
- Frontend: Deploy the `frontend/` directory separately (e.g., Vercel).
- Provide `DATABASE_URL`, `REDIS_URL`, and `SECRET_KEY` as Railway environment variables.
- Set `ALLOWED_ORIGINS` to your frontend URL.
- `DEBUG=false` in production.

### Windows Desktop

- The `installer/` directory contains an Inno Setup script that wraps Docker Compose into a clickable installer.
- `installer/atlas-launch.bat` starts all services; `atlas-stop.bat` stops them.
- Default credentials are set in `installer/resources/default.env`.
