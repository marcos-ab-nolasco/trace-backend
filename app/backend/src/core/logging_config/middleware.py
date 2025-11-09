import logging
from time import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Log all HTTP requests with method, path, status code, and duration."""
        if request.url.path == "/health_check":
            return await call_next(request)

        start_time = time()
        response = await call_next(request)
        duration_ms = int((time() - start_time) * 1000)

        architect_id = getattr(request.state, "architect_id", None) or "anonymous"

        logger.info(
            f"HTTP {request.method} {request.url.path} {response.status_code} "
            f"{duration_ms}ms architect_id={architect_id}"
        )

        return response
