"""Middleware to populate request.state.user_id for rate limiting.

This middleware extracts user_id from JWT token and stores it in request.state
BEFORE rate limiting is applied, allowing per-user rate limits on authenticated endpoints.
"""

import logging
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.core.security import decode_token

logger = logging.getLogger(__name__)


class UserStateMiddleware(BaseHTTPMiddleware):
    """Middleware to extract user_id from JWT and populate request.state."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Extract user_id from Authorization header and store in request.state."""
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            try:
                payload = decode_token(token)
                if payload.get("type") == "access":
                    user_id = payload.get("sub")
                    if user_id:
                        request.state.user_id = user_id
            except (ValueError, TypeError):
                # Invalid token - ignore and continue
                # The actual authentication will be handled by get_current_user dependency
                pass

        response = await call_next(request)
        return response
