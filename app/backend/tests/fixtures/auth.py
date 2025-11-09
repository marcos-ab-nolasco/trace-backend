"""Authentication-related test fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token, hash_password
from src.db.models.architect import Architect
from src.db.models.organization import Organization


@pytest.fixture
async def test_architect(db_session: AsyncSession, test_organization: Organization) -> Architect:
    """Create test architect (authenticated actor)."""
    architect = Architect(
        organization_id=test_organization.id,
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Test Architect",
        phone="+5511999999999",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)
    return architect


@pytest.fixture
async def test_architect_with_whatsapp(
    db_session: AsyncSession, test_organization_with_whatsapp: Organization
) -> Architect:
    """Create test architect with WhatsApp-enabled organization."""
    architect = Architect(
        organization_id=test_organization_with_whatsapp.id,
        email="whatsapp@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="WhatsApp Test Architect",
        phone="+5511888888888",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)
    return architect


@pytest.fixture
async def test_user(test_architect: Architect) -> Architect:
    """Backwards-compatible fixture returning the primary architect."""
    return test_architect


@pytest.fixture
def auth_headers(test_architect: Architect) -> dict[str, str]:
    """Create authentication headers for test architect."""
    token = create_access_token(data={"sub": str(test_architect.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_whatsapp(test_architect_with_whatsapp: Architect) -> dict[str, str]:
    """Create authentication headers for WhatsApp test architect."""
    token = create_access_token(data={"sub": str(test_architect_with_whatsapp.id)})
    return {"Authorization": f"Bearer {token}"}
