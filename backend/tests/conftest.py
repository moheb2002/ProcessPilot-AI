"""Shared pytest fixtures: isolated in-memory DB, mock LLM and async HTTP client."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("USE_MOCK_LLM", "true")
os.environ.setdefault("MOCK_AUTH_ENABLED", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import User  # noqa: E402,F401
from app.services.mock_llm import MockLLMClient  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def engine():
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def db_session(session_factory) -> AsyncIterator:
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(session_factory, tmp_path: Path) -> AsyncIterator[AsyncClient]:
    from app.api import deps
    from app.services.storage import LocalStorageBackend

    app = create_app()
    app.router.lifespan_context = _noop_lifespan  # schema is created by the engine fixture

    async def _override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[deps.get_db_session] = _override_session
    app.dependency_overrides[deps.get_llm_client] = lambda: MockLLMClient()
    app.dependency_overrides[deps.get_storage] = lambda: LocalStorageBackend(tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    app.dependency_overrides.clear()


def _noop_lifespan(_app):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():
        yield

    return _ctx()


@pytest.fixture
def mock_llm() -> MockLLMClient:
    return MockLLMClient()


@pytest.fixture
def sample_description() -> str:
    return (
        "HR receives a signed offer letter by email and manually creates the employee "
        "record in SAP. The hiring manager must approve the equipment request, then "
        "Finance provides a second approval. IT copies the details into Active Directory "
        "by hand and emails the new starter their credentials. HR tracks progress in an "
        "Excel spreadsheet and phones each team for status updates."
    )
