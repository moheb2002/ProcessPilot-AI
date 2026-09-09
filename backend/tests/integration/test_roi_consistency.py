"""End-to-end guarantee: the analysis ROI and the report ROI are the same object.

These tests are the regression net for the original defect, where the analysis
UI showed 44 hours / $1,232 while the executive report showed 40 hours / $1,120.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

ANALYZE_PAYLOAD = {
    "process_name": "Purchase Approval Process",
    "description": (
        "Requesters email a purchase request to Procurement, who manually re-key the details "
        "into SAP. The line manager approves by email, then Finance provides a second approval. "
        "Procurement copies the approved order into the supplier portal by hand and tracks "
        "progress in an Excel spreadsheet."
    ),
    "roi_input": {
        "monthly_volume": 120,
        "minutes_per_case": 40,
        "hourly_cost": 28,
        "automation_potential_percentage": 55,
    },
    "persist": True,
}

ROI_KEYS = (
    "current_monthly_hours",
    "estimated_hours_saved",
    "remaining_monthly_hours",
    "monthly_productivity_value",
    "annual_productivity_value",
    "automation_potential_percentage",
)

#: The contract the analysis endpoint and the report endpoint must both satisfy
#: for the reference purchase-approval inputs.
EXPECTED_ROI = {
    "current_monthly_hours": 80,
    "estimated_hours_saved": 44,
    "remaining_monthly_hours": 36,
    "monthly_productivity_value": 1232,
    "annual_productivity_value": 14784,
    "automation_potential_percentage": 55,
}


async def test_reference_payload_matches_the_published_contract(client: AsyncClient) -> None:
    """Both endpoints must return exactly the documented figures, to the cent."""
    analysis = (await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)).json()
    report = (
        await client.post(
            "/api/v1/report/generate", json={"analysis_id": analysis["analysis_id"]}
        )
    ).json()
    standalone = (
        await client.post("/api/v1/process/roi", json=ANALYZE_PAYLOAD["roi_input"])
    ).json()

    for source in (analysis["roi"], report["roi"], standalone):
        actual = {key: source[key] for key in EXPECTED_ROI}
        assert actual == EXPECTED_ROI
        for key, expected in EXPECTED_ROI.items():
            assert Decimal(str(source[key])) == Decimal(expected)


async def test_analysis_roi_equals_report_roi(client: AsyncClient) -> None:
    analysis = await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)
    assert analysis.status_code == 200
    analysis_body = analysis.json()
    analysis_roi = analysis_body["roi"]

    # The supplied automation potential must be honoured exactly.
    assert analysis_roi["current_monthly_hours"] == 80
    assert analysis_roi["estimated_hours_saved"] == 44
    assert analysis_roi["remaining_monthly_hours"] == 36
    assert analysis_roi["monthly_productivity_value"] == 1232.0
    assert analysis_roi["annual_productivity_value"] == 14784.0
    assert analysis_roi["automation_potential_percentage"] == 55

    report = await client.post(
        "/api/v1/report/generate", json={"analysis_id": analysis_body["analysis_id"]}
    )
    assert report.status_code == 200
    report_body = report.json()

    assert {k: report_body["roi"][k] for k in ROI_KEYS} == {
        k: analysis_roi[k] for k in ROI_KEYS
    }
    # ...and the rendered Markdown states those same numbers.
    markdown = report_body["report"]
    assert "| Current monthly effort | 80 hours |" in markdown
    assert "| Estimated hours saved per month | 44 hours |" in markdown
    assert "| Remaining monthly effort | 36 hours |" in markdown
    assert "| Monthly productivity value | 1232.00 |" in markdown
    assert "| Annual productivity value | 14784.00 |" in markdown
    assert "| Automation potential | 55% |" in markdown


async def test_stored_analysis_roi_survives_a_round_trip(client: AsyncClient) -> None:
    created = await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)
    analysis_id = created.json()["analysis_id"]

    fetched = await client.get(f"/api/v1/process/analyses/{analysis_id}")
    assert fetched.status_code == 200
    assert {k: fetched.json()["roi"][k] for k in ROI_KEYS} == {
        k: created.json()["roi"][k] for k in ROI_KEYS
    }


async def test_report_generation_cannot_modify_roi(client: AsyncClient) -> None:
    created = await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)
    analysis_id = created.json()["analysis_id"]

    first = await client.post("/api/v1/report/generate", json={"analysis_id": analysis_id})
    second = await client.post("/api/v1/report/generate", json={"analysis_id": analysis_id})
    after = await client.get(f"/api/v1/process/analyses/{analysis_id}")

    baseline = {k: created.json()["roi"][k] for k in ROI_KEYS}
    assert {k: first.json()["roi"][k] for k in ROI_KEYS} == baseline
    assert {k: second.json()["roi"][k] for k in ROI_KEYS} == baseline
    assert {k: after.json()["roi"][k] for k in ROI_KEYS} == baseline


async def test_report_sections_and_quick_win_limit(client: AsyncClient) -> None:
    created = await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)
    report = await client.post(
        "/api/v1/report/generate", json={"analysis_id": created.json()["analysis_id"]}
    )
    markdown = report.json()["report"]

    for heading in (
        "## 1. Executive Summary",
        "## 2. Analysis Confidence",
        "## 3. Current State Assessment",
        "## 4. Key Pain Points",
        "## 5. Quick Wins",
        "## 6. Recommended Solutions",
        "## 7. Prioritised Action Plan",
        "## 8. Business Case and ROI",
        "## 9. 30-60-90 Day Roadmap",
        "## 10. Risks and Dependencies",
        "## 11. Executive Recommendation",
    ):
        assert heading in markdown

    assert len(report.json()["quick_wins"]) <= 3
    assert 0 <= report.json()["confidence"]["score"] <= 100


async def test_report_rejects_an_inline_roi_override(client: AsyncClient) -> None:
    """The request schema has no ROI field, so an attempt to inject one is rejected."""
    response = await client.post(
        "/api/v1/report/generate",
        json={"analysis_id": "x", "roi": {"estimated_hours_saved": 999}},
    )
    assert response.status_code == 422


async def test_recommendation_hours_do_not_exceed_roi_via_api(client: AsyncClient) -> None:
    body = (await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)).json()
    total = sum(
        Decimal(str(r["estimated_hours_saved_per_month"])) for r in body["recommendations"]
    )
    assert total <= Decimal(str(body["roi"]["estimated_hours_saved"]))


async def test_recommendations_returned_sorted_by_score(client: AsyncClient) -> None:
    body = (await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)).json()
    scores = [r["recommendation_score"] for r in body["recommendations"]]
    assert scores == sorted(scores, reverse=True)
