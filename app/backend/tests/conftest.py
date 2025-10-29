from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from fakeredis.aioredis import FakeRedis

root_path = Path(__file__).parent
print(f"Loading test environment from: {root_path / '.env.test'}")
load_dotenv(root_path / ".env.test", override=False)  # CI env vars take precedence

# Now safe to import from src (after env loaded)
import asyncio  # noqa: E402
from collections.abc import AsyncGenerator, Generator  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
import sqlalchemy  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from pytest_mock import MockerFixture  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from src.core.cache.client import get_redis_client  # noqa: E402
from src.core.config import get_settings  # noqa: E402
from src.db.models.architect import Architect  # noqa: E402
from src.db.models.end_client import EndClient  # noqa: E402
from src.db.models.organization import Organization  # noqa: E402
from src.db.models.project_type import ProjectType  # noqa: E402
from src.db.session import Base, get_db  # noqa: E402
from src.main import app  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    """Validate test environment is loaded correctly."""
    settings = get_settings()

    if settings.ENVIRONMENT != "test":
        pytest.exit("Failed to load test environment config. ENVIRONMENT must be 'test'")


@pytest.fixture(autouse=True)
def avoid_external_requests(mocker: MockerFixture) -> None:
    """Block external HTTP requests during tests.

    Note: AsyncClient with ASGITransport doesn't make real HTTP requests,
    so we only block real network calls via HTTPTransport.
    """

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("External HTTP communication disabled for tests")

    # Block real HTTP requests
    mocker.patch("httpx._transports.default.AsyncHTTPTransport.handle_async_request", new=fail)
    mocker.patch("httpx._transports.default.HTTPTransport.handle_request", new=fail)


@pytest.fixture(autouse=True)
def mock_ai_service(mocker: MockerFixture) -> Any:
    """Mock AI service globally to prevent slow external API calls during tests.

    Tests that need specific AI service behavior can override this by patching
    'src.services.chat.get_ai_service' again in the test.
    """
    mock_service = mocker.Mock()
    mock_service.generate_response = mocker.AsyncMock(return_value="Mocked AI response")
    mocker.patch("src.services.chat.get_ai_service", return_value=mock_service)
    return mock_service


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine with PostgreSQL.

    Uses NullPool to ensure each operation gets a fresh connection,
    preventing 'another operation is in progress' errors with asyncpg.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL.get_secret_value(),
        echo=False,
        future=True,
        poolclass=NullPool,  # No connection pooling - each op gets fresh connection
    )

    # Create all tables once for the entire test session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables at the end of the test session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with table cleanup after each test."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session

    # Clean all tables after each test using TRUNCATE CASCADE
    # This is fast, handles foreign keys automatically, and resets sequences
    async with test_engine.begin() as conn:
        # Get all table names in reverse order (respects dependencies)
        table_names = ", ".join([table.name for table in reversed(Base.metadata.sorted_tables)])

        # TRUNCATE with CASCADE handles foreign keys, RESTART IDENTITY resets auto-increment
        await conn.execute(
            sqlalchemy.text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
        )


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)  # type: ignore
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def patch_redis() -> Generator[Any, Any, Any]:
    with patch("src.core.cache.client.Redis.from_url", return_value=FakeRedis()):

        get_redis_client.cache_clear()
        yield


@pytest.fixture(autouse=True)
async def clear_redis(patch_redis: Any):
    """Clear Redis cache and rate limit storage before/after each test."""
    from src.core.rate_limit import limiter, limiter_authenticated

    client = get_redis_client()
    await client.flushdb()

    # Clear rate limit storage (memory storage for tests)
    limiter.reset()
    limiter_authenticated.reset()

    yield

    await client.flushdb()
    limiter.reset()
    limiter_authenticated.reset()


@pytest.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create a test organization."""

    organization = Organization(name="Test Organization")
    db_session.add(organization)
    await db_session.commit()
    await db_session.refresh(organization)
    return organization


@pytest.fixture
async def test_architect(
    db_session: AsyncSession, test_organization: Organization
) -> Architect:
    """Create test architect (authenticated actor)."""
    from src.core.security import hash_password

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
async def test_user(test_architect: Architect) -> Architect:
    """Backwards-compatible fixture returning the primary architect."""

    return test_architect


@pytest.fixture
def auth_headers(test_architect: Architect) -> dict[str, str]:
    """Create authentication headers for test architect."""
    from src.core.security import create_access_token

    token = create_access_token(data={"sub": str(test_architect.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def project_type_residencial(db_session: AsyncSession) -> ProjectType:
    """Create a 'residencial' project type."""
    project_type = ProjectType(
        slug="residencial",
        label="Residencial",
        description="Projetos residenciais (casas, apartamentos)",
        is_active=True,
    )
    db_session.add(project_type)
    await db_session.commit()
    await db_session.refresh(project_type)
    return project_type


@pytest.fixture
async def project_type_reforma(db_session: AsyncSession) -> ProjectType:
    """Create a 'reforma' project type."""
    project_type = ProjectType(
        slug="reforma",
        label="Reforma",
        description="Reformas e renovações",
        is_active=True,
    )
    db_session.add(project_type)
    await db_session.commit()
    await db_session.refresh(project_type)
    return project_type


@pytest.fixture
async def project_type_comercial(db_session: AsyncSession) -> ProjectType:
    """Create a 'comercial' project type."""
    project_type = ProjectType(
        slug="comercial",
        label="Comercial",
        description="Projetos comerciais",
        is_active=True,
    )
    db_session.add(project_type)
    await db_session.commit()
    await db_session.refresh(project_type)
    return project_type


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
