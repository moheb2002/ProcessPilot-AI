"""Structured logging with correlation-id propagation."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger import json as jsonlogger

from app.core.config import settings

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")


def get_correlation_id() -> str:
    return correlation_id_ctx.get()


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get()
        record.service = settings.APP_NAME
        record.environment = settings.ENVIRONMENT
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.LOG_LEVEL.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(CorrelationIdFilter())

    if settings.LOG_JSON:
        handler.setFormatter(
            jsonlogger.JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s "
                "%(correlation_id)s %(service)s %(environment)s",
                rename_fields={"asctime": "timestamp", "levelname": "level"},
            )
        )
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | cid=%(correlation_id)s | %(message)s"
            )
        )

    root.addHandler(handler)

    if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
        _attach_application_insights(root)

    for noisy in ("uvicorn.access", "sqlalchemy.engine", "azure", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _attach_application_insights(root: logging.Logger) -> None:
    try:
        from opencensus.ext.azure.log_exporter import AzureLogHandler
    except ImportError:  # pragma: no cover - optional dependency
        root.warning("Application Insights requested but opencensus is not installed")
        return

    azure_handler = AzureLogHandler(
        connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING
    )
    azure_handler.addFilter(CorrelationIdFilter())
    root.addHandler(azure_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
