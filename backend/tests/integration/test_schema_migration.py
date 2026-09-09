"""The startup schema sync must repair databases created by an older model version."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.init_db import sync_schema

#: The `analyses` and `roi_results` shape shipped before the ROI engine landed.
LEGACY_SCHEMA = (
    """
    CREATE TABLE analyses (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        status VARCHAR(32) NOT NULL,
        process_name VARCHAR(255) NOT NULL,
        analysis_payload JSON NOT NULL,
        bottlenecks_payload JSON NOT NULL,
        executive_report TEXT,
        error_message TEXT,
        total_tokens INTEGER NOT NULL,
        duration_ms INTEGER NOT NULL,
        owner_id VARCHAR(36) NOT NULL,
        process_id VARCHAR(36),
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE roi_results (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        monthly_volume INTEGER NOT NULL,
        minutes_per_transaction FLOAT NOT NULL,
        employee_hourly_rate FLOAT NOT NULL,
        automation_rate FLOAT NOT NULL,
        current_hours FLOAT NOT NULL,
        estimated_hours_saved FLOAT NOT NULL,
        monthly_savings FLOAT NOT NULL,
        annual_savings FLOAT NOT NULL,
        roi_score FLOAT NOT NULL,
        analysis_id VARCHAR(36) NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    INSERT INTO analyses VALUES (
        'a1', 'completed', 'Purchase Approval Process', '{}', '[]', NULL, NULL,
        100, 50, 'u1', NULL, '2026-01-01', '2026-01-01'
    )
    """,
    # automation_rate is the request default (0.6) while the stored hours are 50%:
    # the exact shape of the original defect.
    """
    INSERT INTO roi_results VALUES (
        'r1', 120, 40, 28, 0.6, 80.0, 40.0, 1120.0, 13440.0, 5.0, 'a1',
        '2026-01-01', '2026-01-01'
    )
    """,
)


@pytest_asyncio.fixture
async def legacy_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}")
    async with engine.begin() as conn:
        for statement in LEGACY_SCHEMA:
            await conn.execute(text(statement))
    yield engine
    await engine.dispose()


async def _columns(engine, table: str) -> set[str]:
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: {col["name"] for col in inspect(sync_conn).get_columns(table)}
        )


async def test_sync_schema_adds_missing_columns(legacy_engine) -> None:
    assert "opportunities_payload" not in await _columns(legacy_engine, "analyses")

    await sync_schema(legacy_engine)

    analyses = await _columns(legacy_engine, "analyses")
    assert {
        "opportunities_payload",
        "recommendations_payload",
        "automation_potential_payload",
        "confidence_payload",
        "quick_wins_payload",
        "roadmap_payload",
        "report_payload",
    } <= analyses

    roi = await _columns(legacy_engine, "roi_results")
    assert {
        "automation_potential_percentage",
        "remaining_monthly_hours",
        "calculation_method",
        "assumptions",
    } <= roi


async def test_sync_schema_backfills_json_defaults(legacy_engine) -> None:
    await sync_schema(legacy_engine)

    async with legacy_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT opportunities_payload, recommendations_payload, "
                    "confidence_payload, roadmap_payload FROM analyses"
                )
            )
        ).one()
    assert row == ("[]", "[]", "{}", "{}")


async def test_legacy_roi_percentage_is_derived_from_the_stored_hours(legacy_engine) -> None:
    """The buggy `automation_rate` must not be trusted over the hours users saw."""
    await sync_schema(legacy_engine)

    async with legacy_engine.connect() as conn:
        percentage, remaining, method = (
            await conn.execute(
                text(
                    "SELECT automation_potential_percentage, remaining_monthly_hours, "
                    "calculation_method FROM roi_results"
                )
            )
        ).one()

    assert percentage == 50.0  # 40 / 80, not the stored automation_rate of 0.6
    assert remaining == 40.0
    assert method


async def test_sync_schema_is_idempotent(legacy_engine) -> None:
    await sync_schema(legacy_engine)
    await sync_schema(legacy_engine)
    await sync_schema(legacy_engine)

    async with legacy_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT automation_potential_percentage, remaining_monthly_hours, "
                    "current_hours, estimated_hours_saved FROM roi_results"
                )
            )
        ).all()
    assert rows == [(50.0, 40.0, 80.0, 40.0)]


async def test_sync_schema_on_a_current_database_changes_nothing(legacy_engine) -> None:
    await sync_schema(legacy_engine)
    before = await _columns(legacy_engine, "roi_results")

    await sync_schema(legacy_engine)

    assert await _columns(legacy_engine, "roi_results") == before
