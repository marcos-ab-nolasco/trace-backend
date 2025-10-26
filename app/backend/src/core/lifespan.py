import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.cache.client import get_redis_client
from src.db.session import get_engine

# from path/to/client import get_redis_client


log = logging.getLogger(__name__)


async def _check_connection_redis_server() -> None:
    log.debug("Verificando conexão com servidor de cache")
    await get_redis_client().ping()  # type: ignore[misc]


async def _close_connection_redis_server() -> None:
    log.debug("Encerrando conexão com servidor de cache")
    await get_redis_client().close()


async def _check_connection_postgres_server() -> None:
    log.debug("Verificando conexão com servidor Postgres")
    from sqlalchemy import text

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("Conexão com Postgres estabelecida")


async def _close_connection_postgres_server() -> None:
    log.debug("Encerrando conexão com servidor Postgres")

    engine = get_engine()
    await engine.dispose()
    log.info("Conexão com Postgres encerrada")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    await _check_connection_redis_server()
    await _check_connection_postgres_server()

    yield

    await _close_connection_postgres_server()
    await _close_connection_redis_server()
