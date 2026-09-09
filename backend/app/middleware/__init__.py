"""Middleware registration."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.middleware.logging import CorrelationIdMiddleware, RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

__all__ = [
    "CorrelationIdMiddleware",
    "RateLimitMiddleware",
    "RequestLoggingMiddleware",
    "register_middleware",
]


def register_middleware(app: FastAPI) -> None:
    """Order matters: the last registered middleware runs first."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-Response-Time-ms"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
