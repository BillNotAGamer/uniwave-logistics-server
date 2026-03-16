from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401

logger = logging.getLogger(__name__)

settings = get_settings()
DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session


async def init_db() -> None:
    """Create all tables from metadata. Intended for local test utilities only."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def run_dev_startup_db_check(*, require_alembic_version: bool = True) -> None:
    """
    Development-only startup check:
    - verifies DB connectivity
    - optionally verifies alembic_version table exists
    """
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

        if not require_alembic_version:
            return

        def _has_alembic_version(sync_connection) -> bool:
            table_names = inspect(sync_connection).get_table_names()
            return "alembic_version" in table_names

        has_alembic_table = await connection.run_sync(_has_alembic_version)
        if not has_alembic_table:
            raise RuntimeError(
                "Missing alembic_version table. Run `alembic upgrade head` before starting the API."
            )

    logger.debug("Development startup DB check passed.")
