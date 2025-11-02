"""Pytest configuration and shared fixtures.

This file loads test environment and imports all fixtures from the fixtures/ directory.
"""

from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load test environment BEFORE importing anything from src
root_path = Path(__file__).parent
print(f"Loading test environment from: {root_path / '.env.test'}")
load_dotenv(root_path / ".env.test", override=False)  # CI env vars take precedence

# Now safe to import from src (after env is loaded)
from src.core.config import get_settings  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    """Validate test environment is loaded correctly."""
    settings = get_settings()

    if settings.ENVIRONMENT != "test":
        pytest.exit("Failed to load test environment config. ENVIRONMENT must be 'test'")


# Import all fixtures from fixtures/ directory
# This makes them available to all test files without explicit imports
from tests.fixtures import *  # noqa: E402, F403, F401
