"""
Central configuration module — loads all settings from environment variables.
"""

import os
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Raise if a required env var is missing."""
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Required environment variable '{name}' is not set.")
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default)


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------
BOT_TOKEN: str = _require("BOT_TOKEN")
WEBHOOK_URL: Optional[str] = _optional("WEBHOOK_URL") or None
WEBHOOK_PATH: str = _optional("WEBHOOK_PATH", "/webhook")
WEBAPP_URL: str = _optional("WEBAPP_URL", "https://example.com/app")

# ---------------------------------------------------------------------------
# Database (PostgreSQL / Supabase)
# ---------------------------------------------------------------------------
DATABASE_URL: str = _optional(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_bot",
)

# ---------------------------------------------------------------------------
# Redis (session / rate-limit cache)
# ---------------------------------------------------------------------------
REDIS_URL: str = _optional("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# FastAPI / redirect server
# ---------------------------------------------------------------------------
API_HOST: str = _optional("API_HOST", "0.0.0.0")
API_PORT: int = int(_optional("API_PORT", "8000"))
API_SECRET_KEY: str = _optional("API_SECRET_KEY", "change-me-in-production")
BASE_URL: str = _optional("BASE_URL", "http://localhost:8000")

# Short-link prefix used for dynamic QR redirects
SHORT_URL_PREFIX: str = _optional("SHORT_URL_PREFIX", f"{BASE_URL}/r/")

# ---------------------------------------------------------------------------
# Search / enrichment APIs
# ---------------------------------------------------------------------------
GOOGLE_API_KEY: Optional[str] = _optional("GOOGLE_API_KEY") or None
GOOGLE_CSE_ID: Optional[str] = _optional("GOOGLE_CSE_ID") or None
SERP_API_KEY: Optional[str] = _optional("SERP_API_KEY") or None

# VirusTotal for URL safety checks
VIRUSTOTAL_API_KEY: Optional[str] = _optional("VIRUSTOTAL_API_KEY") or None

# Open Food Facts — free product DB (no key needed)
OPENFOODFACTS_ENABLED: bool = _optional("OPENFOODFACTS_ENABLED", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Email (SMTP)
# ---------------------------------------------------------------------------
SMTP_HOST: str = _optional("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(_optional("SMTP_PORT", "587"))
SMTP_USER: Optional[str] = _optional("SMTP_USER") or None
SMTP_PASSWORD: Optional[str] = _optional("SMTP_PASSWORD") or None
SMTP_FROM: str = _optional("SMTP_FROM", "noreply@example.com")

# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------
STRIPE_SECRET_KEY: Optional[str] = _optional("STRIPE_SECRET_KEY") or None
STRIPE_WEBHOOK_SECRET: Optional[str] = _optional("STRIPE_WEBHOOK_SECRET") or None

# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in _optional("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

# ---------------------------------------------------------------------------
# Limits / tiers
# ---------------------------------------------------------------------------
FREE_DAILY_SCANS: int = int(_optional("FREE_DAILY_SCANS", "20"))
FREE_DAILY_GENERATIONS: int = int(_optional("FREE_DAILY_GENERATIONS", "10"))
FREE_DYNAMIC_QR_LIMIT: int = int(_optional("FREE_DYNAMIC_QR_LIMIT", "3"))

PREMIUM_PRICE_STARS: int = int(_optional("PREMIUM_PRICE_STARS", "500"))  # Telegram Stars
PREMIUM_PRICE_USD: float = float(_optional("PREMIUM_PRICE_USD", "4.99"))

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
UPLOAD_DIR: str = _optional("UPLOAD_DIR", "/tmp/tgbot_uploads")
GENERATED_DIR: str = _optional("GENERATED_DIR", "/tmp/tgbot_generated")

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
LOG_LEVEL: str = _optional("LOG_LEVEL", "INFO")
ENVIRONMENT: str = _optional("ENVIRONMENT", "development")
DEBUG: bool = ENVIRONMENT == "development"

# Ensure storage directories exist at import time
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)
