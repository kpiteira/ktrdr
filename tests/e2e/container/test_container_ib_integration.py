"""
Container-based IB integration tests.

These tests validate the IB refactoring works correctly in the actual
container deployment environment.
"""

import time

import httpx
import pytest

# Test configuration
API_BASE_URL = "http://localhost:8000/api/v1"
API_TIMEOUT = 30.0


def check_api_available():
    """Check if API is available."""
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def api_client():
    """Create HTTP client for API testing."""
    if not check_api_available():
        pytest.skip("API server not available - requires Docker containers")
    return httpx.Client(base_url=API_BASE_URL, timeout=API_TIMEOUT)


@pytest.mark.container_e2e
class TestContainerIbRefactorValidation:
    """Test IB refactoring integration in container environment."""

    def test_ib_system_status_comprehensive(self, api_client):
        """Test comprehensive IB system status reporting."""
        response = api_client.get("/ib/status")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        ib_status = data["data"]

        # Verify all required status fields
        required_fields = [
            "ib_available",
            "connection",
            "connection_metrics",
            "data_metrics",
        ]
        for field in required_fields:
            assert field in ib_status, f"Missing status field: {field}"

        # Verify connection structure
        connection = ib_status["connection"]
        assert "connected" in connection
        assert "host" in connection
        assert "port" in connection
        assert "client_id" in connection

        # Verify metrics structure
        conn_metrics = ib_status["connection_metrics"]
        assert "total_connections" in conn_metrics
        assert "failed_connections" in conn_metrics

        data_metrics = ib_status["data_metrics"]
        assert "total_requests" in data_metrics
        assert "successful_requests" in data_metrics
        assert "success_rate" in data_metrics

    def test_ib_health_monitoring(self, api_client):
        """Test IB health monitoring system."""
        response = api_client.get("/ib/health")

        # Should return either 200 (healthy) or 503 (unhealthy)
        assert response.status_code in [200, 503]

        data = response.json()
        assert "data" in data

        health_data = data["data"]
        assert "healthy" in health_data
        assert isinstance(health_data["healthy"], bool)

        # If unhealthy, should provide error information
        if not health_data["healthy"]:
            assert "error_message" in health_data

    def test_ib_configuration_management(self, api_client):
        """Test IB configuration retrieval."""
        response = api_client.get("/ib/config")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        config_data = data["data"]

        # Verify configuration fields
        required_config_fields = ["host", "port", "client_id_range", "timeout"]
        for field in required_config_fields:
            assert field in config_data, f"Missing config field: {field}"

        # Verify field types
        assert isinstance(config_data["port"], int)
        assert isinstance(config_data["timeout"], (int, float))

    def test_ib_connection_cleanup(self, api_client):
        """Test IB connection cleanup endpoint."""
        response = api_client.post("/ib/cleanup")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        cleanup_result = data["data"]
        assert "connections_closed" in cleanup_result
        assert isinstance(cleanup_result["connections_closed"], int)

    def test_ib_symbol_discovery_integration(self, api_client):
        """Test symbol discovery integration."""
        # Test with a well-known symbol
        symbol_request = {"symbol": "AAPL", "force_refresh": False}

        response = api_client.post("/ib/symbols/discover", json=symbol_request)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        discovery_result = data["data"]
        assert "symbol_info" in discovery_result
        assert "cached" in discovery_result
        assert "discovery_time_ms" in discovery_result

        # Verify timing is reasonable
        assert isinstance(discovery_result["discovery_time_ms"], (int, float))
        assert discovery_result["discovery_time_ms"] >= 0

    def test_ib_discovered_symbols_list(self, api_client):
        """Test getting list of discovered symbols."""
        response = api_client.get("/ib/symbols/discovered")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        symbols_data = data["data"]
        assert "symbols" in symbols_data
        assert "total_count" in symbols_data
        assert "instrument_types" in symbols_data
        assert "cache_stats" in symbols_data

        # Verify data types
        assert isinstance(symbols_data["symbols"], list)
        assert isinstance(symbols_data["total_count"], int)
        assert isinstance(symbols_data["instrument_types"], dict)

    def test_data_manager_integration_via_api(self, api_client):
        """Test DataManager integration through data endpoints."""
        # Test local data loading (should work without IB)
        response = api_client.get("/data/AAPL/1h")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        ohlcv_data = data["data"]
        assert "dates" in ohlcv_data
        assert "ohlcv" in ohlcv_data
        assert "metadata" in ohlcv_data

        # Verify metadata structure
        metadata = ohlcv_data["metadata"]
        assert "symbol" in metadata
        assert "timeframe" in metadata
        assert metadata["symbol"] == "AAPL"
        assert metadata["timeframe"] == "1h"

    def test_system_integration_endpoints(self, api_client):
        """Test system-level integration endpoints."""
        # Test system status
        response = api_client.get("/system/status")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        status_data = data["data"]
        assert "version" in status_data
        assert "services" in status_data

        # Verify IB-related services are reported
        services = status_data["services"]
        assert "ib_connection" in services
        assert "gap_filler" in services

    def test_data_info_integration(self, api_client):
        """Test data info endpoint integration."""
        response = api_client.get("/data/info")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        data_info = data["data"]
        assert "available_symbols" in data_info
        assert "data_directory" in data_info
        assert "data_sources" in data_info

        # Should include IB as a data source
        data_sources = data_info["data_sources"]
        assert "ib_gateway" in data_sources

    def test_error_handling_resilience(self, api_client):
        """Test that system handles errors gracefully."""
        # Test with invalid symbol discovery
        invalid_request = {"symbol": "INVALID_SYMBOL_12345", "force_refresh": True}

        response = api_client.post("/ib/symbols/discover", json=invalid_request)

        # Should not crash, should handle gracefully
        assert response.status_code == 200

        data = response.json()
        # Should succeed but might return null symbol_info
        assert data["success"] is True or "error" in data

    def test_performance_monitoring(self, api_client):
        """Test performance characteristics of IB endpoints."""
        endpoints_to_test = [
            "/ib/status",
            "/ib/health",
            "/ib/config",
            "/system/status",
        ]

        for endpoint in endpoints_to_test:
            start_time = time.time()
            response = api_client.get(endpoint)
            elapsed = time.time() - start_time

            assert response.status_code in [200, 503]  # 503 acceptable for health check
            assert elapsed < 10.0, f"Endpoint {endpoint} too slow: {elapsed:.2f}s"

    def test_concurrent_ib_operations(self, api_client):
        """Test concurrent IB operations don't interfere."""
        import queue
        import threading

        results = queue.Queue()

        def test_ib_status():
            try:
                response = api_client.get("/ib/status")
                results.put(("status", response.status_code))
            except Exception as e:
                results.put(("status", str(e)))

        def test_ib_config():
            try:
                response = api_client.get("/ib/config")
                results.put(("config", response.status_code))
            except Exception as e:
                results.put(("config", str(e)))

        # Start concurrent requests
        threads = [
            threading.Thread(target=test_ib_status),
            threading.Thread(target=test_ib_config),
            threading.Thread(target=test_ib_status),  # Duplicate to test concurrency
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Collect results
        collected_results = []
        while not results.empty():
            collected_results.append(results.get())

        # All should succeed
        assert len(collected_results) == 3
        for _endpoint, status_code in collected_results:
            assert status_code == 200


def pytest_configure(config):
    """Configure pytest for container IB integration tests."""
    config.addinivalue_line(
        "markers", "container_ib: marks tests as container IB integration tests"
    )


def pytest_addoption(parser):
    """Add command line options for container IB integration tests."""
    parser.addoption(
        "--run-container-ib",
        action="store_true",
        default=False,
        help="Run container IB integration tests (requires running container)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip container IB integration tests unless explicitly requested."""
    if not config.getoption("--run-container-ib"):
        skip_container = pytest.mark.skip(
            reason="Container IB integration tests not requested (use --run-container-ib)"
        )
        for item in items:
            if "container_ib" in item.keywords or "test_container_ib" in item.name:
                item.add_marker(skip_container)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-container-ib"])
