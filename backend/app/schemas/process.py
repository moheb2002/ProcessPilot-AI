"""Process analysis API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.analysis import AnalysisStatus
from app.schemas.agent import (
    AutomationOpportunity,
    Bottleneck,
    ProcessAnalysis,
    ROIInput,
    ROIResultSchema,
)
from app.schemas.common import APIModel, ORMModel


class ProcessAnalyzeRequest(APIModel):
    process_name: str = Field(min_length=2, max_length=255, examples=["Employee Onboarding"])
    description: str = Field(
        min_length=20,
        max_length=20_000,
        examples=[
            "HR receives a signed offer, creates the employee record in SAP by hand, "
            "emails IT for account provisioning, and waits for two manager approvals."
        ],
    )
    department: str | None = Field(default=None, max_length=128)
    document_ids: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Previously uploaded documents whose text is added as context.",
    )
    roi_input: ROIInput | None = None
    persist: bool = Field(default=True, description="Persist the analysis for later retrieval.")


class ProcessAnalyzeResponse(ORMModel):
    analysis_id: str | None = None
    status: AnalysisStatus = AnalysisStatus.COMPLETED
    analysis: ProcessAnalysis
    bottlenecks: list[Bottleneck] = Field(default_factory=list)
    opportunities: list[AutomationOpportunity] = Field(default_factory=list)
    roi: ROIResultSchema = Field(default_factory=ROIResultSchema)
    total_tokens: int = 0
    duration_ms: int = 0


class AnalysisSummary(ORMModel):
    id: str
    process_name: str
    status: AnalysisStatus
    total_tokens: int
    created_at: datetime
