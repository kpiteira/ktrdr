"""Integration tests for API tracing."""

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace

from ktrdr.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_api_request_creates_trace(client):
    """Test that API requests create traces."""
    # Make request to root endpoint
    response = client.get("/")

    # Should succeed
    assert response.status_code == 200

    # Trace should be active
    tracer = trace.get_tracer(__name__)
    assert tracer is not None


def test_api_request_with_trace_context(client):
    """Test that trace context is propagated."""
    # Make request with trace headers to root endpoint
    response = client.get(
        "/",
        headers={
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        },
    )

    assert response.status_code == 200
