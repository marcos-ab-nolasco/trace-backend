"""Centralized test fixtures.

This module re-exports all fixtures from fixture modules to enable
direct imports like: `from fixtures import test_organization`
"""

# Database fixtures
# Auth fixtures
from .auth import auth_headers, test_architect, test_architect_with_whatsapp, test_user

# HTTP client fixtures
from .client import client

# Client fixtures (end clients)
from .clients import test_end_client
from .database import db_session, event_loop, test_engine

# Mock fixtures
from .mocks import avoid_external_requests, clear_redis, mock_ai_service, patch_redis

# Organization fixtures
from .organization import test_organization, test_organization_with_whatsapp

# Template fixtures
from .templates import (
    project_type_comercial,
    project_type_reforma,
    project_type_residencial,
    test_project_type,
    test_template,
)

__all__ = [
    # Database
    "event_loop",
    "test_engine",
    "db_session",
    # Organization
    "test_organization",
    "test_organization_with_whatsapp",
    # Auth
    "test_architect",
    "test_architect_with_whatsapp",
    "test_user",
    "auth_headers",
    # Clients
    "test_end_client",
    # Templates
    "test_project_type",
    "project_type_residencial",
    "project_type_reforma",
    "project_type_comercial",
    "test_template",
    # HTTP Client
    "client",
    # Mocks
    "avoid_external_requests",
    "mock_ai_service",
    "patch_redis",
    "clear_redis",
]
