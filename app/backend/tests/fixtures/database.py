"""Database and session-related test fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.config import get_settings
from src.db.session import Base


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine with PostgreSQL.

    Uses NullPool to ensure each operation gets a fresh connection,
    preventing 'another operation is in progress' errors with asyncpg.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL.get_secret_value(),
        echo=False,
        future=True,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with table cleanup after each test."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        table_names = ", ".join([table.name for table in reversed(Base.metadata.sorted_tables)])

        await conn.execute(
            sqlalchemy.text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
        )
