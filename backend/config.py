import os
import ssl

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache


def _fix_ssl_certs():
    """Ensure Python can verify HTTPS on fresh Windows installs."""
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass


_fix_ssl_certs()


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    anthropic_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://atlas:atlas@db:5432/atlas"
    redis_url: str = "redis://redis:6379/0"

    # Search APIs
    serpapi_key: str = ""
    scrapingbee_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/analytics/oauth/callback"

    # WordPress
    wordpress_url: str = ""
    wordpress_user: str = ""
    wordpress_app_password: str = ""

    # Shopify
    shopify_store: str = ""
    shopify_access_token: str = ""

    # App
    debug: bool = True
    secret_key: str = "change-me-in-production"
    allowed_origins: str = "http://localhost:3000"

    # Claude model
    claude_model: str = "claude-sonnet-4-5"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
