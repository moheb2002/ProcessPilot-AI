"""Shared schema primitives."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIModel(BaseModel):
    """Base schema with ORM support and strict extra-field handling."""

    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


class ORMModel(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class TimestampedSchema(ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    correlation_id: str
