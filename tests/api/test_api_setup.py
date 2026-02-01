"""
API setup tests.

This module tests the setup and initialization of the API application.
"""

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.main import create_application
from ktrdr.config.settings import get_api_settings
from ktrdr.version import __version__


@pytest.fixture
def client():
    """Create a test client for the API."""
    app = create_application()
    return TestClient(app)


def test_api_root(client):
    """Test that the API root returns the expected response."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "KTRDR API is running" in response.json()["message"]


def test_api_health_check(client):
    """Test that the health check endpoint returns the expected response."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    # Check core health fields
    assert data["status"] == "ok"
    assert data["version"] == __version__
    # orphan_detector may be None in test environment
    assert "orphan_detector" in data


def test_api_openapi_spec(client):
    """Test that the OpenAPI specification is generated correctly."""
    config = get_api_settings()
    response = client.get(f"{config.api_prefix}/openapi.json")
    assert response.status_code == 200

    # Verify the basic structure of the OpenAPI specification
    openapi_spec = response.json()
    assert "openapi" in openapi_spec
    assert "paths" in openapi_spec
    assert "info" in openapi_spec
    assert openapi_spec["info"]["title"] == "KTRDR API"
    assert openapi_spec["info"]["version"] == __version__  # Version from ktrdr.version
