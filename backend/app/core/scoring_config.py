"""Configurable, deterministic scoring constants.

Every number that influences a confidence score, a recommendation score or a
Quick Win selection lives here so the business logic stays auditable and the
LLM is never asked to invent a weighting.

All values are plain data (no I/O) so they can be imported from pure functions
and overridden in tests via ``dataclasses.replace``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


# --------------------------------------------------------------------------- #
# Confidence scoring
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ConfidenceWeights:
    """Maximum points awarded per evidence category. Must sum to 100."""

    process_description_completeness: int = 25
    operational_metrics_availability: int = 25
    actors_and_systems: int = 15
    detected_process_steps: int = 15
    detected_bottlenecks: int = 10
    roi_inputs_completeness: int = 10

    #: Thresholds used to award the description-completeness bucket.
    description_min_chars: int = 200
    description_good_chars: int = 600

    #: A process model with at least this many steps is considered well detected.
    steps_full_credit: int = 8
    steps_partial_credit: int = 4

    #: Bottleneck counts required for full/partial credit.
    bottlenecks_full_credit: int = 3
    bottlenecks_partial_credit: int = 1

    #: Distinct actors/systems required for full credit.
    actors_full_credit: int = 3
    systems_full_credit: int = 2

    high_threshold: float = 90.0
    medium_threshold: float = 70.0

    def total(self) -> int:
        return (
            self.process_description_completeness
            + self.operational_metrics_availability
            + self.actors_and_systems
            + self.detected_process_steps
            + self.detected_bottlenecks
            + self.roi_inputs_completeness
        )


CONFIDENCE_WEIGHTS = ConfidenceWeights()


# --------------------------------------------------------------------------- #
# Recommendation scoring
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class RecommendationScoringConfig:
    """Numeric values behind ``(impact + frequency + risk) / effort``."""

    business_impact: dict[str, int] = field(
        default_factory=lambda: {"critical": 4, "high": 3, "medium": 2, "low": 1}
    )
    implementation_effort: dict[str, int] = field(
        default_factory=lambda: {"low": 1, "medium": 2, "high": 3}
    )
    frequency: dict[str, int] = field(
        default_factory=lambda: {"very high": 4, "high": 3, "medium": 2, "low": 1}
    )
    risk_reduction: dict[str, int] = field(
        default_factory=lambda: {"critical": 4, "high": 3, "medium": 2, "low": 1}
    )

    #: Best achievable raw score: (4 + 4 + 4) / 1 == 12. Used to normalise to 0-100.
    max_raw_score: float = 12.0
    #: Worst achievable raw score: (1 + 1 + 1) / 3 == 1.
    min_raw_score: float = 1.0

    #: Priority bands applied to the normalised 0-100 score.
    priority_critical_min: float = 80.0
    priority_high_min: float = 60.0
    priority_medium_min: float = 35.0


RECOMMENDATION_SCORING = RecommendationScoringConfig()


# --------------------------------------------------------------------------- #
# Quick Win selection
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class QuickWinRules:
    """A recommendation must satisfy *all* of these to qualify as a Quick Win."""

    allowed_efforts: frozenset[str] = frozenset({"low", "medium"})
    allowed_impacts: frozenset[str] = frozenset({"critical", "high"})
    max_timeframe_days: int = 30
    max_dependencies: int = 2
    max_results: int = 3

    #: Default delivery window suggested per effort level, in days.
    timeframe_by_effort: dict[str, int] = field(
        default_factory=lambda: {"low": 14, "medium": 30, "high": 90}
    )


QUICK_WIN_RULES = QuickWinRules()


# --------------------------------------------------------------------------- #
# ROI defaults
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ROIDefaults:
    """Fallbacks used only when no automation potential can be obtained."""

    #: Conservative percentage applied when neither the caller nor the model supplies one.
    automation_potential_percentage: Decimal = Decimal(50)
    #: Equivalent 0-1 rate used to repair an unparseable model response.
    automation_rate: float = 0.5


ROI_DEFAULTS = ROIDefaults()


# --------------------------------------------------------------------------- #
# Savings allocation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SavingsAllocationConfig:
    """Controls how the overall ROI hours are split across recommendations."""

    #: When ``True`` an over-allocation raises instead of being normalised.
    strict: bool = False
    #: Tolerance (hours) absorbing the half-cent of drift introduced by rounding
    #: each recommendation's share to two decimal places.
    tolerance_hours: Decimal = Decimal("0.01")
    assumption: str = (
        "Recommendation-level hours saved are directional estimates apportioned from the "
        "overall automation potential. They are not additive with each other beyond the "
        "total estimated hours saved, because several recommendations address overlapping "
        "manual effort."
    )


SAVINGS_ALLOCATION = SavingsAllocationConfig()
