import logging
from collections.abc import Awaitable
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from src.api import auth, briefings, chat, organizations, templates, whatsapp_webhook
from src.core.cache import client as cache_client
from src.core.config import get_settings
from src.core.lifespan import lifespan
from src.core.logging_config.middleware import LoggingMiddleware
from src.core.rate_limit import limiter, limiter_authenticated
from src.db.session import get_async_sessionmaker
from src.middleware.user_state import UserStateMiddleware
from src.version import __version__

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fullstack Template API",
    description="FastAPI backend with authentication and AI integration",
    version=__version__,
    debug=get_settings().LOG_LEVEL == "DEBUG",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.state.limiter_authenticated = limiter_authenticated
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(UserStateMiddleware)

app.add_middleware(LoggingMiddleware)

app.include_router(auth.router)
app.include_router(briefings.router)
app.include_router(chat.router)
app.include_router(organizations.router)
app.include_router(templates.router)
app.include_router(whatsapp_webhook.router)


@app.get("/health_check")
async def health_check(
    check_db: bool = False,
    check_redis: bool = False,
    check_ai: bool = False,
) -> dict[str, str | bool]:
    """Health check endpoint to verify API is running.

    Args:
        check_db: If True, also checks database connectivity
        check_redis: If True, checks Redis connectivity
        check_whatsapp: If True, checks WhatsApp API availability
        check_ai: If True, checks AI provider APIs (OpenAI/Anthropic)
    """
    settings = get_settings()
    result: dict[str, str | bool] = {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }

    if check_db:
        session_factory = get_async_sessionmaker()

        try:
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
                result["database"] = "connected"
        except Exception as e:
            result["status"] = "unhealthy"
            result["database"] = "disconnected"
            result["error"] = str(e)

    if check_redis:
        try:
            redis_client = cache_client.get_redis_client()
            await cast(Awaitable[bool], redis_client.ping())
            result["redis"] = "connected"
        except Exception as e:
            result["status"] = "unhealthy"
            result["redis"] = "disconnected"
            if "error" not in result:
                result["error"] = str(e)

    if check_ai:
        has_openai = settings.OPENAI_API_KEY is not None
        has_anthropic = settings.ANTHROPIC_API_KEY is not None

        if has_openai or has_anthropic:
            result["ai"] = "connected"
        else:
            result["ai"] = "not_configured"

    return result
