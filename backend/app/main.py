"""ProcessPilot AI — FastAPI application factory and entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_router
from app.api.v1.routers import health
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.init_db import init_db
from app.db.session import engine
from app.middleware import register_middleware

logger = get_logger(__name__)

DESCRIPTION = """
**ProcessPilot AI** turns a natural-language description of a business process into an
actionable transformation plan.

The analysis pipeline chains five agents:

1. **Process Analyzer** — extracts actors, systems, steps, approvals and manual tasks.
2. **Bottleneck Detection** — ranks constraints by severity and business impact.
3. **Automation Advisor** — maps constraints to Microsoft AI and automation services.
4. **ROI Agent** — computes hours saved, monthly/annual savings and an ROI score.
5. **Executive Summary** — writes a consultant-style Markdown report.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info(
        "application_starting",
        extra={
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "llm_mode": "mock" if settings.llm_mock_mode else "azure_openai",
            "storage_backend": settings.STORAGE_BACKEND,
        },
    )
    await init_db()
    try:
        yield
    finally:
        await engine.dispose()
        logger.info("application_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    register_middleware(app)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
