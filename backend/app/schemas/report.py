"""Executive report and document schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.agent import (
    AutomationOpportunity,
    Bottleneck,
    ProcessAnalysis,
    ROIResultSchema,
)
from app.schemas.common import APIModel, ORMModel


class ReportGenerateRequest(APIModel):
    """Generate a report either from a stored analysis or from an inline payload."""

    analysis_id: str | None = Field(default=None, description="Id of a persisted analysis.")
    analysis: ProcessAnalysis | None = None
    bottlenecks: list[Bottleneck] = Field(default_factory=list)
    opportunities: list[AutomationOpportunity] = Field(default_factory=list)
    roi: ROIResultSchema | None = None

    @model_validator(mode="after")
    def _require_source(self) -> "ReportGenerateRequest":
        if self.analysis_id is None and self.analysis is None:
            raise ValueError("Provide either 'analysis_id' or an inline 'analysis' object.")
        return self


class ReportGenerateResponse(ORMModel):
    analysis_id: str | None = None
    report: str
    total_tokens: int = 0


class DocumentRead(ORMModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    storage_backend: str
    storage_uri: str
    text_preview: str | None = None
    created_at: datetime
