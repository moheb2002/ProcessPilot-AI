# ProcessPilot AI — API Examples

Base URL: `http://localhost:8000`

With `MOCK_AUTH_ENABLED=true` (the MVP default) the `Authorization` header is optional —
requests resolve to the seeded demo user.

---

## 1. Health

```bash
curl http://localhost:8000/health
```

```json
{ "status": "healthy" }
```

```bash
curl http://localhost:8000/health/ready
```

```json
{
  "status": "ready",
  "version": "0.1.0",
  "environment": "local",
  "database": "up",
  "llm": "mock"
}
```

---

## 2. Authentication

### Register

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "morgan@contoso.com",
    "full_name": "Morgan Manager",
    "password": "Str0ngPassw0rd!",
    "role": "manager"
  }'
```

```json
{
  "id": "8f1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9",
  "email": "morgan@contoso.com",
  "full_name": "Morgan Manager",
  "role": "manager",
  "is_active": true,
  "created_at": "2026-09-08T09:12:44.512Z",
  "updated_at": "2026-09-08T09:12:44.512Z"
}
```

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{ "email": "morgan@contoso.com", "password": "Str0ngPassw0rd!" }'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 43200,
  "user": { "id": "8f1b2c3d-...", "email": "morgan@contoso.com", "role": "manager" }
}
```

Use the token on subsequent calls:

```bash
-H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## 3. Upload a supporting document

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@./onboarding-sop.pdf"
```

```json
{
  "id": "c2a1f0d9-7b6e-4c3a-9f1d-2e8b0a5c4d63",
  "filename": "onboarding-sop.pdf",
  "content_type": "application/pdf",
  "size_bytes": 184320,
  "storage_backend": "local",
  "storage_uri": "file:///app/storage/9f2c...-onboarding-sop.pdf",
  "text_preview": "1. HR receives the signed offer letter...",
  "created_at": "2026-09-08T09:14:02.771Z"
}
```

Allowed: `.pdf`, `.docx`, `.txt`, up to 10 MB. Anything else returns `422`.

---

## 4. Analyze a process

```bash
curl -X POST http://localhost:8000/api/v1/process/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "process_name": "Employee Onboarding",
    "description": "HR receives a signed offer letter by email and manually creates the employee record in SAP. The hiring manager must approve the equipment request, then Finance provides a second approval. IT copies the details into Active Directory by hand and emails the new starter their credentials. HR tracks progress in an Excel spreadsheet and phones each team for status updates.",
    "department": "People Operations",
    "document_ids": ["c2a1f0d9-7b6e-4c3a-9f1d-2e8b0a5c4d63"],
    "roi_input": {
      "monthly_volume": 120,
      "minutes_per_transaction": 45,
      "employee_hourly_rate": 55,
      "implementation_cost": 40000
    }
  }'
```

```json
{
  "analysis_id": "5d4c3b2a-1908-4776-8e5d-3c2b1a09f8e7",
  "status": "completed",
  "analysis": {
    "process_name": "Employee Onboarding",
    "actors": ["HR", "IT", "Manager", "Finance"],
    "systems": ["SAP", "Active Directory", "Excel"],
    "steps": [
      {
        "order": 1,
        "name": "HR receives a signed offer letter",
        "description": "HR receives a signed offer letter by email.",
        "actor": "HR",
        "system": "",
        "is_manual": true,
        "estimated_minutes": 15.0
      }
    ],
    "approvals": ["The hiring manager must approve the equipment request."],
    "manual_tasks": ["HR receives a signed offer letter"]
  },
  "bottlenecks": [
    {
      "title": "Manual data re-entry across systems",
      "severity": "high",
      "impact": "Adds cycle time per transaction and introduces avoidable data-quality errors.",
      "recommendation": "Replace re-keying with a Power Automate flow writing directly to the system of record."
    }
  ],
  "opportunities": [
    {
      "solution": "Automated approval routing with escalation and audit trail",
      "technology": "Power Automate + Microsoft Teams",
      "business_value": "Cuts approval wait time and gives managers a single place to act.",
      "implementation_effort": "low"
    }
  ],
  "roi": {
    "current_hours": 90.0,
    "estimated_hours_saved": 49.5,
    "monthly_savings": 2722.5,
    "annual_savings": 32670.0,
    "roi_score": 0.0
  },
  "total_tokens": 3184,
  "duration_ms": 5120
}
```

