"""Versioned prompt templates for each ProcessPilot agent."""

from __future__ import annotations

from dataclasses import dataclass
from string import Template


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """A named system/user prompt pair rendered with ``$placeholder`` substitution."""

    name: str
    version: str
    system: str
    user: str

    def render(self, **kwargs: object) -> tuple[str, str]:
        return self.system, Template(self.user).safe_substitute(**kwargs)


_MICROSOFT_CATALOG = """Prioritise these Microsoft technologies, in this order of preference:
- Microsoft 365 Copilot (in-flow assistance, drafting, summarisation)
- Power Automate (workflow, approvals, connectors, RPA for legacy UIs)
- Power Apps (lightweight custom front-ends and intake forms)
- Azure AI Foundry / Azure OpenAI (reasoning, extraction, classification, generation)
- Azure AI Search (retrieval over policy/SOP corpora)
- Azure Document Intelligence (structured extraction from PDFs, forms, invoices)
- Microsoft Graph (people, calendar, mail, Teams integration)
Only propose a non-Microsoft option when no Microsoft service can meet the requirement."""


PROCESS_ANALYSIS_PROMPT = PromptTemplate(
    name="process_analysis",
  version="1.1.0",
    system=(
        "You are a Microsoft-certified business process analyst. You decompose narrative "
        "process descriptions into precise, structured process models. You never invent "
        "systems or actors that are not implied by the source material. "
        "Respond with a single JSON object and nothing else."
    ),
    user="""Analyse the business process below and return JSON matching exactly this schema:

{
  "process_name": "string",
  "actors": ["string"],
  "systems": ["string"],
  "steps": [
    {
      "order": 1,
      "name": "string",
      "description": "string",
      "actor": "string",
      "system": "string",
      "is_manual": true,
      "estimated_minutes": 0
    }
  ],
  "approvals": ["string"],
  "manual_tasks": ["string"]
}

Rules:
- Steps must be ordered sequentially starting at 1.
- Every step must be supported by the process description or supporting documents.
- Preserve explicit actors, systems, decisions, delays and hand-offs from the source.
- Mark `is_manual` true when a human performs the work without system automation.
- `manual_tasks` lists the names of repetitive or copy/paste style human tasks.
- `approvals` lists every approval or sign-off gate.
- Do not infer durations. Use null for `estimated_minutes` unless the source states a duration.
- Use "" or [] for other genuinely absent information.

PROCESS NAME:
$process_name

PROCESS DESCRIPTION:
$description

SUPPORTING DOCUMENT CONTEXT (may be empty):
$document_context
""",
)


BOTTLENECK_DETECTION_PROMPT = PromptTemplate(
    name="bottleneck_detection",
  version="1.1.0",
    system=(
        "You are a lean/six-sigma operations consultant specialising in identifying "
        "delays, rework loops, hand-off friction and control weaknesses in business "
        "processes. Respond with a single JSON object and nothing else."
    ),
    user="""Given the structured process model below, identify the highest-impact bottlenecks.

Return JSON matching exactly this schema:

{
  "bottlenecks": [
    {
      "title": "string",
      "severity": "low|medium|high|critical",
      "impact": "string describing measurable business impact",
      "recommendation": "string describing the concrete fix"
    }
  ]
}

Rules:
- Return at most 7 distinct bottlenecks, ordered from most to least severe.
- Return an empty list when the process model does not support a bottleneck.
- `severity` must be exactly one of: low, medium, high, critical.
- Tie each bottleneck to specific steps, hand-offs, delays or controls in the process model.
- `impact` must explain the supported effect on cycle time, cost, quality, risk or employee
  experience. Never invent quantities, frequencies or monetary values.
- `recommendation` must address the stated cause rather than only restating the symptom.

STRUCTURED PROCESS MODEL:
$process_analysis
""",
)


AUTOMATION_ADVISOR_PROMPT = PromptTemplate(
    name="automation_advisor",
  version="1.1.0",
    system=(
        "You are a Microsoft AI solution architect who maps operational pain points to "
        "concrete Microsoft platform capabilities with realistic effort estimates. "
        "Respond with a single JSON object and nothing else.\n\n" + _MICROSOFT_CATALOG
    ),
    user="""Recommend AI and automation opportunities for the process and bottlenecks below.

Return JSON matching exactly this schema:

{
  "opportunities": [
    {
      "solution": "string - what to build",
      "technology": "string - the Microsoft service(s) used",
      "business_value": "string - the outcome in business terms",
      "implementation_effort": "low|medium|high"
    }
  ]
}

Rules:
- Return at most 6 distinct opportunities, ordered by value-to-effort ratio.
- Return an empty list when no opportunity is supported by the supplied evidence.
- `implementation_effort` must be exactly one of: low, medium, high.
- Each opportunity must explicitly identify the bottleneck or manual task it addresses.
- State concrete prerequisites or integration constraints in `business_value` when they affect
  feasibility. Do not assume APIs, connectors, data quality or licensing are available.
- Do not claim quantified savings here; ROI is calculated separately from supplied baseline data.

STRUCTURED PROCESS MODEL:
$process_analysis

IDENTIFIED BOTTLENECKS:
$bottlenecks
""",
)


