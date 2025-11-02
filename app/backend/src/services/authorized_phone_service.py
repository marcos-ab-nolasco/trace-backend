"""Service for managing authorized phones."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.authorized_phone import AuthorizedPhone


class PhoneAlreadyExistsError(Exception):
    """Raised when trying to add a phone that already exists for the organization."""

    pass


class PhoneNotFoundError(Exception):
    """Raised when phone is not found."""

    pass


class MinimumPhonesError(Exception):
    """Raised when trying to remove the last phone from an organization."""

    pass


class AuthorizedPhoneService:
    """Service for managing authorized phones for organizations."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def add_phone(
        self,
        organization_id: UUID,
        phone_number: str,
        added_by_architect_id: UUID,
    ) -> AuthorizedPhone:
        """Add a new authorized phone to an organization.

        Args:
            organization_id: Organization ID
            phone_number: Phone number to authorize (normalized format)
            added_by_architect_id: Architect who added this phone

        Returns:
            Created AuthorizedPhone

        Raises:
            PhoneAlreadyExistsError: If phone already exists for this organization
        """
        try:
            phone = AuthorizedPhone(
                organization_id=organization_id,
                phone_number=phone_number,
                added_by_architect_id=added_by_architect_id,
                is_active=True,
            )
            self.db.add(phone)
            await self.db.commit()
            await self.db.refresh(phone)
            return phone

        except IntegrityError as e:
            await self.db.rollback()
            raise PhoneAlreadyExistsError(
                f"Phone {phone_number} is already authorized for this organization"
            ) from e

    async def remove_phone(
        self,
        phone_id: UUID,
        organization_id: UUID,
    ) -> None:
        """Remove an authorized phone from an organization.

        Args:
            phone_id: Phone ID to remove
            organization_id: Organization ID (for authorization check)

        Raises:
            PhoneNotFoundError: If phone doesn't exist
            MinimumPhonesError: If this is the last phone (minimum 1 required)
        """
        # Get the phone
        phone = await self.get_phone_by_id(phone_id, organization_id)

        # Check if this is the last active phone
        count_result = await self.db.execute(
            select(func.count(AuthorizedPhone.id)).where(
                AuthorizedPhone.organization_id == organization_id,
                AuthorizedPhone.is_active == True,  # noqa: E712
            )
        )
        active_count = count_result.scalar_one()

        if active_count <= 1:
            raise MinimumPhonesError(
                "Cannot remove the last authorized phone. Organization must have at least 1 authorized phone."
            )

        # Delete the phone
        await self.db.delete(phone)
        await self.db.commit()

    async def list_phones(
        self,
        organization_id: UUID,
        include_inactive: bool = False,
    ) -> list[AuthorizedPhone]:
        """List authorized phones for an organization.

        Args:
            organization_id: Organization ID
            include_inactive: If True, include inactive phones

        Returns:
            List of authorized phones
        """
        query = select(AuthorizedPhone).where(AuthorizedPhone.organization_id == organization_id)

        if not include_inactive:
            query = query.where(AuthorizedPhone.is_active == True)  # noqa: E712

        query = query.order_by(AuthorizedPhone.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def is_authorized(
        self,
        organization_id: UUID,
        phone_number: str,
    ) -> bool:
        """Check if a phone number is authorized for an organization.

        Args:
            organization_id: Organization ID
            phone_number: Phone number to check

        Returns:
            True if phone is authorized and active, False otherwise
        """
        result = await self.db.execute(
            select(AuthorizedPhone).where(
                AuthorizedPhone.organization_id == organization_id,
                AuthorizedPhone.phone_number == phone_number,
                AuthorizedPhone.is_active == True,  # noqa: E712
            )
        )
        phone = result.scalar_one_or_none()
        return phone is not None

    async def get_phone_by_id(
        self,
        phone_id: UUID,
        organization_id: UUID,
    ) -> AuthorizedPhone:
        """Get an authorized phone by ID.

        Args:
            phone_id: Phone ID
            organization_id: Organization ID (for authorization check)

        Returns:
            AuthorizedPhone

        Raises:
            PhoneNotFoundError: If phone doesn't exist
        """
        result = await self.db.execute(
            select(AuthorizedPhone).where(
                AuthorizedPhone.id == phone_id,
                AuthorizedPhone.organization_id == organization_id,
            )
        )
        phone = result.scalar_one_or_none()

        if not phone:
            raise PhoneNotFoundError(f"Phone with ID {phone_id} not found")

        return phone
