"""Executive report generation service."""

from __future__ import annotations

from app.agents import ExecutiveSummaryAgent
from app.core.logging import get_correlation_id
from app.repositories import AuditRepository
from app.schemas.agent import ROIResultSchema
from app.schemas.report import ReportGenerateRequest, ReportGenerateResponse
from app.schemas.user import CurrentUser
from app.services.analysis_service import AnalysisService
from app.services.azure_openai import LLMClient


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
        return await self._generate_inline(request)

    async def _generate_from_stored(
        self, analysis_id: str, user: CurrentUser
    ) -> ReportGenerateResponse:
        record = await self._analysis_service.get_analysis(analysis_id, user)
        roi = (
            ROIResultSchema.model_validate(record.roi_result, from_attributes=True)
            if record.roi_result
            else ROIResultSchema()
        )
        report, usage = await self._agent.run(
            process_name=record.process_name,
            analysis=record.analysis_payload,
            bottlenecks=record.bottlenecks_payload,
            opportunities=[
                {
                    "solution": r.solution,
                    "technology": r.technology,
                    "business_value": r.business_value,
                    "implementation_effort": r.implementation_effort,
                }
                for r in record.recommendations
            ],
            roi=roi.model_dump(mode="json"),
        )
        await self._analysis_service.attach_report(record, report, usage.total_tokens)
        await self._audit_repo.record(
            action="report.generated",
            resource_type="analysis",
            resource_id=record.id,
            actor_id=user.id,
            correlation_id=get_correlation_id(),
            context={"tokens": usage.total_tokens},
        )
        await self._audit_repo.commit()
        return ReportGenerateResponse(
            analysis_id=record.id, report=report, total_tokens=usage.total_tokens
        )

    async def _generate_inline(self, request: ReportGenerateRequest) -> ReportGenerateResponse:
        assert request.analysis is not None  # guaranteed by the request validator
        report, usage = await self._agent.run(
            process_name=request.analysis.process_name or "Business Process",
            analysis=request.analysis,
            bottlenecks=request.bottlenecks,
            opportunities=request.opportunities,
            roi=request.roi or ROIResultSchema(),
        )
        return ReportGenerateResponse(report=report, total_tokens=usage.total_tokens)
