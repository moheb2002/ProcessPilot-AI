"""Executive report endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, ReportServiceDep
from app.schemas.report import ReportGenerateRequest, ReportGenerateResponse

router = APIRouter(prefix="/report", tags=["Executive Report"])


@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    summary="Generate a consultant-style executive report",
    description=(
        "Supply `analysis_id` to report on a stored analysis, or pass the analysis, "
        "bottlenecks, opportunities and ROI inline."
    ),
)
async def generate_report(
    payload: ReportGenerateRequest,
    service: ReportServiceDep,
    user: CurrentUserDep,
) -> ReportGenerateResponse:
    return await service.generate(payload, user)
