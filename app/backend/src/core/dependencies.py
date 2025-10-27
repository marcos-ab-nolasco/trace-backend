import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache.decorator import redis_cache_decorator
from src.core.security import decode_token
from src.db.models.architect import Architect
from src.db.session import get_db

http_bearer_scheme = HTTPBearer()

logger = logging.getLogger(__name__)


@redis_cache_decorator(
    ttl=180,
    ignore_positionals=[0],
    namespace="auth.architect_by_id",
)
async def _get_architect_by_id(db: AsyncSession, architect_id: UUID) -> Architect | None:
    """Fetch architect by ID from database (cached).

    This internal function is cached to reduce database load for authentication.
    The cache key is based on architect_id, making it resilient to token refresh.

    Args:
        db: Database session
        architect_id: Architect UUID

    Returns:
        Architect object if found, None otherwise
    """
    result = await db.execute(select(Architect).where(Architect.id == architect_id))
    return result.scalar_one_or_none()


async def get_current_architect(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Architect:
    """Dependency to get the current authenticated architect."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid token: reason=decode_failed error={str(e)}")
        raise credentials_exception from e

    # Check token type
    if payload.get("type") != "access":
        logger.warning(f"Invalid token: reason=wrong_token_type token_type={payload.get('type')}")
        raise credentials_exception

    architect_id_str: str | None = payload.get("sub")
    if architect_id_str is None:
        logger.warning("Invalid token: reason=missing_subject")
        raise credentials_exception

    try:
        architect_id = UUID(architect_id_str)
    except (ValueError, TypeError) as e:
        logger.warning(
            "Invalid token: reason=invalid_uuid_format architect_id_str=%s", architect_id_str
        )
        raise credentials_exception from e

    # Fetch architect from database (cached by architect_id)
    architect = await _get_architect_by_id(db, architect_id)

    if architect is None:
        logger.warning("Invalid token: reason=architect_not_found architect_id=%s", architect_id)
        raise credentials_exception

    # Store architect_id in request state for middleware logging
    request.state.architect_id = str(architect_id)

    return architect


async def get_current_architect_id(
    current_architect: Annotated[Architect, Depends(get_current_architect)]
) -> UUID:
    """Dependency to get the current architect's ID.

    Useful for endpoints that only need the identifier, not the full object.
    """
    return current_architect.id


# Backwards-compatible aliases while the rest of the stack migrates terminology.
get_current_user = get_current_architect
get_current_user_id = get_current_architect_id
