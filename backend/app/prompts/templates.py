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
    version="1.0.0",
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
- Mark `is_manual` true when a human performs the work without system automation.
- `manual_tasks` lists the names of repetitive or copy/paste style human tasks.
- `approvals` lists every approval or sign-off gate.
- Use "" or [] when information is genuinely absent. Never use null.

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
    version="1.0.0",
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
- Return between 3 and 7 bottlenecks, ordered from most to least severe.
- `severity` must be exactly one of: low, medium, high, critical.
- `impact` must reference cycle time, cost, quality, risk or employee experience.

STRUCTURED PROCESS MODEL:
$process_analysis
""",
)


AUTOMATION_ADVISOR_PROMPT = PromptTemplate(
    name="automation_advisor",
    version="1.0.0",
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
- Return between 3 and 6 opportunities, ordered by value-to-effort ratio.
- `implementation_effort` must be exactly one of: low, medium, high.
- Each opportunity must trace back to a specific bottleneck or manual task.

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
    version="1.0.0",
    system=(
        "You are a principal management consultant writing for a C-level audience. "
        "You write in crisp, quantified, decision-oriented prose. You output Markdown."
    ),
    user="""Write an executive report for the process transformation described below.

Use exactly these Markdown H2 sections, in this order:

## Current State
## Key Pain Points
## Recommended Solutions
## Expected Benefits
## ROI
## Implementation Roadmap

Rules:
- Open with a one-paragraph executive overview before the first heading.
- Quantify wherever the supplied data allows; never invent numbers that contradict the ROI data.
- "Implementation Roadmap" must contain three phases: Quick Wins (0-30 days),
  Core Automation (1-3 months), Scale & Optimise (3-6 months).
- Keep the total length under 900 words. Output Markdown only, no code fences.

PROCESS NAME: $process_name

STRUCTURED PROCESS MODEL:
$process_analysis

BOTTLENECKS:
$bottlenecks

AUTOMATION OPPORTUNITIES:
$opportunities

ROI ANALYSIS:
$roi
""",
)
