"""Deterministic offline LLM used for the MVP, local dev and tests."""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.schemas.agent import TokenUsage

logger = get_logger(__name__)

_MANUAL_HINTS = (
    "manual", "by hand", "copy", "paste", "re-key", "rekey", "retype",
    "spreadsheet", "excel", "email", "phone", "print", "scan", "fax",
)
_APPROVAL_HINTS = ("approve", "approval", "sign-off", "sign off", "authorise", "authorize", "review")
_SYSTEM_HINTS = (
    "sap", "salesforce", "servicenow", "sharepoint", "outlook", "teams", "dynamics",
    "workday", "oracle", "jira", "excel", "crm", "erp", "active directory",
)
_ACTOR_HINTS = (
    "hr", "manager", "employee", "finance", "it", "analyst", "customer",
    "supervisor", "vendor", "admin", "legal", "procurement",
)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 3]


def _found(text: str, hints: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [h.upper() if len(h) <= 3 else h.title() for h in hints if h in lowered]


class MockLLMClient:
    """Heuristic stand-in that satisfies the :class:`LLMClient` protocol."""

    async def complete_json(
        self, *, system: str, user: str, template_name: str
    ) -> tuple[dict[str, Any], TokenUsage]:
        logger.info("mock_llm_call", extra={"template": template_name})
        builder = {
            "process_analysis": self._process_analysis,
            "bottleneck_detection": self._bottlenecks,
            "automation_advisor": self._opportunities,
            "roi_strategy": self._roi_strategy,
        }.get(template_name)
        if builder is None:
            return {}, self._usage(user)
        return builder(user), self._usage(user)

    async def complete_text(
        self, *, system: str, user: str, template_name: str
    ) -> tuple[str, TokenUsage]:
        logger.info("mock_llm_call", extra={"template": template_name})
        return self._executive_report(user), self._usage(user)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _usage(user: str) -> TokenUsage:
        approx = max(1, len(user) // 4)
        return TokenUsage(prompt_tokens=approx, completion_tokens=approx // 3, total_tokens=approx + approx // 3)

    @staticmethod
    def _extract_field(user: str, label: str) -> str:
        # Sections end at the next upper-case heading, e.g. "SUPPORTING DOCUMENT CONTEXT (…):".
        pattern = rf"{re.escape(label)}:\s*\n?(.*?)(?:\n[A-Z][A-Z0-9 _-]*(?:\([^)]*\))?:|\Z)"
        match = re.search(pattern, user, re.S)
        return match.group(1).strip() if match else ""

    # ------------------------------------------------------------- generators
    def _process_analysis(self, user: str) -> dict[str, Any]:
        name = self._extract_field(user, "PROCESS NAME") or "Untitled Process"
        description = self._extract_field(user, "PROCESS DESCRIPTION")
        sentences = _sentences(description)[:12] or ["Process described at a high level."]

        steps = []
        manual_tasks = []
        for index, sentence in enumerate(sentences, start=1):
            is_manual = any(hint in sentence.lower() for hint in _MANUAL_HINTS)
            step_name = " ".join(sentence.split()[:8]).rstrip(".,")
            steps.append(
                {
                    "order": index,
                    "name": step_name,
                    "description": sentence,
                    "actor": (_found(sentence, _ACTOR_HINTS) or ["Process Owner"])[0],
                    "system": (_found(sentence, _SYSTEM_HINTS) or [""])[0],
                    "is_manual": is_manual,
                    "estimated_minutes": 15.0 if is_manual else 5.0,
                }
            )
            if is_manual:
                manual_tasks.append(step_name)

        return {
            "process_name": name.splitlines()[0].strip(),
            "actors": sorted(set(_found(description, _ACTOR_HINTS))) or ["Process Owner"],
            "systems": sorted(set(_found(description, _SYSTEM_HINTS))),
            "steps": steps,
            "approvals": [s for s in sentences if any(h in s.lower() for h in _APPROVAL_HINTS)],
            "manual_tasks": manual_tasks,
        }

    def _bottlenecks(self, user: str) -> dict[str, Any]:
        return {
            "bottlenecks": [
                {
                    "title": "Manual data re-entry across systems",
                    "severity": "high",
                    "impact": "Adds cycle time per transaction and introduces avoidable data-quality errors.",
                    "recommendation": "Replace re-keying with a Power Automate flow writing directly to the system of record.",
                },
                {
                    "title": "Sequential approval chain",
                    "severity": "high",
                    "impact": "Approvals sit idle in inboxes, dominating end-to-end elapsed time.",
                    "recommendation": "Move approvals into Teams-based Power Automate approvals with auto-approve thresholds and escalation.",
                },
                {
                    "title": "Unstructured email hand-offs",
                    "severity": "medium",
                    "impact": "No SLA visibility and requests are lost or duplicated between teams.",
                    "recommendation": "Introduce a Power Apps intake form backed by a tracked queue.",
                },
                {
                    "title": "Document review performed by hand",
                    "severity": "medium",
                    "impact": "Reviewers spend time locating fields instead of exercising judgement.",
                    "recommendation": "Use Azure Document Intelligence to pre-extract fields and flag exceptions only.",
                },
                {
                    "title": "Tribal knowledge is undocumented",
                    "severity": "low",
                    "impact": "Onboarding new staff is slow and outcomes vary by individual.",
                    "recommendation": "Index SOPs in Azure AI Search and surface answers through Microsoft 365 Copilot.",
                },
            ]
        }

    def _opportunities(self, user: str) -> dict[str, Any]:
        return {
            "opportunities": [
                {
                    "solution": "Automated approval routing with escalation and audit trail",
                    "technology": "Power Automate + Microsoft Teams",
                    "business_value": "Cuts approval wait time and gives managers a single place to act.",
                    "implementation_effort": "low",
                },
                {
                    "solution": "Structured intake form replacing email requests",
                    "technology": "Power Apps + Dataverse",
                    "business_value": "Eliminates incomplete submissions and provides SLA reporting.",
                    "implementation_effort": "low",
                },
                {
                    "solution": "Document field extraction with human-in-the-loop exception review",
                    "technology": "Azure AI Document Intelligence",
                    "business_value": "Removes manual reading and typing of document fields.",
                    "implementation_effort": "medium",
                },
                {
                    "solution": "Grounded assistant over policies and SOPs",
                    "technology": "Azure OpenAI + Azure AI Search",
                    "business_value": "Answers policy questions instantly and reduces escalations to subject-matter experts.",
                    "implementation_effort": "medium",
                },
                {
                    "solution": "In-flow drafting and summarisation for case handlers",
                    "technology": "Microsoft 365 Copilot",
                    "business_value": "Reduces time spent writing status updates and summaries.",
                    "implementation_effort": "low",
                },
            ]
        }

    def _roi_strategy(self, user: str) -> dict[str, Any]:
        return {
            "automation_rate": 0.55,
            "rationale": "Routine data entry and routing are highly automatable; judgement steps and exceptions remain manual.",
            "assumptions": [
                "Exception rate of roughly 15% still requires human handling.",
                "Systems of record expose APIs or supported connectors.",
            ],
        }

    def _executive_report(self, user: str) -> str:
        name = self._extract_field(user, "PROCESS NAME").splitlines()[0].strip() or "the process"
        roi = self._extract_field(user, "ROI ANALYSIS")
        return f"""{name} is currently delivered through a mix of manual data entry, email-based hand-offs and sequential approvals. The analysis below summarises the current state, the constraints limiting throughput, and a phased Microsoft-first automation plan with the associated business case.

## Current State
Work arrives through unstructured channels and is progressed by individuals re-keying data between systems of record. Progress is tracked informally, so there is no reliable measure of cycle time or backlog.

## Key Pain Points
- Manual re-entry of the same data into multiple systems.
- Approvals queued sequentially in personal inboxes with no escalation path.
- Unstructured intake causing rework and lost requests.
- Document review performed entirely by hand.
- Undocumented tribal knowledge slowing onboarding.

## Recommended Solutions
- **Power Automate + Teams** for approval routing, escalation and audit trail.
- **Power Apps** for structured intake with validation at the point of capture.
- **Azure AI Document Intelligence** for field extraction with exception-only review.
- **Azure OpenAI + Azure AI Search** for a grounded assistant over policies and SOPs.
- **Microsoft 365 Copilot** for in-flow drafting and summarisation.

## Expected Benefits
Reduced end-to-end cycle time, fewer data-quality defects, measurable SLA reporting, and capacity released back to higher-value work.

## ROI
{roi or "ROI metrics were not supplied for this analysis."}

## Implementation Roadmap
**Quick Wins (0-30 days).** Deploy the Power Apps intake form and Power Automate approval routing; instrument baseline cycle-time metrics.

**Core Automation (1-3 months).** Integrate the systems of record, add Document Intelligence extraction with exception review, and retire the manual re-keying steps.

**Scale & Optimise (3-6 months).** Roll out the grounded assistant and Copilot experiences, extend the pattern to adjacent processes, and establish continuous monitoring of throughput and savings.
"""
