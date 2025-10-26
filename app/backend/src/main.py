import logging

# import time
from fastapi import FastAPI  # , Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api import auth, chat, templates, whatsapp_webhook
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
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware to populate user_id in request.state (must be before rate limiting)
app.add_middleware(UserStateMiddleware)

app.add_middleware(LoggingMiddleware)

# Include routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(templates.router)
app.include_router(whatsapp_webhook.router)


@app.get("/health_check")
async def health_check(check_db: bool = False) -> dict[str, str | bool]:
    """Health check endpoint to verify API is running.

    Args:
        check_db: If True, also checks database connectivity
    """
    settings = get_settings()
    result: dict[str, str | bool] = {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }

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

    return result
