"""Pytest configuration and shared fixtures.

This file loads test environment and imports all fixtures from the fixtures/ directory.
"""

from pathlib import Path

import pytest
from dotenv import load_dotenv

root_path = Path(__file__).parent
print(f"Loading test environment from: {root_path / '.env.test'}")
load_dotenv(root_path / ".env.test", override=False)

from src.core.config import get_settings  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    """Validate test environment is loaded correctly."""
    settings = get_settings()

    if settings.ENVIRONMENT != "test":
        pytest.exit("Failed to load test environment config. ENVIRONMENT must be 'test'")


from tests.fixtures import *  # noqa: E402, F403


# Factory-boy configuration
@pytest.fixture(autouse=True)
def _configure_factories(db_session):  # noqa: F811
    """Configure factory-boy to use the test database session.

    This fixture runs automatically before each test to ensure all factories
    use the correct async database session.
    """
    from tests.factories import (
        ArchitectFactory,
        AuthorizedPhoneFactory,
        BriefingFactory,
        BriefingTemplateFactory,
        EndClientFactory,
        OrganizationFactory,
        ProjectTypeFactory,
        TemplateVersionFactory,
        WhatsAppSessionFactory,
    )

    # Set the session for all factories
    for factory_class in [
        OrganizationFactory,
        ArchitectFactory,
        EndClientFactory,
        AuthorizedPhoneFactory,
        ProjectTypeFactory,
        TemplateVersionFactory,
        BriefingTemplateFactory,
        BriefingFactory,
        WhatsAppSessionFactory,
    ]:
        factory_class._meta.sqlalchemy_session = db_session
