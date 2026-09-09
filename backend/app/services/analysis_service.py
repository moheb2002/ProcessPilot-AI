"""Analysis orchestration: runs the agent pipeline and persists the result."""

from __future__ import annotations

import time
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
from app.models.roi import ROIResult
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
    ROIResultSchema,
    TokenUsage,
)
from app.schemas.process import ProcessAnalyzeRequest, ProcessAnalyzeResponse
from app.schemas.user import CurrentUser
from app.services.azure_openai import LLMClient

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
        roi, step_usage = await self._roi.run(
            roi_input=roi_input,
            analysis=analysis,
            opportunities=automation_plan.opportunities,
        )
        usage += step_usage

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "analysis_pipeline_completed",
            extra={
                "process_name": request.process_name,
                "total_tokens": usage.total_tokens,
                "duration_ms": duration_ms,
            },
        )

        analysis_id: str | None = None
        if request.persist:
            analysis_id = await self._persist(
                request=request,
                user=user,
                analysis=analysis,
                bottlenecks=bottleneck_report.bottlenecks,
                opportunities=automation_plan.opportunities,
                roi_input=roi_input,
                roi=roi,
                usage=usage,
                duration_ms=duration_ms,
            )

        return ProcessAnalyzeResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.COMPLETED,
            analysis=analysis,
            bottlenecks=bottleneck_report.bottlenecks,
            opportunities=automation_plan.opportunities,
            roi=roi,
            total_tokens=usage.total_tokens,
            duration_ms=duration_ms,
        )

    async def get_analysis(self, analysis_id: str, user: CurrentUser) -> Analysis:
        analysis = await self._analysis_repo.get(analysis_id)
        if analysis is None or analysis.owner_id != user.id:
            raise NotFoundError(f"Analysis '{analysis_id}' was not found.")
        return analysis

    async def list_analyses(
        self, user: CurrentUser, *, limit: int, offset: int
    ) -> tuple[Sequence[Analysis], int]:
        items = await self._analysis_repo.list_for_owner(user.id, limit=limit, offset=offset)
        total = await self._analysis_repo.count(owner_id=user.id)
        return items, total

    async def attach_report(self, analysis: Analysis, report: str, tokens: int) -> None:
        analysis.executive_report = report
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
        analysis: ProcessAnalysis,
        bottlenecks: list[Bottleneck],
        opportunities: list[AutomationOpportunity],
        roi_input: ROIInput,
        roi: ROIResultSchema,
        usage: TokenUsage,
        duration_ms: int,
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

        record = Analysis(
            status=AnalysisStatus.COMPLETED,
            process_name=analysis.process_name or request.process_name,
            analysis_payload=analysis.model_dump(mode="json"),
            bottlenecks_payload=[b.model_dump(mode="json") for b in bottlenecks],
            total_tokens=usage.total_tokens,
            duration_ms=duration_ms,
            owner_id=user.id,
            process_id=process.id,
        )
        record.recommendations = [
            Recommendation(
                solution=item.solution,
                technology=item.technology,
                business_value=item.business_value,
                implementation_effort=str(item.implementation_effort),
            )
            for item in opportunities
        ]
        record.roi_result = ROIResult(
            monthly_volume=roi_input.monthly_volume,
            minutes_per_transaction=roi_input.minutes_per_transaction,
            employee_hourly_rate=roi_input.employee_hourly_rate,
            automation_rate=roi_input.automation_rate,
            current_hours=roi.current_hours,
            estimated_hours_saved=roi.estimated_hours_saved,
            monthly_savings=roi.monthly_savings,
            annual_savings=roi.annual_savings,
            roi_score=roi.roi_score,
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
