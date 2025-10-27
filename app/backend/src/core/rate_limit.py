"""Rate limiting configuration for API endpoints.

This module provides two rate limiting strategies:
- IP-based: For public endpoints (auth)
- Architect-based: For authenticated endpoints (chat)
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.config import get_settings

settings = get_settings()

# Use memory storage for tests, Redis for production
if settings.ENVIRONMENT == "test":
    storage_uri = "memory://"
else:
    storage_uri = settings.REDIS_URL.get_secret_value()


# Rate limiter based on IP address (for public endpoints like auth)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=storage_uri,
    strategy="fixed-window",
)


def get_architect_id_or_ip(request: Request) -> str:
    """Hybrid key function: returns architect_id if authenticated, otherwise IP.

    This allows authenticated endpoints to be rate limited per user,
    while unauthenticated requests are limited per IP.

    Args:
        request: FastAPI Request object

    Returns:
        Key string for rate limiting (user:{id} or ip:{address})
    """
    architect_id = getattr(request.state, "architect_id", None)
    if architect_id:
        return f"user:{architect_id}"

    # Fallback to IP if no user
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


# Rate limiter for authenticated endpoints (uses architect_id or IP)
limiter_authenticated = Limiter(
    key_func=get_architect_id_or_ip,
    storage_uri=storage_uri,
    strategy="fixed-window",
)
