"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DBSession
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.health import HealthResponse, ReadinessResponse

logger = get_logger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse()


@router.get("/health/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness(session: DBSession) -> ReadinessResponse:
    database = "up"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("readiness_database_check_failed")
        database = "down"

    return ReadinessResponse(
        status="ready" if database == "up" else "degraded",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        database=database,
        llm="mock" if settings.llm_mock_mode else "azure_openai",
    )
