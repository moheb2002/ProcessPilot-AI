"""Analysis orchestration: runs the agent pipeline and persists the result.

ROI is calculated exactly once, by :mod:`app.services.roi_service`, and the
resulting object is threaded through scoring, persistence and the executive
report without ever being recalculated.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Sequence

from app.agents import (
    AutomationAdvisorAgent,
    BottleneckDetectionAgent,
    ExecutiveSummaryAgent,
    ProcessAnalyzerAgent,
    ROIAgent,
)
from app.core.exceptions import NotFoundError
from app.core.logging import get_correlation_id, get_logger
from app.models.analysis import Analysis, AnalysisStatus
from app.models.process import Process
from app.models.recommendation import Recommendation
from app.models.roi import ROIResult as ROIResultRow
from app.repositories import (
    AnalysisRepository,
    AuditRepository,
    DocumentRepository,
    ProcessRepository,
)
from app.schemas.agent import (
    AutomationOpportunity,
    Bottleneck,
    ProcessAnalysis,
    ROIInput,
    TokenUsage,
)
from app.schemas.insight import (
    AnalysisConfidence,
    AutomationPotential,
    QuickWin,
    RecommendationDetail,
    Roadmap,
)
from app.schemas.process import ProcessAnalyzeRequest, ProcessAnalyzeResponse, ProcessSummary
from app.schemas.roi import ROIResult
from app.schemas.user import CurrentUser
from app.services.azure_openai import LLMClient
from app.services.confidence_service import calculate_confidence
from app.services.recommendation_service import build_recommendations, select_quick_wins
from app.services.report_renderer import build_roadmap

logger = get_logger(__name__)

MAX_DOCUMENT_CONTEXT_CHARS = 12_000


class AnalysisService:
    """Coordinates the five agents; owns no persistence details of its own."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        analysis_repo: AnalysisRepository,
        process_repo: ProcessRepository,
        document_repo: DocumentRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._analysis_repo = analysis_repo
        self._process_repo = process_repo
        self._document_repo = document_repo
        self._audit_repo = audit_repo

        self._analyzer = ProcessAnalyzerAgent(llm)
        self._bottlenecks = BottleneckDetectionAgent(llm)
        self._advisor = AutomationAdvisorAgent(llm)
        self._roi = ROIAgent(llm)
        self._summary = ExecutiveSummaryAgent(llm)

    async def analyze(
        self, request: ProcessAnalyzeRequest, user: CurrentUser
    ) -> ProcessAnalyzeResponse:
        started = time.perf_counter()
        usage = TokenUsage()

        document_context = await self._load_document_context(request.document_ids, user.id)

        analysis, step_usage = await self._analyzer.run(
            process_name=request.process_name,
            description=request.description,
            document_context=document_context,
        )
        usage += step_usage
        if not analysis.process_name:
            analysis.process_name = request.process_name

        bottleneck_report, step_usage = await self._bottlenecks.run(analysis=analysis)
        usage += step_usage

        automation_plan, step_usage = await self._advisor.run(
            analysis=analysis, bottlenecks=bottleneck_report.bottlenecks
        )
        usage += step_usage

        roi_input = request.roi_input or ROIInput()
        roi_stage, step_usage = await self._roi.run(
            roi_input=roi_input,
            analysis=analysis,
            opportunities=automation_plan.opportunities,
        )
        usage += step_usage
        roi = roi_stage.roi  # <- the single source of truth from here on

        confidence = calculate_confidence(
            description=request.description,
            analysis=analysis,
            bottlenecks=bottleneck_report.bottlenecks,
            roi_input=roi_stage.calculation_input,
            document_context=document_context,
        )
        recommendations = build_recommendations(
            opportunities=automation_plan.opportunities,
            bottlenecks=bottleneck_report.bottlenecks,
            roi=roi,
            monthly_volume=roi_input.monthly_volume,
            hourly_cost=Decimal(roi_input.hourly_cost),
        )
        quick_wins = select_quick_wins(recommendations)
        roadmap = build_roadmap(recommendations, quick_wins)

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "analysis_pipeline_completed",
            extra={
                "correlation_id": get_correlation_id(),
                "process_name": request.process_name,
                "total_tokens": usage.total_tokens,
                "duration_ms": duration_ms,
                "confidence_score": confidence.score,
                "recommendation_count": len(recommendations),
                "quick_win_count": len(quick_wins),
            },
        )

        response = ProcessAnalyzeResponse(
            analysis_id=None,
            status=AnalysisStatus.COMPLETED,
            process=ProcessSummary.from_analysis(analysis),
            analysis=analysis,
            automation_potential=roi_stage.automation_potential,
            confidence=confidence,
            bottlenecks=bottleneck_report.bottlenecks,
            recommendations=recommendations,
            quick_wins=quick_wins,
            roi=roi,
            roadmap=roadmap,
            opportunities=automation_plan.opportunities,
            total_tokens=usage.total_tokens,
            duration_ms=duration_ms,
        )

        if request.persist:
            response.analysis_id = await self._persist(
                request=request,
                user=user,
                response=response,
                roi_input=roi_input,
                usage=usage,
            )
        return response

    async def get_analysis(self, analysis_id: str, user: CurrentUser) -> Analysis:
        analysis = await self._analysis_repo.get(analysis_id)
        if analysis is None or analysis.owner_id != user.id:
            raise NotFoundError(f"Analysis '{analysis_id}' was not found.")
        return analysis

    @staticmethod
    def to_response(record: Analysis) -> ProcessAnalyzeResponse:
        """Rehydrate a stored analysis without recalculating a single figure."""
        analysis = ProcessAnalysis.model_validate(record.analysis_payload)
        roi = (
            ROIResult.model_validate(record.roi_result, from_attributes=True)
            if record.roi_result
            else ROIResult()
        )
        if record.roi_result is not None:
            # The ORM row stores the canonical values under their legacy column names.
            roi = roi.model_copy(
                update={
                    "current_monthly_hours": roi.current_hours,
                    "monthly_productivity_value": roi.monthly_savings,
                    "annual_productivity_value": roi.annual_savings,
                }
            )
        return ProcessAnalyzeResponse(
            analysis_id=record.id,
            status=record.status,
            process=ProcessSummary.from_analysis(analysis),
            analysis=analysis,
            automation_potential=AutomationPotential.model_validate(
                record.automation_potential_payload or {}
            ),
            confidence=AnalysisConfidence.model_validate(record.confidence_payload or {}),
            bottlenecks=[Bottleneck.model_validate(b) for b in record.bottlenecks_payload or []],
            recommendations=[
                RecommendationDetail.model_validate(r)
                for r in record.recommendations_payload or []
            ],
            quick_wins=[QuickWin.model_validate(q) for q in record.quick_wins_payload or []],
            roi=roi,
            roadmap=Roadmap.model_validate(record.roadmap_payload or {}),
            opportunities=[
                AutomationOpportunity.model_validate(o)
                for o in record.opportunities_payload or []
            ],
            total_tokens=record.total_tokens,
            duration_ms=record.duration_ms,
        )

    async def list_analyses(
        self, user: CurrentUser, *, limit: int, offset: int
    ) -> tuple[Sequence[Analysis], int]:
        items = await self._analysis_repo.list_for_owner(user.id, limit=limit, offset=offset)
        total = await self._analysis_repo.count(owner_id=user.id)
        return items, total

    async def attach_report(
        self, analysis: Analysis, report_payload: dict, markdown: str, tokens: int
    ) -> None:
        analysis.executive_report = markdown
        analysis.report_payload = report_payload
        analysis.total_tokens += tokens
        await self._analysis_repo.commit()

    async def delete_analysis(self, analysis_id: str, user: CurrentUser) -> None:
        record = await self.get_analysis(analysis_id, user)
        await self._analysis_repo.delete(record)
        await self._audit_repo.record(
            action="analysis.deleted",
            resource_type="analysis",
            resource_id=analysis_id,
            actor_id=user.id,
            correlation_id=get_correlation_id(),
        )
        await self._analysis_repo.commit()

    # ------------------------------------------------------------------ internals
    async def _load_document_context(self, document_ids: list[str], owner_id: str) -> str:
        if not document_ids:
            return ""
        documents = await self._document_repo.get_many(document_ids, owner_id)
        chunks = [
            f"--- {doc.filename} ---\n{doc.extracted_text}"
            for doc in documents
            if doc.extracted_text
        ]
        return "\n\n".join(chunks)[:MAX_DOCUMENT_CONTEXT_CHARS]

    async def _persist(
        self,
        *,
        request: ProcessAnalyzeRequest,
        user: CurrentUser,
        response: ProcessAnalyzeResponse,
        roi_input: ROIInput,
        usage: TokenUsage,
    ) -> str:
        process = await self._process_repo.add(
            Process(
                name=request.process_name,
                description=request.description,
                department=request.department,
                owner_id=user.id,
                process_metadata={"document_ids": request.document_ids},
            )
        )

        roi = response.roi
        record = Analysis(
            status=AnalysisStatus.COMPLETED,
            process_name=response.analysis.process_name or request.process_name,
            analysis_payload=response.analysis.model_dump(mode="json"),
            bottlenecks_payload=[b.model_dump(mode="json") for b in response.bottlenecks],
            opportunities_payload=[o.model_dump(mode="json") for o in response.opportunities],
            recommendations_payload=[r.model_dump(mode="json") for r in response.recommendations],
            automation_potential_payload=response.automation_potential.model_dump(mode="json"),
            confidence_payload=response.confidence.model_dump(mode="json"),
            quick_wins_payload=[q.model_dump(mode="json") for q in response.quick_wins],
            roadmap_payload=response.roadmap.model_dump(mode="json"),
            total_tokens=usage.total_tokens,
            duration_ms=response.duration_ms,
            owner_id=user.id,
            process_id=process.id,
        )
        record.recommendations = [
            Recommendation(
                solution=item.title,
                technology=", ".join(item.recommended_technologies),
                business_value=item.description,
                implementation_effort=item.implementation_effort.value,
                reference=item.id,
                title=item.title,
                description=item.description,
                related_bottleneck_ids=item.related_bottleneck_ids,
                priority=item.priority.value,
                business_impact=item.business_impact.value,
                implementation_complexity=item.implementation_complexity.value,
                estimated_hours_saved_per_month=float(item.estimated_hours_saved_per_month),
                estimated_monthly_value=float(item.estimated_monthly_value),
                estimated_annual_value=float(item.estimated_annual_value),
                recommended_technologies=item.recommended_technologies,
                expected_benefits=item.expected_benefits,
                dependencies=item.dependencies,
                implementation_notes=item.implementation_notes,
                implementation_timeframe_days=item.implementation_timeframe_days,
                recommendation_score=item.recommendation_score,
                score_explanation=item.score_explanation,
            )
            for item in response.recommendations
        ]
        record.roi_result = ROIResultRow(
            monthly_volume=roi_input.monthly_volume,
            minutes_per_transaction=float(roi_input.minutes_per_case),
            employee_hourly_rate=float(roi_input.hourly_cost),
            automation_rate=float(roi.automation_potential_percentage) / 100,
            automation_potential_percentage=float(roi.automation_potential_percentage),
            current_hours=float(roi.current_monthly_hours),
            estimated_hours_saved=float(roi.estimated_hours_saved),
            remaining_monthly_hours=float(roi.remaining_monthly_hours),
            monthly_savings=float(roi.monthly_productivity_value),
            annual_savings=float(roi.annual_productivity_value),
            roi_score=float(roi.roi_score),
            calculation_method=roi.calculation_method,
            assumptions=roi.assumptions,
        )
        await self._analysis_repo.add(record)

        await self._audit_repo.record(
            action="process.analyzed",
            resource_type="analysis",
            resource_id=record.id,
            actor_id=user.id,
            correlation_id=get_correlation_id(),
            context={"process_name": record.process_name, "tokens": usage.total_tokens},
        )
        await self._analysis_repo.commit()
        return record.id
