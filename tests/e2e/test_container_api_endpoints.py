"""
Container-based End-to-End tests for API endpoints.

These tests run against the actual containerized API to ensure all endpoints
work correctly in the production environment. They test the complete stack
including the refactored IB components.
"""

import pytest
import httpx
import asyncio
import time
import json
from typing import Dict, Any, List
from datetime import datetime, timedelta

# Test configuration
API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 30.0


@pytest.fixture(scope="session")
def api_client():
    """Create HTTP client for API testing."""
    return httpx.Client(base_url=API_BASE_URL, timeout=API_TIMEOUT)


class TestContainerAPIHealth:
    """Test basic API health and availability."""

    def test_api_health_endpoint(self, api_client):
        """Test that the API health endpoint responds correctly."""
        response = api_client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_api_docs_available(self, api_client):
        """Test that API documentation is available."""
        response = api_client.get("/api/v1/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_api_openapi_spec(self, api_client):
        """Test that OpenAPI spec is available."""
        response = api_client.get("/api/v1/openapi.json")
        assert response.status_code == 200

        spec = response.json()
        assert "openapi" in spec
        assert "info" in spec
        assert spec["info"]["title"] == "KTRDR API"


class TestContainerIBEndpoints:
    """Test IB-related API endpoints in container environment."""

    def test_ib_status_endpoint(self, api_client):
        """Test IB status endpoint returns proper structure."""
        response = api_client.get("/api/v1/ib/status")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data

        # Validate IB status structure
        ib_status = data["data"]
        required_fields = [
            "ib_available",
            "connection",
            "connection_metrics",
            "data_metrics",
        ]
        for field in required_fields:
            assert field in ib_status, f"Missing field: {field}"

        # Validate connection structure
        connection = ib_status["connection"]
        connection_fields = [
            "connected",
            "host",
            "port",
            "client_id",
            "connection_time",
        ]
        for field in connection_fields:
            assert field in connection, f"Missing connection field: {field}"

        # Validate metrics structure
        connection_metrics = ib_status["connection_metrics"]
        assert "total_connections" in connection_metrics

    def test_ib_health_endpoint(self, api_client):
        """Test IB health endpoint responds appropriately."""
        response = api_client.get("/api/v1/ib/health")

        # Should return either 200 (healthy) or 503 (unhealthy)
        assert response.status_code in [200, 503]

        data = response.json()
        assert "data" in data

        health_data = data["data"]
        assert "healthy" in health_data
        assert isinstance(health_data["healthy"], bool)

        if not health_data["healthy"]:
            assert "error_message" in health_data

    def test_ib_config_endpoint(self, api_client):
        """Test IB configuration endpoint."""
        response = api_client.get("/api/v1/ib/config")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        config_data = data["data"]
        expected_fields = ["host", "port", "client_id_range", "timeout"]
        for field in expected_fields:
            assert field in config_data, f"Missing config field: {field}"

    def test_ib_cleanup_endpoint(self, api_client):
        """Test IB cleanup endpoint (should be safe to call)."""
        response = api_client.post("/api/v1/ib/cleanup")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data

        cleanup_result = data["data"]
        assert "connections_closed" in cleanup_result
        assert isinstance(cleanup_result["connections_closed"], int)

    def test_ib_symbol_discovery(self, api_client):
        """Test symbol discovery endpoint with a known symbol."""
        symbol_request = {"symbol": "AAPL", "force_refresh": False}

        response = api_client.post("/api/v1/ib/symbols/discover", json=symbol_request)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        discovery_result = data["data"]
        assert "symbol_info" in discovery_result
        assert "cached" in discovery_result
        assert "discovery_time_ms" in discovery_result

        # AAPL should be discoverable (or cached)
        if discovery_result["symbol_info"]:
            symbol_info = discovery_result["symbol_info"]
            assert symbol_info["symbol"] == "AAPL"
            assert "instrument_type" in symbol_info
            assert "exchange" in symbol_info

    def test_ib_discovered_symbols_list(self, api_client):
        """Test getting list of discovered symbols."""
        response = api_client.get("/api/v1/ib/symbols/discovered")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        symbols_data = data["data"]
        assert "symbols" in symbols_data
        assert "total_count" in symbols_data
        assert "instrument_types" in symbols_data
        assert "cache_stats" in symbols_data

        assert isinstance(symbols_data["symbols"], list)
        assert isinstance(symbols_data["total_count"], int)


class TestContainerDataEndpoints:
    """Test data-related API endpoints."""

    def test_data_info_endpoint(self, api_client):
        """Test data info endpoint."""
        response = api_client.get("/api/v1/data/info")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "data" in data

        data_info = data["data"]
        assert "available_symbols" in data_info
        assert "data_directory" in data_info

    def test_data_load_endpoint_validation(self, api_client):
        """Test data load endpoint with invalid parameters."""
        # Test missing required parameters
        response = api_client.post("/api/v1/data/load", json={})
        assert response.status_code == 422  # Validation error

        # Test invalid timeframe
        invalid_request = {
            "symbol": "AAPL",
            "timeframe": "invalid_timeframe",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
        }

        response = api_client.post("/api/v1/data/load", json=invalid_request)
        assert response.status_code in [400, 422]  # Client error

    def test_data_cached_endpoint_local_mode(self, api_client):
        """Test cached data endpoint (should work without IB)."""
        # Use GET endpoint for cached/local data
        response = api_client.get("/api/v1/data/AAPL/1d")

        # Should return 200 even if no local data (graceful handling)
        assert response.status_code == 200

        data = response.json()
        # Should succeed with empty data structure when no cached data
        assert data["success"] is True
        assert "data" in data

        # Should return empty OHLCV structure when no data available
        ohlcv_data = data["data"]
        assert "dates" in ohlcv_data
        assert "ohlcv" in ohlcv_data
        assert "metadata" in ohlcv_data
        # Empty data should have empty arrays
        assert isinstance(ohlcv_data["dates"], list)
        assert isinstance(ohlcv_data["ohlcv"], list)


class TestContainerSystemEndpoints:
    """Test system-level API endpoints."""

    def test_system_status_endpoint(self, api_client):
        """Test system status endpoint."""
        response = api_client.get("/api/v1/system/status")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        status_data = data["data"]
        assert "version" in status_data
        assert "environment" in status_data
        assert "uptime_seconds" in status_data

    def test_system_config_endpoint(self, api_client):
        """Test system configuration endpoint."""
        response = api_client.get("/api/v1/system/config")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        config_data = data["data"]
        assert "version" in config_data
        assert "environment" in config_data


@pytest.mark.asyncio
class TestContainerAsyncEndpoints:
    """Test endpoints that require async operations."""

    async def test_concurrent_ib_status_requests(self):
        """Test multiple concurrent requests to IB status."""
        async with httpx.AsyncClient(
            base_url=API_BASE_URL, timeout=API_TIMEOUT
        ) as client:
            tasks = []

            # Create 5 concurrent requests
            for i in range(5):
                task = client.get("/api/v1/ib/status")
                tasks.append(task)

            # Execute all requests concurrently
            responses = await asyncio.gather(*tasks)

            # All should succeed
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True

    async def test_ib_symbol_discovery_concurrent(self):
        """Test concurrent symbol discovery requests."""
        async with httpx.AsyncClient(
            base_url=API_BASE_URL, timeout=API_TIMEOUT
        ) as client:
            symbols = ["AAPL", "MSFT", "GOOGL"]
            tasks = []

            for symbol in symbols:
                request_data = {"symbol": symbol, "force_refresh": False}
                task = client.post("/api/v1/ib/symbols/discover", json=request_data)
                tasks.append(task)

            responses = await asyncio.gather(*tasks)

            # All should succeed or fail gracefully
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True


class TestContainerAPIPerformance:
    """Test API performance characteristics."""

    def test_api_response_times(self, api_client):
        """Test that API endpoints respond within reasonable time."""
        endpoints = [
            "/api/v1/health",
            "/api/v1/system/status",
            "/api/v1/ib/status",
            "/api/v1/ib/config",
            "/api/v1/data/info",
        ]

        for endpoint in endpoints:
            start_time = time.time()
            response = api_client.get(endpoint)
            elapsed = time.time() - start_time

            assert response.status_code == 200, f"Endpoint {endpoint} failed"
            assert elapsed < 5.0, f"Endpoint {endpoint} too slow: {elapsed:.2f}s"

    def test_api_error_handling(self, api_client):
        """Test API error handling for invalid requests."""
        # Test non-existent endpoint
        response = api_client.get("/api/v1/nonexistent/endpoint")
        assert response.status_code == 404

        # Test invalid JSON
        response = api_client.post(
            "/api/v1/ib/symbols/discover",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


def pytest_configure(config):
    """Configure pytest for container E2E tests."""
    config.addinivalue_line(
        "markers", "container_e2e: marks tests as container end-to-end tests"
    )


def pytest_addoption(parser):
    """Add command line options for container E2E tests."""
    parser.addoption(
        "--run-container-e2e",
        action="store_true",
        default=False,
        help="Run container end-to-end tests (requires running container)",
    )
    parser.addoption(
        "--api-base-url",
        action="store",
        default="http://localhost:8000",
        help="Base URL for API testing",
    )


def pytest_collection_modifyitems(config, items):
    """Skip container E2E tests unless explicitly requested."""
    if not config.getoption("--run-container-e2e"):
        skip_container = pytest.mark.skip(
            reason="Container E2E tests not requested (use --run-container-e2e)"
        )
        for item in items:
            if "container_e2e" in item.keywords or "test_container" in item.name:
                item.add_marker(skip_container)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-container-e2e"])
