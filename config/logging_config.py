"""
Structured logging configuration using Python's standard logging + optional structlog.
"""

import logging
import sys
from config import settings


def setup_logging() -> None:
    """Configure root logger for the whole application."""
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
        if settings.ENVIRONMENT == "production"
        else "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    )

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    # Silence noisy third-party loggers
    for noisy in ("aiohttp", "asyncio", "PIL", "urllib3", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging initialised | level=%s env=%s",
        settings.LOG_LEVEL,
        settings.ENVIRONMENT,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
