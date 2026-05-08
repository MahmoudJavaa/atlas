import os
import ssl

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


def _fix_ssl_certs():
    """Ensure Python can verify HTTPS on fresh installs and inside Docker."""
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass


_fix_ssl_certs()


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── AI Engine ─────────────────────────────────────────────────────────────
    # Groq (cloud, free — set GROQ_API_KEY to enable)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Ollama (local Docker fallback — used automatically when Groq key is absent)
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://atlas:atlas@db:5432/atlas"
    redis_url: str = "redis://redis:6379/0"

    # ── Search APIs (optional) ────────────────────────────────────────────────
    serpapi_key: str = ""
    scrapingbee_key: str = ""
    # DataForSEO — real keyword volume + difficulty (supports EN + AR)
    # Sign up free at https://dataforseo.com — get login + password from dashboard
    dataforseo_login: str = ""
    dataforseo_password: str = ""

    # ── Google OAuth (optional — for Search Console) ──────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/analytics/oauth/callback"

    # ── CMS integrations (optional) ───────────────────────────────────────────
    wordpress_url: str = ""
    wordpress_user: str = ""
    wordpress_app_password: str = ""
    shopify_store: str = ""
    shopify_access_token: str = ""

    # ── App ───────────────────────────────────────────────────────────────────
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Comma-separated list of allowed frontend origins.
    # In production set this to your Vercel URL, e.g.:
    #   ALLOWED_ORIGINS=https://yourapp.vercel.app,https://yourdomain.com
    allowed_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
