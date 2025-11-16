"""End client factory for test data generation."""

import factory

from src.db.models.end_client import EndClient
from tests.factories.auth import ArchitectFactory
from tests.factories.base import AsyncSQLAlchemyFactory
from tests.factories.organization import OrganizationFactory


class EndClientFactory(AsyncSQLAlchemyFactory):
    """Factory for creating EndClient instances."""

    class Meta:
        model = EndClient

    organization = factory.SubFactory(OrganizationFactory)
    organization_id = factory.LazyAttribute(lambda o: o.organization.id)
    architect = factory.SubFactory(
        ArchitectFactory,
        organization=factory.SelfAttribute("..organization"),
    )
    architect_id = factory.LazyAttribute(lambda o: o.architect.id)
    name = factory.Faker("name")
    phone = factory.Sequence(lambda n: f"+55119{n:08d}")
    email = factory.Faker("email")
    meta = None
