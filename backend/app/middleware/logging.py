"""Correlation-id propagation and request/response access logging."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import correlation_id_ctx, get_logger

logger = get_logger("app.request")

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        token = correlation_id_ctx.set(correlation_id)
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
        finally:
            correlation_id_ctx.reset(token)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Response-Time-ms"] = str(duration_ms)
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