ROI_STRATEGY_PROMPT = PromptTemplate(
    name="roi_strategy",
    version="1.0.0",
    system=(
        "You are a business value engineer. You estimate automation potential "
        "conservatively and justify every assumption. "
        "Respond with a single JSON object and nothing else."
    ),
    user="""Estimate the realistic automation rate for the process below.

Return JSON matching exactly this schema:

{
  "automation_rate": 0.0,
  "rationale": "string",
  "assumptions": ["string"]
}

Rules:
- `automation_rate` is the fraction (0.0-1.0) of current effort that automation can remove.
- Be conservative: full straight-through processing is rare. Typical range is 0.3-0.7.

STRUCTURED PROCESS MODEL:
$process_analysis

AUTOMATION OPPORTUNITIES:
$opportunities

BASELINE METRICS:
Monthly volume: $monthly_volume
Minutes per transaction: $minutes_per_transaction
Employee hourly rate: $employee_hourly_rate
""",
)


EXECUTIVE_SUMMARY_PROMPT = PromptTemplate(
    name="executive_summary",
    version="2.0.0",
    system=(
        "You are a principal management consultant writing for a CIO, COO, operations "
        "manager or transformation leader. You write crisp, decision-oriented prose.\n\n"
        "CRITICAL CONSTRAINT: every financial and effort figure has already been calculated "
        "deterministically by the ProcessPilot ROI engine and is supplied to you as fact. "
        "You must NOT calculate, estimate, re-derive, adjust, round, annualise or restate "
        "any number. Do not introduce hours, percentages, currency amounts, headcount or "
        "payback periods that are not present verbatim in the supplied ROI facts. "
        "Your job is business interpretation of the supplied numbers, not arithmetic.\n\n"
        "Respond with a single JSON object and nothing else."
    ),
    user="""Write the narrative sections of an executive report for the transformation below.

Return JSON matching exactly this schema:

{
  "executive_summary": "string - 3 to 5 sentences framing the opportunity and the ask",
  "current_state_assessment": "string - how the process runs today and why it constrains the business",
  "key_pain_points": ["string - one concrete, evidenced pain point per entry"],
  "roi_interpretation": "string - what the supplied ROI figures mean for the business",
  "risks": ["string - delivery, adoption, data or compliance risks"],
  "dependencies": ["string - prerequisites outside the delivery team's control"],
  "executive_recommendation": "string - the decision you are asking the leadership team to take",
  "confidence_commentary": "string - explain what the supplied confidence score reflects"
}

Rules:
- Write in a professional consulting tone. No marketing language, no hedging.
- Reuse the supplied ROI figures verbatim when you reference them. Never recompute them.
- Never state a number that is absent from the ROI FACTS block below.
- `roi_interpretation` must not repeat the arithmetic; explain the operational meaning
  (recovered capacity, redeployment options, what the remaining hours are spent on).
- `confidence_commentary` must explain the supplied score. Do not propose a different score.
- Ground every pain point in the supplied process model or bottlenecks.
- Keep each string under 150 words. Output JSON only, no code fences.

PROCESS NAME: $process_name

STRUCTURED PROCESS MODEL:
$process_analysis

BOTTLENECKS:
$bottlenecks

SCORED RECOMMENDATIONS (priority, impact and score are already final):
$recommendations

QUICK WINS (already selected by the backend):
$quick_wins

ANALYSIS CONFIDENCE (calculated by the backend; do not change it):
$confidence

ROI FACTS — AUTHORITATIVE, DO NOT RECALCULATE:
Current monthly effort: $current_monthly_hours hours
Estimated hours saved per month: $estimated_hours_saved hours
Remaining monthly effort: $remaining_monthly_hours hours
Monthly productivity value: $monthly_productivity_value
Annual productivity value: $annual_productivity_value
Automation potential: $automation_potential_percentage%

ROI ASSUMPTIONS:
$roi_assumptions
""",
)

