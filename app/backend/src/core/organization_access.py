"""Organization access control for multi-tenant isolation.

This module provides decorators and dependencies to enforce organization-level isolation,
preventing cross-tenant data leakage (critical for GDPR compliance).
"""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Annotated, ParamSpec, TypeVar
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_architect
from src.db.models.architect import Architect

logger = logging.getLogger(__name__)
P = ParamSpec("P")
R = TypeVar("R")


def require_organization_access(
    param_name: str = "architect_id",
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator to enforce organization isolation on endpoints.

    This decorator verifies that the authenticated architect can only access resources
    from their own organization. It validates that resource IDs passed in the request
    belong to the authenticated architect's organization.

    Args:
        param_name: Name of the parameter containing the resource architect_id to validate.
                   Defaults to "architect_id".

    Usage:
        @router.post("/briefings/start")
        @require_organization_access("architect_id")
        async def start_briefing(
            request: StartBriefingRequest,
            current_architect: Architect = Depends(get_current_architect),
            db: AsyncSession = Depends(get_db_session),
        ):
            ...

    Raises:
        HTTPException: 403 Forbidden if architect tries to access another organization's resources.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            current_architect: Architect | None = kwargs.get("current_architect")
            db_session: AsyncSession | None = kwargs.get("db_session")

            if current_architect is None:
                current_architect = kwargs.get("current_user")

            if current_architect is None or db_session is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies for organization access control",
                )

            resource_architect_id = None

            if param_name in kwargs:
                resource_architect_id = kwargs[param_name]
            else:
                for _key, value in kwargs.items():
                    if hasattr(value, param_name):
                        resource_architect_id = getattr(value, param_name)
                        break

            if resource_architect_id is None:
                logger.warning(
                    f"Organization access validation skipped: parameter '{param_name}' not found"
                )
                return await func(*args, **kwargs)

            if isinstance(resource_architect_id, str):
                try:
                    resource_architect_id = UUID(resource_architect_id)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid UUID format for {param_name}",
                    ) from None

            result = await db_session.execute(
                select(Architect).where(Architect.id == resource_architect_id)
            )
            resource_architect = result.scalar_one_or_none()

            if resource_architect is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Architect not found: {resource_architect_id}",
                )

            if resource_architect.organization_id != current_architect.organization_id:
                logger.warning(
                    f"Cross-organization access attempt: architect {current_architect.id} "
                    f"(org {current_architect.organization_id}) tried to access "
                    f"architect {resource_architect_id} (org {resource_architect.organization_id})"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to access resources from another organization",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def get_current_organization_id(
    current_architect: Annotated[Architect, Depends(get_current_architect)],
) -> UUID:
    """Dependency to get the current architect's organization ID.

    Useful for filtering queries to only resources from the current organization.
    """
    return current_architect.organization_id
