"""
Root conftest.py for tania-signal-copier tests.

Contains shared fixtures and configuration for all test modules.
"""

import os

import pytest
from dotenv import load_dotenv

# Load environment variables at test collection time
load_dotenv()


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test requiring MT5 Docker container",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running",
    )


@pytest.fixture(scope="session")
def mt5_credentials() -> dict | None:
    """Provide MT5 credentials from environment variables.

    Returns:
        dict with login, password, server, host, port or None if not configured
    """
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    host = os.getenv("MT5_DOCKER_HOST", "localhost")
    port = os.getenv("MT5_DOCKER_PORT", "8001")

    if not all([login, password, server]):
        return None

    return {
        "login": int(login),
        "password": password,
        "server": server,
        "host": host,
        "port": int(port),
    }
