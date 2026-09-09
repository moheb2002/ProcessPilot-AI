"""Integration tests exercising the HTTP API end to end."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

ANALYZE_PAYLOAD = {
    "process_name": "Employee Onboarding",
    "description": (
        "HR receives a signed offer letter by email and manually creates the employee record "
        "in SAP. The hiring manager must approve the equipment request and Finance provides a "
        "second approval. IT copies the details into Active Directory by hand."
    ),
    "roi_input": {
        "monthly_volume": 120,
        "minutes_per_transaction": 45,
        "employee_hourly_rate": 55,
    },
}


async def test_health_returns_healthy(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_readiness_reports_dependencies(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "up"
    assert body["llm"] == "mock"


async def test_correlation_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Correlation-ID": "cid-123"})
    assert response.headers["X-Correlation-ID"] == "cid-123"


async def test_analyze_returns_full_pipeline_result(client: AsyncClient) -> None:
    response = await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)
    assert response.status_code == 200

    body = response.json()
    assert body["analysis"]["process_name"] == "Employee Onboarding"
    assert body["analysis"]["steps"]
    assert len(body["bottlenecks"]) >= 3
    assert len(body["opportunities"]) >= 3
    assert body["roi"]["annual_savings"] > 0
    assert body["analysis_id"]


async def test_analyze_rejects_short_description(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/process/analyze", json={"process_name": "X", "description": "short"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_analysis_can_be_retrieved_and_listed(client: AsyncClient) -> None:
    created = await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)
    analysis_id = created.json()["analysis_id"]

    fetched = await client.get(f"/api/v1/process/analyses/{analysis_id}")
    assert fetched.status_code == 200
    assert fetched.json()["analysis_id"] == analysis_id

    listed = await client.get("/api/v1/process/analyses")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


async def test_unknown_analysis_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/process/analyses/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_roi_endpoint_is_deterministic(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/process/roi",
        json={
            "monthly_volume": 100,
            "minutes_per_transaction": 60,
            "employee_hourly_rate": 50,
            "automation_rate": 0.5,
        },
    )
    assert response.status_code == 200
    assert response.json()["monthly_savings"] == 2500.0


async def test_report_generation_from_stored_analysis(client: AsyncClient) -> None:
    created = await client.post("/api/v1/process/analyze", json=ANALYZE_PAYLOAD)
    analysis_id = created.json()["analysis_id"]

    response = await client.post(
        "/api/v1/report/generate", json={"analysis_id": analysis_id}
    )
    assert response.status_code == 200
    assert "## Implementation Roadmap" in response.json()["report"]


async def test_report_generation_requires_a_source(client: AsyncClient) -> None:
    response = await client.post("/api/v1/report/generate", json={})
    assert response.status_code == 422


async def test_document_upload_extracts_text(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("sop.txt", b"Step 1: receive request.", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "sop.txt"
    assert "receive request" in body["text_preview"]


async def test_document_upload_rejects_unsupported_extension(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_uploaded_document_feeds_analysis_context(client: AsyncClient) -> None:
    upload = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("sop.txt", b"Finance re-keys invoice data into SAP.", "text/plain")},
    )
    document_id = upload.json()["id"]

    response = await client.post(
        "/api/v1/process/analyze", json={**ANALYZE_PAYLOAD, "document_ids": [document_id]}
    )
    assert response.status_code == 200
