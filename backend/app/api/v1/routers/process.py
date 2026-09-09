"""Process analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import AnalysisServiceDep, CurrentUserDep, PaginationDep, require_role
from app.core.security import Role
from app.schemas.common import Page
from app.schemas.process import (
    AnalysisSummary,
    ProcessAnalyzeRequest,
    ProcessAnalyzeResponse,
)
from app.schemas.roi import ROICalculationInput, ROIResult
from app.services.analysis_service import AnalysisService
from app.services.roi_service import calculate_roi

router = APIRouter(prefix="/process", tags=["Process Analysis"])


@router.post(
    "/analyze",
    response_model=ProcessAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Run the full AI analysis pipeline on a business process",
    description=(
        "Executes the Process Analyzer, Bottleneck Detection, Automation Advisor and "
        "ROI agents in sequence and returns the combined result."
    ),
)
async def analyze_process(
    payload: ProcessAnalyzeRequest,
    service: AnalysisServiceDep,
    user: CurrentUserDep,
) -> ProcessAnalyzeResponse:
    return await service.analyze(payload, user)


@router.post(
    "/roi",
    response_model=ROIResult,
    summary="Calculate ROI from baseline metrics without invoking the LLM",
    description=(
        "Runs the deterministic ROI engine that every other surface reuses. "
        "The same formulas and rounding rules power the analysis response and "
        "the executive report."
    ),
)
async def calculate_roi_endpoint(payload: ROICalculationInput) -> ROIResult:
    return calculate_roi(payload)


@router.get(
    "/analyses",
    response_model=Page[AnalysisSummary],
    summary="List analyses owned by the caller",
)
async def list_analyses(
    service: AnalysisServiceDep,
    user: CurrentUserDep,
    pagination: PaginationDep,
) -> Page[AnalysisSummary]:
    items, total = await service.list_analyses(
        user, limit=pagination.limit, offset=pagination.offset
    )
    return Page[AnalysisSummary](
        items=[AnalysisSummary.model_validate(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/analyses/{analysis_id}",
    response_model=ProcessAnalyzeResponse,
    summary="Retrieve a stored analysis",
)
async def get_analysis(
    analysis_id: str,
    service: AnalysisServiceDep,
    user: CurrentUserDep,
) -> ProcessAnalyzeResponse:
    record = await service.get_analysis(analysis_id, user)
    return AnalysisService.to_response(record)


@router.delete(
    "/analyses/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[Depends(require_role(Role.MANAGER))],
    summary="Delete a stored analysis (manager or above)",
)
async def delete_analysis(
    analysis_id: str,
    service: AnalysisServiceDep,
    user: CurrentUserDep,
) -> None:
    await service.delete_analysis(analysis_id, user)
