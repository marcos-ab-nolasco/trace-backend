from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


@lru_cache
def get_engine() -> AsyncEngine:
    """Return cached async engine instance."""

    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL.get_secret_value(),
        echo=settings.LOG_LEVEL == "DEBUG",
        future=True,
    )


@lru_cache
def get_async_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return cached async session factory."""

    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""

    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# Alias for consistency with other parts of the codebase
get_db_session = get_db
