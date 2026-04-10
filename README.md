# Atlas — Autonomous SEO & GEO Agent

A full-stack AI SEO/GEO platform that collects data, analyzes it, executes changes, and learns continuously.

## Quick Start

```bash
# 1. Copy env file and fill in your keys
cp .env.example .env

# 2. Start all services
docker compose up --build

# 3. Open the dashboard
open http://localhost:3000
```

## Architecture

| Service | Port | Description |
|---------|------|-------------|
| Frontend (Next.js) | 3000 | Dashboard UI |
| Backend (FastAPI) | 8000 | REST API + Agent |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Job queue + session state |
| Celery Worker | — | Async task executor |
| Celery Beat | — | Scheduled tasks (learning loop) |

## Modules

| Module | Path | Description |
|--------|------|-------------|
| Technical SEO | `modules/technical_seo/` | Playwright crawler + audit engine |
| Keyword Intel | `modules/keyword_intel/` | Intent classifier + cluster builder |
| GEO Engine | `modules/geo_engine/` | AI answerability scorer |
| Content Engine | `modules/content_engine/` | Claude-powered content generator |
| Competitor Intel | `modules/competitor_intel/` | Gap analysis via SerpAPI + Claude |
| Internal Linking | `modules/internal_linking/` | Silo + orphan page detector |
| Local SEO | `modules/local_seo/` | Local page generator with doorway check |
| Backlink AI | `modules/backlink_ai/` | Opportunity finder + outreach emails |
| Analytics | `modules/analytics/` | GSC + GA4 connector |
| Execution | `modules/execution/` | WordPress + Shopify publisher |
| Learning Loop | `modules/learning_loop/` | Weekly performance evaluation |

## API Endpoints

```
GET  /health
GET  /api/sites/
POST /api/sites/
POST /api/technical-seo/crawl/sync
GET  /api/technical-seo/results/{site_id}
POST /api/keywords/classify/sync
GET  /api/keywords/{site_id}
POST /api/content/generate
POST /api/content/local-page
POST /api/content/publish
GET  /api/analytics/performance/{site_id}
POST /api/analytics/forecast
POST /api/agent/run
GET  /api/agent/audit-log/{site_id}
```

## Running Tests

```bash
cd atlas
pip install -r backend/requirements.txt
pytest tests/ -v
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key (required) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `SERPAPI_KEY` | SerpAPI key (optional, enables SERP enrichment) |
| `GOOGLE_CLIENT_ID` | Google OAuth for GSC/GA4 |
| `WORDPRESS_URL` | WordPress site URL |
| `WORDPRESS_APP_PASSWORD` | WordPress application password |
| `SHOPIFY_STORE` | Shopify store domain |
| `SHOPIFY_ACCESS_TOKEN` | Shopify Admin API token |

## Key Design Decisions

- **Dry run by default** — all CMS publishing requires `dry_run=False` explicitly
- **Doorway page check** — local SEO pages must score ≥ 60/100 before publishing is allowed
- **Async throughout** — FastAPI + async SQLAlchemy, no blocking calls on the main thread
- **Celery for heavy work** — crawls, content generation, and analytics pulls queue to workers
- **Claude tool use** — the Atlas Agent uses structured tool_use to autonomously plan + execute
