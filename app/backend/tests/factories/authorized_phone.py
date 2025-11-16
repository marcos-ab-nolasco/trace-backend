"""Authorized phone factory for test data generation."""

import factory

from src.db.models.authorized_phone import AuthorizedPhone
from tests.factories.auth import ArchitectFactory
from tests.factories.base import AsyncSQLAlchemyFactory
from tests.factories.organization import OrganizationFactory


class AuthorizedPhoneFactory(AsyncSQLAlchemyFactory):
    """Factory for creating AuthorizedPhone instances."""

    class Meta:
        model = AuthorizedPhone

    organization = factory.SubFactory(OrganizationFactory)
    organization_id = factory.LazyAttribute(lambda o: o.organization.id)
    phone_number = factory.Sequence(lambda n: f"+55119{n:08d}")
    added_by = factory.SubFactory(
        ArchitectFactory,
        organization=factory.SelfAttribute("..organization"),
    )
    added_by_architect_id = factory.LazyAttribute(lambda o: o.added_by.id)
    is_active = True

    class Params:
        # Trait: Inactive authorized phone
        inactive = factory.Trait(is_active=False)
