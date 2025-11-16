"""Authentication-related factories for test data generation."""

import factory

from src.core.security import create_access_token, hash_password
from src.db.models.architect import Architect
from tests.factories.base import AsyncSQLAlchemyFactory
from tests.factories.organization import OrganizationFactory


class ArchitectFactory(AsyncSQLAlchemyFactory):
    """Factory for creating Architect instances."""

    class Meta:
        model = Architect

    organization = factory.SubFactory(OrganizationFactory)
    organization_id = factory.LazyAttribute(lambda o: o.organization.id)
    email = factory.Sequence(lambda n: f"architect{n}@example.com")
    hashed_password = factory.LazyFunction(lambda: hash_password("testpassword123"))
    full_name = factory.Faker("name")
    phone = factory.Sequence(lambda n: f"+55119{n:08d}")
    is_authorized = True
    meta = None

    class Params:
        # Trait: Unauthorized architect
        unauthorized = factory.Trait(is_authorized=False)

        # Trait: Architect with WhatsApp-enabled organization
        with_whatsapp = factory.Trait(
            organization=factory.SubFactory(OrganizationFactory, with_whatsapp=True)
        )


def make_auth_headers(architect: Architect) -> dict[str, str]:
    """Create authentication headers for an architect.

    Args:
        architect: The architect to create headers for

    Returns:
        Dictionary with Authorization header containing Bearer token
    """
    token = create_access_token(data={"sub": str(architect.id)})
    return {"Authorization": f"Bearer {token}"}
