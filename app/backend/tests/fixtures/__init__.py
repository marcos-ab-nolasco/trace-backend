"""Centralized test fixtures.

This module re-exports all fixtures from fixture modules to enable
direct imports like: `from fixtures import test_organization`
"""

from .auth import (
    auth_headers,
    auth_headers_whatsapp,
    test_architect,
    test_architect_with_whatsapp,
    test_user,
)
from .briefing import (
    briefing_with_session,
    template_version_simple,
    template_with_conditions,
    test_briefing,
    test_whatsapp_session,
)
from .client import client
from .clients import test_end_client
from .database import db_session, event_loop, test_engine
from .mocks import (
    avoid_external_requests,
    clear_redis,
    mock_ai_service,
    mock_extraction_service,
    mock_template_service,
    mock_whatsapp_service,
    patch_redis,
)
from .organization import test_organization, test_organization_with_whatsapp
from .templates import (
    project_type_comercial,
    project_type_reforma,
    project_type_residencial,
    test_project_type,
    test_template,
)

__all__ = [
    "event_loop",
    "test_engine",
    "db_session",
    "test_organization",
    "test_organization_with_whatsapp",
    "test_architect",
    "test_architect_with_whatsapp",
    "test_user",
    "auth_headers",
    "auth_headers_whatsapp",
    "test_end_client",
    "test_project_type",
    "project_type_residencial",
    "project_type_reforma",
    "project_type_comercial",
    "test_template",
    "template_version_simple",
    "template_with_conditions",
    "test_briefing",
    "test_whatsapp_session",
    "briefing_with_session",
    "client",
    "avoid_external_requests",
    "mock_ai_service",
    "mock_extraction_service",
    "mock_template_service",
    "mock_whatsapp_service",
    "patch_redis",
    "clear_redis",
]
