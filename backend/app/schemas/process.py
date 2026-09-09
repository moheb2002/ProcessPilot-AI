"""Process analysis API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, Field

from app.models.analysis import AnalysisStatus
from app.schemas.agent import (
    AutomationOpportunity,
    Bottleneck,
    ProcessAnalysis,
    ROIInput,
    ROIResult,
)
from app.schemas.common import APIModel, ORMModel
from app.schemas.insight import (
    AnalysisConfidence,
    AutomationPotential,
    ExecutiveReport,
    QuickWin,
    RecommendationDetail,
    Roadmap,
)


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


class ProcessSummary(ORMModel):
    """Flat, UI-friendly view of the structured process model."""

    name: str = ""
    total_steps: int = 0
    manual_tasks: int = 0
    actors: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)

    @classmethod
    def from_analysis(cls, analysis: ProcessAnalysis) -> "ProcessSummary":
        manual = len([s for s in analysis.steps if s.is_manual]) or len(analysis.manual_tasks)
        return cls(
            name=analysis.process_name,
            total_steps=len(analysis.steps),
            manual_tasks=manual,
            actors=analysis.actors,
            systems=analysis.systems,
            approvals=analysis.approvals,
        )


class ProcessAnalyzeResponse(ORMModel):
    """The complete analysis. `roi` is the single source of truth for every figure."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "analysis_id": "b8d2f0b6-7e1a-4a1e-9f0c-2b6f3f2f1a44",
                    "status": "completed",
                    "process": {
                        "name": "Purchase Approval Process",
                        "total_steps": 17,
                        "manual_tasks": 10,
                        "actors": ["Requester", "Manager", "Finance"],
                        "systems": ["SAP", "Outlook"],
                        "approvals": ["Manager approval", "Finance approval"],
                    },
                    "automation_potential": {
                        "percentage": 55,
                        "explanation": [
                            "Routing and data entry are fully rule-based.",
                            "Exception handling still requires human judgement.",
                        ],
                        "calculation_method": "Estimated once by the automation-potential agent.",
                    },
                    "confidence": {
                        "score": 87,
                        "level": "Medium",
                        "reasons": ["17 discrete process steps were detected."],
                        "missing_information": ["Per-step cycle times."],
                    },
                    "roi": {
                        "current_monthly_hours": 80,
                        "estimated_hours_saved": 44,
                        "remaining_monthly_hours": 36,
                        "monthly_productivity_value": 1232.00,
                        "annual_productivity_value": 14784.00,
                        "automation_potential_percentage": 55,
                        "calculation_method": "current_monthly_hours = monthly_volume x "
                        "minutes_per_case / 60; ...",
                        "assumptions": [
                            "Volume, handling time and hourly cost are steady-state averages."
                        ],
                    },
                    "bottlenecks": [],
                    "recommendations": [],
                    "quick_wins": [],
                    "total_tokens": 4210,
                    "duration_ms": 8123,
                }
            ]
        },
    )

    analysis_id: str | None = None
    status: AnalysisStatus = AnalysisStatus.COMPLETED
    process: ProcessSummary = Field(default_factory=ProcessSummary)
    analysis: ProcessAnalysis
    automation_potential: AutomationPotential = Field(default_factory=AutomationPotential)
    confidence: AnalysisConfidence = Field(default_factory=AnalysisConfidence)
    bottlenecks: list[Bottleneck] = Field(default_factory=list)
    recommendations: list[RecommendationDetail] = Field(default_factory=list)
    quick_wins: list[QuickWin] = Field(default_factory=list)
    roi: ROIResult = Field(default_factory=ROIResult)
    roadmap: Roadmap = Field(default_factory=Roadmap)
    executive_report: ExecutiveReport | None = None
    #: Retained for backwards compatibility with the existing front end.
    opportunities: list[AutomationOpportunity] = Field(default_factory=list)
    total_tokens: int = 0
    duration_ms: int = 0


class AnalysisSummary(ORMModel):
    id: str
    process_name: str
    status: AnalysisStatus
    total_tokens: int
    created_at: datetime
