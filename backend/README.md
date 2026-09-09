# ProcessPilot AI — Backend

AI-powered business process optimization platform. Describe a business process in natural
language (optionally with supporting SOPs), and ProcessPilot AI returns a structured process
model, ranked bottlenecks, Microsoft-first automation recommendations, a quantified ROI model,
and a consultant-style executive report.

---

## Contents

- [Architecture](#architecture)
- [Agent pipeline](#agent-pipeline)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Data model](#data-model)
- [Security](#security)
- [Observability](#observability)
- [Testing](#testing)
- [Docker](#docker)
- [MVP scope and the path to production](#mvp-scope-and-the-path-to-production)

---

## Architecture

Clean architecture with strict inward-pointing dependencies:

```
HTTP  ->  api/          routers + dependency wiring (FastAPI)
      ->  services/     use-case orchestration (no HTTP, no SQL details)
      ->  agents/       single-responsibility LLM agents
      ->  repositories/ persistence boundary (SQLAlchemy)
      ->  models/       ORM aggregates
```

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py                  # DI: auth principal, repos, services, pagination
│   │   └── v1/
│   │       ├── router.py            # /api/v1 aggregation
│   │       └── routers/             # health, auth, process, report, documents
│   ├── core/                        # config, logging, security, exceptions
│   ├── models/                      # User, Process, Analysis, Recommendation,
│   │                                #   ROIResult, UploadedDocument, AuditLog
│   ├── schemas/                     # Pydantic v2 request/response contracts
│   ├── services/                    # AnalysisService, ReportService, DocumentService,
│   │                                #   AuthService, AzureOpenAIClient, storage
│   ├── repositories/                # Generic + per-aggregate repositories
│   ├── agents/                      # The five AI agents
│   ├── prompts/                     # Versioned prompt templates
│   ├── db/                          # Base, async session, schema init/seed
│   ├── middleware/                  # correlation id, request logging, rate limiting
│   ├── utils/                       # PDF/DOCX/TXT text extraction
│   └── main.py                      # Application factory + lifespan
├── tests/
│   ├── unit/                        # agents, ROI maths, security, storage
│   └── integration/                 # full HTTP round trips
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── .env.example
└── API_EXAMPLES.md
```

**SOLID in practice**

- *Single responsibility* — each agent owns exactly one reasoning step; services orchestrate,
  repositories persist, routers translate HTTP.
- *Open/closed* — new agents subclass `BaseAgent`; new storage backends implement the
  `StorageBackend` protocol; neither requires changing existing code.
- *Liskov* — `MockLLMClient` and `AzureOpenAIClient` are freely interchangeable behind `LLMClient`.
- *Interface segregation* — `LLMClient` and `StorageBackend` are narrow `Protocol`s, not fat base classes.
- *Dependency inversion* — services depend on protocols; concrete implementations are injected
  in [app/api/deps.py](app/api/deps.py).

---

## Agent pipeline

`POST /api/v1/process/analyze` runs four agents in sequence; the fifth is invoked by
`POST /api/v1/report/generate`.

```mermaid
flowchart LR
    A[Process description<br/>+ optional documents] --> B[1. Process Analyzer]
    B --> C[2. Bottleneck Detection]
    C --> D[3. Automation Advisor]
    D --> E[4. ROI Agent]
    E --> F[5. Executive Summary]
    F --> G[Markdown report]
```

| # | Agent | Output contract |
|---|-------|-----------------|
| 1 | **Process Analyzer** | `process_name`, `actors`, `systems`, `steps`, `approvals`, `manual_tasks` |
| 2 | **Bottleneck Detection** | `bottlenecks[] { title, severity, impact, recommendation }` |
| 3 | **Automation Advisor** | `opportunities[] { solution, technology, business_value, implementation_effort }` |
| 4 | **ROI Agent** | `current_hours`, `estimated_hours_saved`, `monthly_savings`, `annual_savings`, `roi_score` |
| 5 | **Executive Summary** | Markdown: Current State, Key Pain Points, Recommended Solutions, Expected Benefits, ROI, Implementation Roadmap |

The Automation Advisor is prompted to prioritise Microsoft 365 Copilot, Power Automate,
Power Apps, Azure AI Foundry, Azure OpenAI, Azure AI Search, Azure Document Intelligence and
Microsoft Graph.

**ROI is deterministic, not hallucinated.** The LLM only estimates the *automation rate*; the
financial maths lives in the pure function `calculate_roi()`:

```
current_hours          = monthly_volume * minutes_per_transaction / 60
estimated_hours_saved  = current_hours * automation_rate
monthly_savings        = estimated_hours_saved * employee_hourly_rate
annual_savings         = monthly_savings * 12
roi_score              = (annual_savings - implementation_cost) / implementation_cost * 100
                         (or annual_savings normalised to a reference when no cost is given,
                          clamped to 0-100)
```

---

## Quick start

Requires Python 3.12+.

```powershell
cd backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

Copy-Item .env.example .env
az login
uvicorn app.main:app --reload
```

```bash
# macOS / Linux
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
az login
uvicorn app.main:app --reload
```

Then open:

- Swagger UI — <http://localhost:8000/docs>
- ReDoc — <http://localhost:8000/redoc>
- Liveness — <http://localhost:8000/health>

The SQLite schema is created and the demo user is seeded automatically on startup.

**No Azure OpenAI resource?** Leave `AZURE_OPENAI_ENDPOINT` blank. The app falls back to a
deterministic heuristic `MockLLMClient` so every endpoint returns realistic, schema-valid data
offline. When an endpoint is configured, the app uses the identity signed in through `az login`;
that identity needs the `Cognitive Services OpenAI User` role on the resource. `GET /health/ready`
reports which mode is active.

---

## Configuration

All settings are environment variables bound by Pydantic Settings. See
[.env.example](.env.example) for the full annotated list.

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./processpilot.db` | Swap for `postgresql+asyncpg://...` in production |
| `AZURE_OPENAI_ENDPOINT` | empty | Blank ⇒ mock LLM; otherwise authenticate with `az login` |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Deployment name, not the model name |
| `USE_MOCK_LLM` | `false` | Force the mock even when Azure OpenAI is configured |
| `STORAGE_BACKEND` | `local` | `local` or `azure_blob` |
| `MOCK_AUTH_ENABLED` | `true` | MVP: unauthenticated requests resolve to the demo user |
| `JWT_SECRET_KEY` | `change-me-in-production` | **Must** be rotated before deployment |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | `120` / `60` | Per-client sliding window |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | empty | Enables Azure Monitor log export |

---

## API reference

All business endpoints are versioned under `/api/v1`. Health probes are unversioned so
infrastructure probes stay stable.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness — `{"status": "healthy"}` |
| `GET` | `/health/ready` | Readiness — database and LLM mode |
| `POST` | `/api/v1/auth/register` | Create a user |
| `POST` | `/api/v1/auth/login` | Exchange credentials for a JWT |
| `GET` | `/api/v1/auth/me` | Current principal |
| `POST` | `/api/v1/process/analyze` | **Run the full agent pipeline** |
| `POST` | `/api/v1/process/roi` | Deterministic ROI calculation (no LLM call) |
| `GET` | `/api/v1/process/analyses` | Paginated list of the caller's analyses |
| `GET` | `/api/v1/process/analyses/{id}` | Retrieve a stored analysis |
| `DELETE` | `/api/v1/process/analyses/{id}` | Delete an analysis (manager+) |
| `POST` | `/api/v1/report/generate` | Generate the executive report |
| `POST` | `/api/v1/documents/upload` | Upload a PDF, DOCX or TXT (≤ 10 MB) |
| `GET` | `/api/v1/documents` | List uploaded documents |
| `GET` | `/api/v1/documents/{id}` | Document metadata + text preview |

Runnable request/response samples: [API_EXAMPLES.md](API_EXAMPLES.md).

Every error uses one envelope:

```json
{
  "error": { "code": "not_found", "message": "Analysis 'abc' was not found." },
  "correlation_id": "0f3c1c1e-..."
}
```

---

## Data model

| Model | Purpose |
|-------|---------|
| `User` | Account, hashed password, role |
| `Process` | The submitted process description and metadata |
| `Analysis` | Pipeline run: status, structured analysis, bottlenecks, report, token/latency metrics |
| `Recommendation` | One automation opportunity (child of `Analysis`) |
| `ROIResult` | Inputs and computed savings (child of `Analysis`) |
| `UploadedDocument` | File metadata, storage URI, extracted text |
| `AuditLog` | Immutable action trail with actor and correlation id |

All tables use UUID string primary keys and timezone-aware `created_at` / `updated_at`.

---

## Security

- **JWT** (HS256) via `python-jose`; tokens carry `sub`, `role`, `iat`, `exp` and `iss`.
- **Password hashing** with bcrypt (`passlib`); plaintext is never stored or logged.
- **RBAC** with a role hierarchy (`admin ⊃ manager ⊃ employee`) enforced by the
  `require_role(...)` dependency factory.
- **Request validation** — Pydantic v2 with `extra="forbid"` on inbound schemas, plus length
  and range bounds on every field.
- **Upload hardening** — extension allow-list, size cap, and filename sanitisation with a path
  traversal guard on the resolved destination.
- **Rate limiting** — per-client sliding window, health/docs paths exempt.
- **CORS** — explicit origin allow-list, no wildcard with credentials.
- **Exception handling** — no stack traces or internal details leak to clients; everything is
  logged server-side with a correlation id.
- **Container** — runs as a non-root user (uid 10001).

> **MVP note:** `MOCK_AUTH_ENABLED=true` lets unauthenticated requests resolve to a demo user
> so the frontend can be built in parallel. **Set it to `false` before any deployment.**

---

## Observability

- **Structured JSON logs** (`python-json-logger`) with `timestamp`, `level`, `correlation_id`,
  `service` and `environment` on every record.
- **Correlation IDs** — accepted from the inbound `X-Correlation-ID` header or generated,
  stored in a `ContextVar`, attached to every log line and audit row, and echoed on the response.
- **Request logging** — method, path, status and duration; `X-Response-Time-ms` response header.
- **Token monitoring** — prompt/completion/total tokens are logged per LLM call and persisted
  per analysis.
- **Application Insights** — set `APPLICATIONINSIGHTS_CONNECTION_STRING` and uncomment
  `opencensus-ext-azure` in `requirements.txt` to export logs to Azure Monitor.

---

## Testing

```powershell
# whole suite
pytest

# with coverage gate (fails under 80%)
pytest --cov=app --cov-report=term-missing --cov-report=html

# subsets
pytest tests/unit
pytest tests/integration
```

Tests run entirely offline: an in-memory SQLite database per test, the mock LLM, and a
temp-directory storage backend — all injected through FastAPI dependency overrides.

---

## Docker

```bash
cd backend
cp .env.example .env

docker compose up --build              # API only, SQLite + local storage
docker compose --profile postgres up   # API + PostgreSQL
```

For the PostgreSQL profile, set in `.env`:

```
DATABASE_URL=postgresql+asyncpg://processpilot:processpilot@postgres:5432/processpilot
```

The image is a slim Python 3.12 build with a `/health` healthcheck and a non-root runtime user.

---

## MVP scope and the path to production

| Concern | MVP today | Extension point |
|---------|-----------|-----------------|
| Database | SQLite (`aiosqlite`) | Change `DATABASE_URL` to `postgresql+asyncpg://…`; `asyncpg` is already a dependency |
| Auth | Mock principal when no token is supplied | Set `MOCK_AUTH_ENABLED=false`; JWT + RBAC are already fully implemented |
| AI | Azure OpenAI only, with an offline mock fallback | Add an AI Foundry Agent Service client implementing `LLMClient` — no agent or service changes needed |
| Files | Local disk | Set `STORAGE_BACKEND=azure_blob` + a connection string; `AzureBlobStorageBackend` ships in the box |
| Microsoft Graph | Not implemented | Add a `GraphService` behind the existing service layer |
| Rate limiting | In-process sliding window | Swap the backing store for Redis or move to Azure API Management |
| Migrations | `create_all` on startup | `alembic` is a dependency; add a migration directory when the schema stabilises |
