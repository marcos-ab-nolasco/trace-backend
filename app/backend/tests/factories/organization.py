"""Organization factory for test data generation."""

import factory

from src.db.models.organization import Organization
from tests.factories.base import AsyncSQLAlchemyFactory


class OrganizationFactory(AsyncSQLAlchemyFactory):
    """Factory for creating Organization instances."""

    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Test Organization {n}")
    whatsapp_business_account_id = None
    settings = None

    class Params:
        # Trait: Organization with WhatsApp enabled
        with_whatsapp = factory.Trait(
            whatsapp_business_account_id=factory.Sequence(
                lambda n: f"whatsapp_business_account_{n}"
            ),
            settings=factory.Dict(
                {
                    "whatsapp_enabled": True,
                    "whatsapp_phone_number_id": factory.Faker("uuid4"),
                }
            ),
        )
