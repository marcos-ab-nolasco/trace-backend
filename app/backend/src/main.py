import logging
from collections.abc import Awaitable
from typing import cast

# import time
from fastapi import FastAPI  # , Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api import auth, briefings, chat, organizations, templates, whatsapp_webhook
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

# Configure rate limiting
app.state.limiter = limiter
app.state.limiter_authenticated = limiter_authenticated
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware to populate architect_id in request.state (must be before rate limiting)
app.add_middleware(UserStateMiddleware)

app.add_middleware(LoggingMiddleware)

# Include routers
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
    check_whatsapp: bool = False,
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

    # Check database connectivity
    if check_db:
        from sqlalchemy import text

        session_factory = get_async_sessionmaker()

        try:
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
                result["database"] = "connected"
        except Exception as e:  # pragma: no cover - diagnostic only
            result["status"] = "unhealthy"
            result["database"] = "disconnected"
            result["error"] = str(e)

    # Check Redis connectivity
    if check_redis:
        from src.core.cache.client import get_redis_client

        try:
            redis_client = get_redis_client()
            await cast(Awaitable[bool], redis_client.ping())
            result["redis"] = "connected"
        except Exception as e:
            result["status"] = "unhealthy"
            result["redis"] = "disconnected"
            if "error" not in result:
                result["error"] = str(e)

    # Check WhatsApp API availability
    if check_whatsapp:
        # Lightweight check - just verify if credentials are configured
        # Full API check would require actual API call which may fail in test env
        if settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
            result["whatsapp"] = "connected"
        else:
            result["whatsapp"] = "not_configured"

    # Check AI providers availability
    if check_ai:
        # Check if any AI provider is configured
        has_openai = settings.OPENAI_API_KEY is not None
        has_anthropic = settings.ANTHROPIC_API_KEY is not None

        if has_openai or has_anthropic:
            result["ai"] = "connected"
        else:
            result["ai"] = "not_configured"

    return result
