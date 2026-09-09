"""Health check schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    version: str
    environment: str
    database: Literal["up", "down"]
    llm: Literal["azure_openai", "mock"]
