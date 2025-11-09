"""Tests for briefing CRUD API endpoints."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_analytics import BriefingAnalytics
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization


@pytest.fixture
async def test_briefing_in_progress(
    db_session: AsyncSession,
    test_end_client: EndClient,
    test_template: BriefingTemplate,
) -> Briefing:
    """Create an in-progress briefing."""
    briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)
    return briefing


@pytest.fixture
async def test_briefing_completed(
    db_session: AsyncSession,
    test_end_client: EndClient,
    test_template: BriefingTemplate,
) -> Briefing:
    """Create a completed briefing with analytics."""

    briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.COMPLETED,
        current_question_order=3,
        answers={
            "1": "Casa",
            "2": "3 quartos",
            "3": "Sim",
        },
        completed_at=datetime.now(UTC),
        created_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    db_session.add(briefing)
    await db_session.flush()

    analytics = BriefingAnalytics(
        briefing_id=briefing.id,
        metrics={
            "duration_seconds": 600,
            "total_questions": 3,
            "answered_questions": 3,
            "required_answered": 3,
            "optional_answered": 0,
            "optional_skipped": 0,
            "completion_rate": 1.0,
        },
        observations="Test briefing completed successfully",
    )
    db_session.add(analytics)
    await db_session.commit()
    await db_session.refresh(briefing)
    return briefing


@pytest.fixture
async def test_briefing_cancelled(
    db_session: AsyncSession,
    test_end_client: EndClient,
    test_template: BriefingTemplate,
) -> Briefing:
    """Create a cancelled briefing."""
    briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.CANCELLED,
        current_question_order=2,
        answers={"1": "Apartamento"},
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)
    return briefing


@pytest.fixture
async def other_organization_briefing(
    db_session: AsyncSession,
    test_template: BriefingTemplate,
) -> Briefing:
    """Create a briefing for a different organization to test isolation."""
    other_org = Organization(
        name="Other Organization",
        whatsapp_business_account_id="999999999",
    )
    db_session.add(other_org)
    await db_session.flush()

    other_architect = Architect(
        organization_id=other_org.id,
        email="other@test.com",
        hashed_password=hash_password("password"),
        phone="+5511666666666",
        is_authorized=True,
    )
    db_session.add(other_architect)
    await db_session.flush()

    other_client = EndClient(
        organization_id=other_org.id,
        architect_id=other_architect.id,
        name="Other Client",
        phone="+5511777777777",
    )
    db_session.add(other_client)
    await db_session.flush()

    briefing = Briefing(
        end_client_id=other_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)
    return briefing


@pytest.mark.asyncio
async def test_list_briefings_unauthenticated(client: AsyncClient):
    """Test listing briefings without authentication returns 403."""
    response = await client.get("/api/briefings")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_briefings_empty(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Test listing briefings when there are none."""
    response = await client.get("/api/briefings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["limit"] == 20
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_briefings_with_data(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
    test_briefing_completed: Briefing,
    test_briefing_cancelled: Briefing,
):
    """Test listing briefings returns all briefings for organization."""
    response = await client.get("/api/briefings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    item = data["items"][0]
    assert "id" in item
    assert "status" in item
    assert "current_question_order" in item
    assert "created_at" in item
    assert "end_client" in item
    assert "template_version" in item


@pytest.mark.asyncio
async def test_list_briefings_filters_by_status(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
    test_briefing_completed: Briefing,
    test_briefing_cancelled: Briefing,
):
    """Test filtering briefings by status."""
    response = await client.get(
        "/api/briefings?status=in_progress",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "in_progress"

    response = await client.get(
        "/api/briefings?status=completed",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "completed"

    response = await client.get(
        "/api/briefings?status=cancelled",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_list_briefings_filters_by_client(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
    test_end_client: EndClient,
):
    """Test filtering briefings by end_client_id."""
    response = await client.get(
        f"/api/briefings?end_client_id={test_end_client.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(item["end_client"]["id"] == str(test_end_client.id) for item in data["items"])


@pytest.mark.asyncio
async def test_list_briefings_pagination(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
    test_briefing_completed: Briefing,
    test_briefing_cancelled: Briefing,
):
    """Test pagination of briefings list."""
    response = await client.get(
        "/api/briefings?limit=2&offset=0",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    response = await client.get(
        "/api/briefings?limit=2&offset=2",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1
    assert data["limit"] == 2
    assert data["offset"] == 2


@pytest.mark.asyncio
async def test_list_briefings_organization_isolation(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
    other_organization_briefing: Briefing,
):
    """Test that briefings are isolated by organization."""
    response = await client.get("/api/briefings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    briefing_ids = {item["id"] for item in data["items"]}
    assert str(test_briefing_in_progress.id) in briefing_ids
    assert str(other_organization_briefing.id) not in briefing_ids


@pytest.mark.asyncio
async def test_get_briefing_unauthenticated(
    client: AsyncClient,
    test_briefing_in_progress: Briefing,
):
    """Test getting briefing without authentication returns 403."""
    response = await client.get(f"/api/briefings/{test_briefing_in_progress.id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_briefing_success(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
):
    """Test getting briefing details successfully."""
    response = await client.get(
        f"/api/briefings/{test_briefing_in_progress.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_briefing_in_progress.id)
    assert data["status"] == "in_progress"
    assert data["current_question_order"] == 1
    assert "end_client" in data
    assert "template_version" in data
    assert "answers" in data


@pytest.mark.asyncio
async def test_get_briefing_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Test getting non-existent briefing returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/briefings/{fake_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_briefing_cross_organization(
    client: AsyncClient,
    auth_headers: dict[str, str],
    other_organization_briefing: Briefing,
):
    """Test getting briefing from another organization returns 404."""
    response = await client.get(
        f"/api/briefings/{other_organization_briefing.id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_complete_briefing_unauthenticated(
    client: AsyncClient,
    test_briefing_in_progress: Briefing,
):
    """Test completing briefing without authentication returns 403."""
    response = await client.post(f"/api/briefings/{test_briefing_in_progress.id}/complete")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_complete_briefing_success(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
    db_session: AsyncSession,
):
    """Test completing an in-progress briefing successfully."""
    test_briefing_in_progress.answers = {
        "1": "Casa",
        "2": "3 quartos",
        "3": "Sim",
    }
    test_briefing_in_progress.current_question_order = 3
    await db_session.commit()

    response = await client.post(
        f"/api/briefings/{test_briefing_in_progress.id}/complete",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "completed successfully" in data["message"].lower()

    await db_session.refresh(test_briefing_in_progress)
    assert test_briefing_in_progress.status == BriefingStatus.COMPLETED
    assert test_briefing_in_progress.completed_at is not None


@pytest.mark.asyncio
async def test_complete_briefing_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Test completing non-existent briefing returns 404."""
    fake_id = uuid.uuid4()
    response = await client.post(
        f"/api/briefings/{fake_id}/complete",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_complete_briefing_already_completed(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_completed: Briefing,
):
    """Test completing an already completed briefing returns 400."""
    response = await client.post(
        f"/api/briefings/{test_briefing_completed.id}/complete",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "cannot complete" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_complete_briefing_cancelled(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_cancelled: Briefing,
):
    """Test completing a cancelled briefing returns 400."""
    response = await client.post(
        f"/api/briefings/{test_briefing_cancelled.id}/complete",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "cannot complete" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_complete_briefing_cross_organization(
    client: AsyncClient,
    auth_headers: dict[str, str],
    other_organization_briefing: Briefing,
):
    """Test completing briefing from another organization returns 404."""
    response = await client.post(
        f"/api/briefings/{other_organization_briefing.id}/complete",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_complete_briefing_missing_required_answers(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_end_client: EndClient,
    test_template: BriefingTemplate,
):
    """Test completing briefing with missing required answers returns 400."""
    incomplete_briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=2,
        answers={"1": "Casa"},
    )
    db_session.add(incomplete_briefing)
    await db_session.commit()
    await db_session.refresh(incomplete_briefing)

    response = await client.post(
        f"/api/briefings/{incomplete_briefing.id}/complete",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "cannot complete" in response.json()["detail"].lower()
    assert (
        "required questions" in response.json()["detail"].lower()
        or "answer" in response.json()["detail"].lower()
    )


@pytest.mark.asyncio
async def test_cancel_briefing_unauthenticated(
    client: AsyncClient,
    test_briefing_in_progress: Briefing,
):
    """Test cancelling briefing without authentication returns 403."""
    response = await client.post(
        f"/api/briefings/{test_briefing_in_progress.id}/cancel",
        json={"reason": "Test cancellation"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cancel_briefing_success(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
    db_session: AsyncSession,
):
    """Test cancelling an in-progress briefing successfully."""
    response = await client.post(
        f"/api/briefings/{test_briefing_in_progress.id}/cancel",
        headers=auth_headers,
        json={"reason": "Client requested cancellation"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "cancelled successfully" in data["message"].lower()
    assert data["reason"] == "Client requested cancellation"

    await db_session.refresh(test_briefing_in_progress)
    assert test_briefing_in_progress.status == BriefingStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_briefing_without_reason(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
):
    """Test cancelling briefing without reason succeeds."""
    response = await client.post(
        f"/api/briefings/{test_briefing_in_progress.id}/cancel",
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_cancel_briefing_idempotent(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_cancelled: Briefing,
):
    """Test cancelling already cancelled briefing is idempotent."""
    response = await client.post(
        f"/api/briefings/{test_briefing_cancelled.id}/cancel",
        headers=auth_headers,
        json={"reason": "Another cancellation"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "already cancelled" in data["message"].lower()


@pytest.mark.asyncio
async def test_cancel_briefing_completed_fails(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_completed: Briefing,
):
    """Test cancelling completed briefing returns 400."""
    response = await client.post(
        f"/api/briefings/{test_briefing_completed.id}/cancel",
        headers=auth_headers,
        json={"reason": "Trying to cancel"},
    )

    assert response.status_code == 400
    assert "cannot cancel" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancel_briefing_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Test cancelling non-existent briefing returns 404."""
    fake_id = uuid.uuid4()
    response = await client.post(
        f"/api/briefings/{fake_id}/cancel",
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_briefing_cross_organization(
    client: AsyncClient,
    auth_headers: dict[str, str],
    other_organization_briefing: Briefing,
):
    """Test cancelling briefing from another organization returns 404."""
    response = await client.post(
        f"/api/briefings/{other_organization_briefing.id}/cancel",
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_analytics_unauthenticated(
    client: AsyncClient,
    test_briefing_completed: Briefing,
):
    """Test getting analytics without authentication returns 403."""
    response = await client.get(f"/api/briefings/{test_briefing_completed.id}/analytics")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_analytics_success(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_completed: Briefing,
):
    """Test getting analytics for completed briefing successfully."""
    response = await client.get(
        f"/api/briefings/{test_briefing_completed.id}/analytics",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["briefing_id"] == str(test_briefing_completed.id)
    assert "metrics" in data
    metrics = data["metrics"]
    assert metrics["total_questions"] == 3
    assert metrics["answered_questions"] == 3
    assert metrics["completion_rate"] == 1.0
    assert data["observations"] == "Test briefing completed successfully"


@pytest.mark.asyncio
async def test_get_analytics_in_progress_briefing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_in_progress: Briefing,
):
    """Test getting analytics for in-progress briefing returns 400."""
    response = await client.get(
        f"/api/briefings/{test_briefing_in_progress.id}/analytics",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "only available for completed" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_analytics_cancelled_briefing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_briefing_cancelled: Briefing,
):
    """Test getting analytics for cancelled briefing returns 400."""
    response = await client.get(
        f"/api/briefings/{test_briefing_cancelled.id}/analytics",
        headers=auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_analytics_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Test getting analytics for non-existent briefing returns 404."""
    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/briefings/{fake_id}/analytics",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_analytics_cross_organization(
    client: AsyncClient,
    auth_headers: dict[str, str],
    other_organization_briefing: Briefing,
):
    """Test getting analytics from another organization returns 404."""
    response = await client.get(
        f"/api/briefings/{other_organization_briefing.id}/analytics",
        headers=auth_headers,
    )

    assert response.status_code == 404