Set `"persist": false` to run the pipeline without writing to the database.

---

## 5. ROI only (no LLM call)

```bash
curl -X POST http://localhost:8000/api/v1/process/roi \
  -H "Content-Type: application/json" \
  -d '{
    "monthly_volume": 100,
    "minutes_per_transaction": 60,
    "employee_hourly_rate": 50,
    "automation_rate": 0.5
  }'
```

```json
{
  "current_hours": 100.0,
  "estimated_hours_saved": 50.0,
  "monthly_savings": 2500.0,
  "annual_savings": 30000.0,
  "roi_score": 12.0
}
```

---

## 6. Generate the executive report

### From a stored analysis

```bash
curl -X POST http://localhost:8000/api/v1/report/generate \
  -H "Content-Type: application/json" \
  -d '{ "analysis_id": "5d4c3b2a-1908-4776-8e5d-3c2b1a09f8e7" }'
```

### Inline (stateless)

```bash
curl -X POST http://localhost:8000/api/v1/report/generate \
  -H "Content-Type: application/json" \
  -d '{
    "analysis": { "process_name": "Invoice Approval", "actors": ["Finance"], "systems": ["SAP"], "steps": [], "approvals": [], "manual_tasks": ["Re-key invoice data"] },
    "bottlenecks": [{ "title": "Manual invoice keying", "severity": "high", "impact": "12 FTE-hours per week", "recommendation": "Automate extraction" }],
    "opportunities": [{ "solution": "Invoice field extraction", "technology": "Azure AI Document Intelligence", "business_value": "Removes manual keying", "implementation_effort": "medium" }],
    "roi": { "current_hours": 100, "estimated_hours_saved": 55, "monthly_savings": 5500, "annual_savings": 66000, "roi_score": 26.4 }
  }'
```

```json
{
  "analysis_id": "5d4c3b2a-1908-4776-8e5d-3c2b1a09f8e7",
  "report": "Employee Onboarding is currently delivered through a mix of manual data entry...\n\n## Current State\n...\n\n## Implementation Roadmap\n...",
  "total_tokens": 1204
}
```

---

## 7. Browse stored analyses

```bash
curl "http://localhost:8000/api/v1/process/analyses?limit=10&offset=0"
curl http://localhost:8000/api/v1/process/analyses/5d4c3b2a-1908-4776-8e5d-3c2b1a09f8e7
```

```json
{
  "items": [
    {
      "id": "5d4c3b2a-1908-4776-8e5d-3c2b1a09f8e7",
      "process_name": "Employee Onboarding",
      "status": "completed",
      "total_tokens": 3184,
      "created_at": "2026-09-08T09:15:31.004Z"
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

Deleting requires the `manager` role or above:

```bash
curl -X DELETE http://localhost:8000/api/v1/process/analyses/5d4c3b2a-... \
  -H "Authorization: Bearer <manager-token>"
```

---

## 8. Error envelope

Every failure shares one shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request payload is invalid.",
    "details": [
      { "type": "string_too_short", "loc": ["body", "description"], "msg": "String should have at least 20 characters" }
    ]
  },
  "correlation_id": "0f3c1c1e-9a4b-4b91-9a1e-2c7f5b8d6e10"
}
```

| Code | HTTP | Meaning |
|------|------|---------|
| `validation_error` | 422 | Payload failed validation |
| `unauthorized` | 401 | Missing or invalid token |
| `forbidden` | 403 | Role does not satisfy the requirement |
| `not_found` | 404 | Resource missing or not owned by the caller |
| `conflict` | 409 | Duplicate resource |
| `rate_limit_exceeded` | 429 | Sliding-window limit hit (`Retry-After` header set) |
| `storage_error` | 502 | Upload persistence failed |
| `llm_unavailable` | 503 | Azure OpenAI failed after retries |
| `internal_error` | 500 | Unhandled server error |

---

## 9. Tracing a request

```bash
curl -i http://localhost:8000/api/v1/process/analyses \
  -H "X-Correlation-ID: my-trace-001"
```

The same id appears in the response headers, in every structured log line for the request, and
on the `audit_logs` rows it produced.
