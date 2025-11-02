"""Client-related test fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization


@pytest.fixture
async def test_end_client(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
) -> EndClient:
    """Create a test end client."""
    end_client = EndClient(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        name="João Silva",
        phone="+5511987654321",
        email="joao@example.com",
    )
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)
    return end_client
