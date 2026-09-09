"""In-process sliding-window rate limiter.

Suitable for a single-instance MVP. Swap the backing store for Redis or Azure API
Management when scaling horizontally.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import get_correlation_id, get_logger

logger = get_logger(__name__)

EXEMPT_PATHS = frozenset({"/health", "/health/ready", "/docs", "/redoc", "/openapi.json"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limit: int | None = None, window_seconds: int | None = None) -> None:
        super().__init__(app)
        self._limit = limit or settings.RATE_LIMIT_REQUESTS
        self._window = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.RATE_LIMIT_ENABLED or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        key = self._client_key(request)
        allowed, remaining, retry_after = self._register(key)

        if not allowed:
            logger.warning("rate_limit_exceeded", extra={"client": key, "path": request.url.path})
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests. Please retry later.",
                    },
                    "correlation_id": get_correlation_id(),
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _register(self, key: str) -> tuple[bool, int, int]:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self._window:
                bucket.popleft()

            if len(bucket) >= self._limit:
                retry_after = max(1, int(self._window - (now - bucket[0])))
                return False, 0, retry_after

            bucket.append(now)
            return True, self._limit - len(bucket), 0

    @staticmethod
    def _client_key(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
