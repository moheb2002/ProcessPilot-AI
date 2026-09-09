"""Deterministic assembly of the executive report.

The renderer owns every number that appears in the report. The LLM narrative is
inserted as prose only, and is scanned for figures that conflict with the
validated :class:`~app.schemas.roi.ROIResult` so a divergence is always logged.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.core.logging import get_correlation_id, get_logger
from app.schemas.insight import (
    AnalysisConfidence,
    ExecutiveReport,
    QuickWin,
    RecommendationDetail,
    ReportNarrative,
    Roadmap,
    RoadmapItem,
    RoadmapPhase,
)
from app.schemas.roi import ROIResult, to_decimal

logger = get_logger(__name__)

_NUMBER_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w])")
_SENTENCE_RE = re.compile(r"[^.!?]*[.!?]|[^.!?]+$")

#: A bare number only counts as a *claimed metric* when it is presented as one: prefixed by a
#: currency symbol, followed by a unit, written with a separator/decimal, or large enough that
#: it cannot be incidental prose. This keeps "the first 2 weeks" from being treated as ROI.
_CURRENCY_PREFIX = re.compile(r"(?:[$€£]|USD|EUR|GBP)\s*$", re.IGNORECASE)
_METRIC_SUFFIX = re.compile(
    r"^\s*(?:%|percent\b|hours?\b|hrs?\b|fte\b|per month\b|per year\b|monthly\b"
    r"|annually\b|a month\b|a year\b)",
    re.IGNORECASE,
)

#: Figures that are legitimately allowed to appear in narrative prose.
_ALWAYS_ALLOWED = {Decimal(0), Decimal(12), Decimal(30), Decimal(60), Decimal(90), Decimal(100)}


def build_roadmap(
    recommendations: list[RecommendationDetail], quick_wins: list[QuickWin]
) -> Roadmap:
    """Split scored recommendations into 30 / 60 / 90 day delivery phases."""
    quick_win_ids = {qw.source_recommendation_id for qw in quick_wins}
    first = [r for r in recommendations if r.id in quick_win_ids]
    remaining = [r for r in recommendations if r.id not in quick_win_ids]
    second = [r for r in remaining if r.implementation_timeframe_days <= 60]
    third = [r for r in remaining if r.implementation_timeframe_days > 60]

    def _items(items: list[RecommendationDetail]) -> list[RoadmapItem]:
        return [
            RoadmapItem(title=r.title, description=r.description, recommendation_id=r.id)
            for r in items
        ]

    return Roadmap(
        phases=[
            RoadmapPhase(
                name="Days 0-30 — Prove value",
                window="0-30 days",
                objective=(
                    "Ship the Quick Wins, instrument the process and establish the "
                    "measurement baseline."
                ),
                items=_items(first),
            ),
            RoadmapPhase(
                name="Days 31-60 — Core automation",
                window="31-60 days",
                objective="Automate the highest-scoring remaining recommendations end to end.",
                items=_items(second),
            ),
            RoadmapPhase(
                name="Days 61-90 — Scale and optimise",
                window="61-90 days",
                objective="Extend coverage, harden exception handling and review realised value.",
                items=_items(third),
            ),
        ]
    )


def _allowed_figures(
    roi: ROIResult, confidence: AnalysisConfidence, recommendations: list[RecommendationDetail]
) -> set[Decimal]:
    allowed = set(_ALWAYS_ALLOWED)
    allowed.update(roi.fingerprint())
    allowed.add(to_decimal(confidence.score))
    for recommendation in recommendations:
        allowed.add(to_decimal(recommendation.estimated_hours_saved_per_month))
        allowed.add(to_decimal(recommendation.estimated_monthly_value))
        allowed.add(to_decimal(recommendation.estimated_annual_value))
        allowed.add(to_decimal(recommendation.recommendation_score))
        allowed.add(Decimal(recommendation.implementation_timeframe_days))
    return {value.normalize() for value in allowed}


def _is_claimed_metric(text: str, match: re.Match[str]) -> bool:
    before = text[: match.start()]
    after = text[match.end() :]
    token = match.group()
    if _CURRENCY_PREFIX.search(before) or _METRIC_SUFFIX.match(after):
        return True
    if "," in token or "." in token:
        return True
    return Decimal(token) >= 1_000


def detect_roi_conflicts(
    *,
    narrative_text: str,
    roi: ROIResult,
    confidence: AnalysisConfidence,
    recommendations: list[RecommendationDetail],
) -> list[str]:
    """Return figures the model presented as metrics that the ROI engine does not back."""
    allowed = _allowed_figures(roi, confidence, recommendations)
    conflicts: list[str] = []
    for match in _NUMBER_RE.finditer(narrative_text):
        try:
            value = Decimal(match.group().replace(",", "")).normalize()
        except (InvalidOperation, ValueError):
            continue
        if value in allowed or not _is_claimed_metric(narrative_text, match):
            continue
        conflicts.append(match.group())
    return conflicts


def sanitise_narrative(
    narrative: ReportNarrative,
    *,
    roi: ROIResult,
    confidence: AnalysisConfidence,
    recommendations: list[RecommendationDetail],
) -> tuple[ReportNarrative, list[str]]:
    """Strip any sentence stating a figure the ROI engine did not produce.

    Logging a conflict is not enough: an unbacked figure must never reach the
    reader, otherwise the report can still contradict the analysis on screen.
    """
    conflicts: list[str] = []

    def _clean(text: str) -> str:
        found = detect_roi_conflicts(
            narrative_text=text, roi=roi, confidence=confidence, recommendations=recommendations
        )
        if not found:
            return text
        conflicts.extend(found)
        kept = [
            sentence
            for sentence in _SENTENCE_RE.findall(text)
            if not detect_roi_conflicts(
                narrative_text=sentence,
                roi=roi,
                confidence=confidence,
                recommendations=recommendations,
            )
        ]
        return " ".join(part.strip() for part in kept if part.strip())

    cleaned = narrative.model_copy(
        update={
            "executive_summary": _clean(narrative.executive_summary),
            "current_state_assessment": _clean(narrative.current_state_assessment),
            "roi_interpretation": _clean(narrative.roi_interpretation),
            "executive_recommendation": _clean(narrative.executive_recommendation),
            "confidence_commentary": _clean(narrative.confidence_commentary),
            "key_pain_points": [_clean(item) for item in narrative.key_pain_points],
            "risks": [_clean(item) for item in narrative.risks],
            "dependencies": [_clean(item) for item in narrative.dependencies],
        }
    )
    return cleaned, conflicts


def _bullets(items: list[str], *, empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"_{empty}_"


def _paragraph(text: str, *, fallback: str) -> str:
    return text.strip() if text.strip() else f"_{fallback}_"


def _recommendation_block(recommendation: RecommendationDetail) -> str:
    return "\n".join(
        [
            f"#### {recommendation.id} — {recommendation.title}",
            "",
            recommendation.description,
            "",
            f"- **Priority:** {recommendation.priority.value}",
            f"- **Business impact:** {recommendation.business_impact.value}",
            f"- **Implementation effort:** {recommendation.implementation_effort.value}",
            (
                "- **Expected hours saved:** "
                f"{recommendation.estimated_hours_saved_per_month} hours/month "
                f"({recommendation.estimated_monthly_value} per month, "
                f"{recommendation.estimated_annual_value} per year)"
            ),
            "- **Recommended technology:** "
            + (", ".join(recommendation.recommended_technologies) or "To be confirmed"),
            "- **Dependencies:** " + (", ".join(recommendation.dependencies) or "None identified"),
            "- **Expected benefits:** "
            + ("; ".join(recommendation.expected_benefits) or "See description"),
            f"- **Recommendation score:** {recommendation.recommendation_score}/100 "
            f"({recommendation.score_explanation})",
        ]
    )


def render_report(
    *,
    process_name: str,
    narrative: ReportNarrative,
    roi: ROIResult,
    confidence: AnalysisConfidence,
    recommendations: list[RecommendationDetail],
    quick_wins: list[QuickWin],
    bottlenecks: list,
    roadmap: Roadmap,
) -> ExecutiveReport:
    """Compose the final Markdown report. All figures come from ``roi``."""
    narrative, conflicts = sanitise_narrative(
        narrative, roi=roi, confidence=confidence, recommendations=recommendations
    )
    if conflicts:
        logger.warning(
            "report_narrative_contains_unbacked_figures",
            extra={
                "correlation_id": get_correlation_id(),
                "process_name": process_name,
                "figures": conflicts[:10],
            },
        )

    pain_points = [point for point in narrative.key_pain_points if point] or [
        f"{b.title}: {b.impact}" for b in bottlenecks
    ]

    sections: list[str] = [
        f"# Executive Report — {process_name}",
        "",
        "## 1. Executive Summary",
        _paragraph(
            narrative.executive_summary,
            fallback="Narrative unavailable; the quantified business case below still applies.",
        ),
        "",
        "## 2. Analysis Confidence",
        f"**Score:** {confidence.score}/100 &nbsp;&nbsp; **Level:** {confidence.level.value}",
        "",
        _paragraph(narrative.confidence_commentary, fallback="No commentary provided."),
        "",
        "**Supporting evidence**",
        _bullets(confidence.reasons, empty="No supporting evidence recorded."),
        "",
        "**Missing information**",
        _bullets(confidence.missing_information, empty="No material gaps identified."),
        "",
        "## 3. Current State Assessment",
        _paragraph(narrative.current_state_assessment, fallback="Narrative unavailable."),
        "",
        f"Today the process consumes **{roi.current_monthly_hours} hours per month** of "
        f"hands-on effort.",
        "",
        "## 4. Key Pain Points",
        _bullets(pain_points, empty="No bottlenecks were evidenced by the supplied input."),
        "",
        "## 5. Quick Wins",
        _quick_wins_section(quick_wins),
        "",
        "## 6. Recommended Solutions",
        _recommendations_section(recommendations),
        "",
        "## 7. Prioritised Action Plan",
        _action_plan_section(recommendations),
        "",
        "## 8. Business Case and ROI",
        _roi_section(roi),
        "",
        _paragraph(narrative.roi_interpretation, fallback="No interpretation provided."),
        "",
        "## 9. 30-60-90 Day Roadmap",
        _roadmap_section(roadmap),
        "",
        "## 10. Risks and Dependencies",
        "**Risks**",
        _bullets(narrative.risks, empty="No delivery risks recorded."),
        "",
        "**Dependencies**",
        _bullets(
            narrative.dependencies or sorted({d for r in recommendations for d in r.dependencies}),
            empty="No external dependencies identified.",
        ),
        "",
        "## 11. Executive Recommendation",
        _paragraph(narrative.executive_recommendation, fallback="No recommendation provided."),
    ]

    return ExecutiveReport(
        markdown="\n".join(sections).strip(),
        narrative=narrative,
        roi_overridden=bool(conflicts),
    )


def _roi_section(roi: ROIResult) -> str:
    rows = [
        "| Measure | Value |",
        "| --- | --- |",
        f"| Current monthly effort | {roi.current_monthly_hours} hours |",
        f"| Automation potential | {roi.automation_potential_percentage}% |",
        f"| Estimated hours saved per month | {roi.estimated_hours_saved} hours |",
        f"| Remaining monthly effort | {roi.remaining_monthly_hours} hours |",
        f"| Monthly productivity value | {roi.monthly_productivity_value} |",
        f"| Annual productivity value | {roi.annual_productivity_value} |",
        "",
        f"**Calculation method.** {roi.calculation_method}",
        "",
        "**Assumptions**",
        _bullets(roi.assumptions, empty="No assumptions recorded."),
    ]
    return "\n".join(rows)


def _quick_wins_section(quick_wins: list[QuickWin]) -> str:
    if not quick_wins:
        return (
            "_No recommendation met the Quick Win criteria (Low/Medium effort, "
            "High/Critical impact, deliverable within 30 days, limited dependencies)._"
        )
    blocks = []
    for index, win in enumerate(quick_wins, start=1):
        blocks.append(
            "\n".join(
                [
                    f"**QW-{index}. {win.title}** ({win.implementation_timeframe})",
                    "",
                    win.description,
                    "",
                    f"- **Impact:** {win.business_impact.value} · "
                    f"**Effort:** {win.implementation_effort.value} · "
                    f"**Priority:** {win.priority.value}",
                    f"- **Hours saved:** {win.estimated_hours_saved_per_month} hours/month",
                    "- **Technology:** "
                    + (", ".join(win.recommended_technologies) or "To be confirmed"),
                    f"- **Expected outcome:** {win.expected_outcome}",
                    "- **Dependencies:** " + (", ".join(win.dependencies) or "None identified"),
                    f"- **Source recommendation:** {win.source_recommendation_id}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _recommendations_section(recommendations: list[RecommendationDetail]) -> str:
    if not recommendations:
        return "_No automation recommendations were supported by the supplied evidence._"
    return "\n\n".join(_recommendation_block(r) for r in recommendations)


def _action_plan_section(recommendations: list[RecommendationDetail]) -> str:
    if not recommendations:
        return "_Nothing to sequence until recommendations are available._"
    rows = [
        "| # | Recommendation | Priority | Impact | Effort | Hours saved/month | Score |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for position, r in enumerate(recommendations, start=1):
        rows.append(
            f"| {position} | {r.title} | {r.priority.value} | {r.business_impact.value} | "
            f"{r.implementation_effort.value} | {r.estimated_hours_saved_per_month} | "
            f"{r.recommendation_score} |"
        )
    return "\n".join(rows)


def _roadmap_section(roadmap: Roadmap) -> str:
    blocks = []
    for phase in roadmap.phases:
        items = [f"{item.recommendation_id} — {item.title}" for item in phase.items]
        blocks.append(
            "\n".join(
                [
                    f"### {phase.name}",
                    phase.objective,
                    "",
                    _bullets(items, empty="No work scheduled in this phase."),
                ]
            )
        )
    return "\n\n".join(blocks)
