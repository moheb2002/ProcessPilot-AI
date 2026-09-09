"""Deterministic analysis-confidence scoring.

The LLM may *explain* a confidence score but never produces one. Points are
awarded from observable evidence in the request and in the structured process
model, using the weights in :mod:`app.core.scoring_config`.
"""

from __future__ import annotations

from app.core.logging import get_correlation_id, get_logger
from app.core.scoring_config import CONFIDENCE_WEIGHTS, ConfidenceWeights
from app.schemas.agent import Bottleneck, ProcessAnalysis
from app.schemas.insight import AnalysisConfidence, ConfidenceLevel
from app.schemas.roi import ROICalculationInput

logger = get_logger(__name__)


def _level_for(score: float, weights: ConfidenceWeights) -> ConfidenceLevel:
    if score >= weights.high_threshold:
        return ConfidenceLevel.HIGH
    if score >= weights.medium_threshold:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def calculate_confidence(
    *,
    description: str,
    analysis: ProcessAnalysis,
    bottlenecks: list[Bottleneck],
    roi_input: ROICalculationInput | None,
    document_context: str = "",
    weights: ConfidenceWeights = CONFIDENCE_WEIGHTS,
) -> AnalysisConfidence:
    """Score how much evidence supports the analysis, on a 0-100 scale."""
    reasons: list[str] = []
    missing: list[str] = []
    score = 0.0

    # 1. Process description completeness -------------------------------------
    text_length = len(description.strip()) + len(document_context.strip())
    max_points = weights.process_description_completeness
    if text_length >= weights.description_good_chars:
        score += max_points
        reasons.append("The process description is detailed enough to model each step.")
    elif text_length >= weights.description_min_chars:
        score += max_points * 0.6
        reasons.append("The process description covers the main flow but lacks depth.")
        missing.append("A fuller narrative covering exceptions, hand-offs and edge cases.")
    else:
        score += max_points * 0.2
        missing.append("A substantially longer process description or supporting documents.")

    # 2. Operational metrics availability --------------------------------------
    max_points = weights.operational_metrics_availability
    timed_steps = [s for s in analysis.steps if s.estimated_minutes]
    if roi_input is not None and timed_steps:
        score += max_points
        reasons.append("Baseline volume, handling time and per-step durations are available.")
    elif roi_input is not None:
        score += max_points * 0.7
        reasons.append("Baseline volume and handling time were supplied for the whole process.")
        missing.append("Per-step cycle times to validate where effort actually accumulates.")
    else:
        missing.append("Monthly volume, minutes per case and hourly cost.")

    # 3. Clear actors and systems ----------------------------------------------
    max_points = weights.actors_and_systems
    has_actors = len(analysis.actors) >= weights.actors_full_credit
    has_systems = len(analysis.systems) >= weights.systems_full_credit
    if has_actors and has_systems:
        score += max_points
        reasons.append("Actors and systems of record are explicitly identified.")
    elif analysis.actors or analysis.systems:
        score += max_points * 0.5
        missing.append("A complete list of participating teams and systems of record.")
    else:
        missing.append("Any identification of the actors and systems involved.")

    # 4. Clearly detected process steps ----------------------------------------
    max_points = weights.detected_process_steps
    step_count = len(analysis.steps)
    if step_count >= weights.steps_full_credit:
        score += max_points
        reasons.append(f"{step_count} discrete process steps were detected.")
    elif step_count >= weights.steps_partial_credit:
        score += max_points * 0.6
        missing.append("A more granular breakdown of the process steps.")
    else:
        score += max_points * 0.2
        missing.append("A step-by-step description of how work actually flows.")

    # 5. Clearly detected bottlenecks ------------------------------------------
    max_points = weights.detected_bottlenecks
    if len(bottlenecks) >= weights.bottlenecks_full_credit:
        score += max_points
        reasons.append(f"{len(bottlenecks)} bottlenecks were evidenced by the process model.")
    elif len(bottlenecks) >= weights.bottlenecks_partial_credit:
        score += max_points * 0.5
        missing.append("Evidence of additional delay, rework or control weaknesses.")
    else:
        missing.append("Observable bottlenecks; none could be evidenced from the input.")

    # 6. ROI input completeness -------------------------------------------------
    max_points = weights.roi_inputs_completeness
    if roi_input is None:
        missing.append("Complete ROI inputs (volume, minutes per case and hourly cost).")
    elif roi_input.hourly_cost > 0:
        score += max_points
        reasons.append("A fully loaded hourly cost was supplied, so financial value is grounded.")
    else:
        score += max_points * 0.5
        missing.append("A fully loaded hourly cost; monetary value cannot be quantified without it.")

    final_score = round(min(max(score, 0.0), 100.0), 1)
    confidence = AnalysisConfidence(
        score=final_score,
        level=_level_for(final_score, weights),
        reasons=reasons,
        missing_information=missing,
    )
    logger.info(
        "confidence_calculated",
        extra={
            "correlation_id": get_correlation_id(),
            "score": confidence.score,
            "level": confidence.level.value,
            "missing_count": len(confidence.missing_information),
        },
    )
    return confidence
