"""Domain exceptions and global exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_correlation_id, get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base application error."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: object | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"
    message = "Resource not found."


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_error"
    message = "Request payload is invalid."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"
    message = "Authentication credentials are missing or invalid."


class AuthorizationError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"
    message = "You do not have permission to perform this action."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"
    message = "Resource already exists."


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"
    message = "Too many requests. Please retry later."


class StorageError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "storage_error"
    message = "Document storage operation failed."


class LLMError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "llm_unavailable"
    message = "The AI service is currently unavailable."


def _payload(error_code: str, message: str, details: object | None = None) -> dict[str, object]:
    body: dict[str, object] = {
        "error": {"code": error_code, "message": message},
        "correlation_id": get_correlation_id(),
    }
    if details is not None:
        body["error"]["details"] = details  # type: ignore[index]
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", extra={"error_code": exc.error_code, "detail": exc.message})
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.error_code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # `errors()` can embed raw exception objects in `ctx`, so encode defensively.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_payload(
                "validation_error",
                "Request payload is invalid.",
                jsonable_encoder(exc.errors()),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload("http_error", str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_payload("internal_error", "An unexpected error occurred."),
        )
