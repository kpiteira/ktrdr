"""Integration tests for Jaeger trace collection."""

import os
import time

import httpx
import pytest


@pytest.fixture
def jaeger_url():
    """Jaeger API base URL."""
    return os.getenv("JAEGER_URL", "http://localhost:16686")


@pytest.fixture
def api_url():
    """KTRDR API base URL."""
    return os.getenv("KTRDR_API_URL", "http://localhost:8000")


@pytest.mark.skipif(
    os.getenv("SKIP_JAEGER_TESTS") == "true",
    reason="Jaeger not available (set SKIP_JAEGER_TESTS=false to run)",
)
def test_jaeger_receives_traces(jaeger_url, api_url):
    """Test that Jaeger receives traces from the API."""
    # Make a request to the API
    response = httpx.get(f"{api_url}/")
    assert response.status_code == 200

    # Wait for traces to be processed by Jaeger
    time.sleep(2)

    # Query Jaeger for traces
    with httpx.Client() as client:
        # Get list of services
        services_response = client.get(f"{jaeger_url}/api/services")
        assert services_response.status_code == 200
        services = services_response.json()

        # Verify ktrdr-api service exists
        assert "data" in services
        assert "ktrdr-api" in services["data"]

        # Get traces for ktrdr-api service
        traces_response = client.get(
            f"{jaeger_url}/api/traces",
            params={"service": "ktrdr-api", "limit": 10},
        )
        assert traces_response.status_code == 200
        traces_data = traces_response.json()

        # Verify traces exist
        assert "data" in traces_data
        assert len(traces_data["data"]) > 0

        # Verify trace structure
        first_trace = traces_data["data"][0]
        assert "spans" in first_trace
        assert len(first_trace["spans"]) > 0

        # Verify span attributes
        first_span = first_trace["spans"][0]
        assert "operationName" in first_span
        assert "tags" in first_span

        # Verify service name tag
        tags = {tag["key"]: tag["value"] for tag in first_span["tags"]}
        assert "service.name" in tags
        assert tags["service.name"] == "ktrdr-api"


@pytest.mark.skipif(
    os.getenv("SKIP_JAEGER_TESTS") == "true",
    reason="Jaeger not available (set SKIP_JAEGER_TESTS=false to run)",
)
def test_jaeger_ui_accessible(jaeger_url):
    """Test that Jaeger UI is accessible."""
    response = httpx.get(jaeger_url)
    assert response.status_code == 200
    assert "Jaeger UI" in response.text or "jaeger" in response.text.lower()
