"""Executive report generation service.

The report is *assembled* here, not calculated. Every figure comes from the
validated :class:`~app.schemas.roi.ROIResult` produced by the analysis
pipeline; the LLM contributes narrative prose only.
"""

from __future__ import annotations

from app.agents import ExecutiveSummaryAgent
from app.core.logging import get_correlation_id, get_logger
from app.repositories import AuditRepository
from app.schemas.process import ProcessAnalyzeResponse
from app.schemas.report import ReportGenerateRequest, ReportGenerateResponse
from app.schemas.user import CurrentUser
from app.services.analysis_service import AnalysisService
from app.services.azure_openai import LLMClient
from app.services.report_renderer import build_roadmap, render_report
from app.services.roi_service import assert_roi_consistency

logger = get_logger(__name__)


class ReportService:
    def __init__(
        self,
        *,
        llm: LLMClient,
        analysis_service: AnalysisService,
        audit_repo: AuditRepository,
    ) -> None:
        self._agent = ExecutiveSummaryAgent(llm)
        self._analysis_service = analysis_service
        self._audit_repo = audit_repo

    async def generate(
        self, request: ReportGenerateRequest, user: CurrentUser
    ) -> ReportGenerateResponse:
        if request.analysis_id:
            return await self._generate_from_stored(request.analysis_id, user)
        assert request.analysis_result is not None  # guaranteed by the request validator
        return await self._build(request.analysis_result)

    async def _generate_from_stored(
        self, analysis_id: str, user: CurrentUser
    ) -> ReportGenerateResponse:
        record = await self._analysis_service.get_analysis(analysis_id, user)
        source = AnalysisService.to_response(record)
        response = await self._build(source)

        await self._analysis_service.attach_report(
            record,
            response.executive_report.model_dump(mode="json"),
            response.report,
            response.total_tokens,
        )
        await self._audit_repo.record(
            action="report.generated",
            resource_type="analysis",
            resource_id=record.id,
            actor_id=user.id,
            correlation_id=get_correlation_id(),
            context={"tokens": response.total_tokens},
        )
        await self._audit_repo.commit()
        return response.model_copy(update={"analysis_id": record.id})

    async def _build(self, source: ProcessAnalyzeResponse) -> ReportGenerateResponse:
        """Render the report for an already-validated analysis. No ROI maths here."""
        roi = source.roi
        logger.info(
            "report_generation_requested",
            extra={
                "correlation_id": get_correlation_id(),
                "analysis_id": source.analysis_id,
                "process_name": source.process.name or source.analysis.process_name,
                "estimated_hours_saved": float(roi.estimated_hours_saved),
                "annual_productivity_value": float(roi.annual_productivity_value),
            },
        )

        narrative, usage = await self._agent.run(
            process_name=source.process.name or source.analysis.process_name,
            analysis=source.analysis,
            bottlenecks=source.bottlenecks,
            recommendations=source.recommendations,
            quick_wins=source.quick_wins,
            confidence=source.confidence,
            roi=roi,
        )

        roadmap = source.roadmap
        if not roadmap.phases:
            roadmap = build_roadmap(source.recommendations, source.quick_wins)

        report = render_report(
            process_name=source.process.name or source.analysis.process_name,
            narrative=narrative,
            roi=roi,
            confidence=source.confidence,
            recommendations=source.recommendations,
            quick_wins=source.quick_wins,
            bottlenecks=source.bottlenecks,
            roadmap=roadmap,
        )

        # Final guard rail: the report's ROI must be byte-for-byte the analysis ROI.
        verified_roi = assert_roi_consistency(
            source=source.roi, candidate=roi, context="executive_report"
        )

        return ReportGenerateResponse(
            analysis_id=source.analysis_id,
            report=report.markdown,
            executive_report=report,
            roi=verified_roi,
            confidence=source.confidence,
            recommendations=source.recommendations,
            quick_wins=source.quick_wins,
            roadmap=roadmap,
            total_tokens=usage.total_tokens,
        )
