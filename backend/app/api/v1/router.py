"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import auth, documents, process, report

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(process.router)
api_router.include_router(report.router)
api_router.include_router(documents.router)

__all__ = ["api_router"]
