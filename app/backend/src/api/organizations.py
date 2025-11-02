"""API endpoints for organization management."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_architect
from src.db.models.architect import Architect
from src.db.session import get_db
from src.schemas.authorized_phone import (
    AuthorizedPhoneCreate,
    AuthorizedPhoneList,
    AuthorizedPhoneRead,
)
from src.services.authorized_phone_service import (
    AuthorizedPhoneService,
    MinimumPhonesError,
    PhoneAlreadyExistsError,
    PhoneNotFoundError,
)

router = APIRouter(prefix="/api/organizations", tags=["organizations"])

logger = logging.getLogger(__name__)


@router.get("/authorized-phones", response_model=AuthorizedPhoneList)
async def list_authorized_phones(
    architect: Annotated[Architect, Depends(get_current_architect)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthorizedPhoneList:
    """List all authorized phones for the current architect's organization."""
    service = AuthorizedPhoneService(db)

    phones = await service.list_phones(
        organization_id=architect.organization_id,
        include_inactive=False,
    )

    return AuthorizedPhoneList(
        phones=[AuthorizedPhoneRead.model_validate(p) for p in phones],
        total=len(phones),
    )


@router.post(
    "/authorized-phones",
    response_model=AuthorizedPhoneRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_authorized_phone(
    phone_data: AuthorizedPhoneCreate,
    architect: Annotated[Architect, Depends(get_current_architect)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthorizedPhoneRead:
    """Add a new authorized phone to the organization."""
    service = AuthorizedPhoneService(db)

    try:
        phone = await service.add_phone(
            organization_id=architect.organization_id,
            phone_number=phone_data.phone_number,
            added_by_architect_id=architect.id,
        )

        logger.info(
            "Authorized phone added: phone=%s organization_id=%s added_by=%s",
            phone_data.phone_number,
            architect.organization_id,
            architect.id,
        )

        return AuthorizedPhoneRead.model_validate(phone)

    except PhoneAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/authorized-phones/{phone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_authorized_phone(
    phone_id: UUID,
    architect: Annotated[Architect, Depends(get_current_architect)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete an authorized phone from the organization."""
    service = AuthorizedPhoneService(db)

    try:
        await service.remove_phone(
            phone_id=phone_id,
            organization_id=architect.organization_id,
        )

        logger.info(
            "Authorized phone removed: phone_id=%s organization_id=%s removed_by=%s",
            phone_id,
            architect.organization_id,
            architect.id,
        )

    except PhoneNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorized phone not found",
        ) from e
    except MinimumPhonesError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
