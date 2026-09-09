"""Executive report and document schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.common import APIModel, ORMModel
from app.schemas.insight import (
    AnalysisConfidence,
    ExecutiveReport,
    QuickWin,
    RecommendationDetail,
    Roadmap,
)
from app.schemas.process import ProcessAnalyzeResponse
from app.schemas.roi import ROIResult


class ReportGenerateRequest(APIModel):
    """Generate a report from a stored analysis id, or from a complete analysis object.

    There is deliberately no way to supply ROI inputs here: the report never
    calculates ROI, it reuses the validated :class:`ROIResult` produced by the
    analysis pipeline.
    """

    analysis_id: str | None = Field(default=None, description="Id of a persisted analysis.")
    analysis_result: ProcessAnalyzeResponse | None = Field(
        default=None,
        description="A complete, already-validated analysis response to report on.",
    )

    @model_validator(mode="after")
    def _require_source(self) -> "ReportGenerateRequest":
        if self.analysis_id is None and self.analysis_result is None:
            raise ValueError(
                "Provide either 'analysis_id' or a complete 'analysis_result' object."
            )
        return self


class ReportGenerateResponse(ORMModel):
    """The report plus the exact same ROI object the analysis returned."""

    analysis_id: str | None = None
    #: Rendered Markdown, kept for backwards compatibility with existing clients.
    report: str
    executive_report: ExecutiveReport = Field(default_factory=ExecutiveReport)
    roi: ROIResult = Field(default_factory=ROIResult)
    confidence: AnalysisConfidence = Field(default_factory=AnalysisConfidence)
    recommendations: list[RecommendationDetail] = Field(default_factory=list)
    quick_wins: list[QuickWin] = Field(default_factory=list)
    roadmap: Roadmap = Field(default_factory=Roadmap)
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
