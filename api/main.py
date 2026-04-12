"""
FastAPI application.

Serves:
  • /r/{short_code}         — dynamic QR redirect
  • /api/*                  — generation, scanning, analytics
  • /api/admin/*            — admin endpoints
  • /app/*                  — static Mini App files
  • /docs                   — Swagger UI
  • /redoc                  — ReDoc
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import dynamic_qr, generate, admin
from config.logging_config import setup_logging
from database.engine import init_db

logger = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).parent.parent / "webapp"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await init_db()
    logger.info("FastAPI started.")
    yield
    logger.info("FastAPI shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Code Scanner & Generator API",
        description=(
            "Backend for the Telegram Code Scanner & Generator bot.\n\n"
            "Provides dynamic QR redirect, code generation, scanning, and admin endpoints."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS — allow Telegram Mini App origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(dynamic_qr.router)
    app.include_router(generate.router)
    app.include_router(admin.router)

    # Serve Mini App static files
    if WEBAPP_DIR.exists():
        app.mount("/app", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")

    @app.get("/health", tags=["System"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    from config import settings

    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
