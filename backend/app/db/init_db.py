"""Schema creation and demo-data seeding for the MVP."""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import Role, hash_password
from app.db.base import Base
from app.db.session import AsyncSessionFactory, engine
from app.models import User  # importing the package registers every ORM model

logger = get_logger(__name__)


async def create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_schema_ready")


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
    await seed_demo_user()
