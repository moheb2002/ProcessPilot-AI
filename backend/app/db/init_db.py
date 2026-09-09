"""Schema creation and demo-data seeding for the MVP."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Column, Connection, Table, func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import Role, hash_password
from app.db.base import Base
from app.db.session import AsyncSessionFactory, engine
from app.models import User  # importing the package registers every ORM model
from app.models.roi import ROIResult as ROIResultRow
from app.services.roi_service import CALCULATION_METHOD

logger = get_logger(__name__)


async def create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_schema_ready")


def _default_value(column: Column[Any]) -> Any:
    """The Python-side default SQLAlchemy would apply on insert, if any."""
    default = column.default
    if default is None:
        return None
    if default.is_scalar:
        return default.arg
    if default.is_callable:
        return default.arg(None)
    return None


def _missing_columns(conn: Connection, table: Table) -> list[Column[Any]]:
    inspector = inspect(conn)
    if table.name not in inspector.get_table_names():
        return []
    present = {col["name"] for col in inspector.get_columns(table.name)}
    return [column for column in table.columns if column.name not in present]


async def sync_schema(bind: AsyncEngine | None = None) -> None:
    """Add columns that models gained after the database file was first created.

    ``create_all`` only creates missing tables, so an existing database keeps
    failing at startup once a model grows a column. This additive, idempotent
    step closes that gap; Alembic remains the right tool for production.
    """
    async with (bind or engine).begin() as conn:
        for table in Base.metadata.sorted_tables:
            for column in await conn.run_sync(_missing_columns, table):
                column_type = column.type.compile(dialect=conn.dialect)
                # Added without NOT NULL: SQLite cannot enforce it on existing rows.
                await conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}')
                )
                default = _default_value(column)
                if default is not None:
                    await conn.execute(
                        table.update().where(column.is_(None)).values({column.name: default})
                    )
                logger.info(
                    "database_column_added",
                    extra={"table": table.name, "column": column.name},
                )

        await _derive_legacy_roi_columns(conn)


async def _derive_legacy_roi_columns(conn: Any) -> None:
    """Recompute ROI columns that rows predating the ROI engine never stored.

    The stored hours are authoritative: ``automation_rate`` was the column
    carrying the original defect, so the percentage is reconstructed from the
    hours the user was actually shown. Each statement only fires when the row
    genuinely disagrees, so it is convergent and self-correcting.
    """
    table = ROIResultRow.__table__
    derived_percentage = table.c.estimated_hours_saved * 100 / table.c.current_hours
    derived_remaining = table.c.current_hours - table.c.estimated_hours_saved

    await conn.execute(
        table.update()
        .where(
            table.c.current_hours > 0,
            # Tolerance absorbs the drift from hours having been stored rounded.
            func.abs(table.c.automation_potential_percentage - derived_percentage) > 1,
        )
        .values(automation_potential_percentage=derived_percentage)
    )
    await conn.execute(
        table.update()
        .where(
            table.c.current_hours > 0,
            func.abs(table.c.remaining_monthly_hours - derived_remaining) > 0.01,
        )
        .values(remaining_monthly_hours=derived_remaining)
    )
    await conn.execute(
        table.update()
        .where(table.c.calculation_method == "")
        .values(calculation_method=CALCULATION_METHOD)
    )


async def seed_demo_user() -> None:
    """Create the mock-auth demo user so MVP requests resolve to a real row."""
    if not settings.MOCK_AUTH_ENABLED:
        return

    async with AsyncSessionFactory() as session:
        existing = await session.scalar(
            select(User).where(User.email == settings.MOCK_AUTH_EMAIL)
        )
        if existing is not None:
            return

        session.add(
            User(
                email=settings.MOCK_AUTH_EMAIL,
                full_name="Demo User",
                hashed_password=hash_password("demo-password"),
                role=Role(settings.MOCK_AUTH_ROLE),
                is_active=True,
            )
        )
        await session.commit()
        logger.info("demo_user_seeded", extra={"email": settings.MOCK_AUTH_EMAIL})


async def init_db() -> None:
    await create_schema()
    await sync_schema()
    await seed_demo_user()
