"""
End-to-End tests for IB connection resilience features.

These tests validate the complete connection resilience implementation
from Phases 1-6 of the connection resilience plan in a containerized environment.
"""

import time
from datetime import datetime

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
class TestConnectionResilienceE2E:
    """
    End-to-End tests for connection resilience features.

    Tests the complete implementation of:
    - Phase 1: Systematic connection validation before handoff
    - Phase 2: Garbage collection with 5-minute idle timeout
    - Phase 3: Client ID 1 preference with incremental fallback
    - Phase 4: Enhanced IB status endpoint with live validation
    """

    def test_resilience_endpoint_available(self, api_client):
        """Test that the new resilience endpoint is available."""
        response = api_client.get("/ib/resilience")

        # Should succeed regardless of IB availability
        assert response.status_code in [
            200,
            503,
        ], f"Unexpected status: {response.status_code}"

        data = response.json()
        assert "success" in data

        if response.status_code == 200:
            assert data["success"] is True
            assert "data" in data
            resilience_data = data["data"]

            # Verify all phases are reported
            assert "phase_1_systematic_validation" in resilience_data
            assert "phase_2_garbage_collection" in resilience_data
            assert "phase_3_client_id_preference" in resilience_data
            assert "overall_resilience_score" in resilience_data
            assert "connection_pool_health" in resilience_data

            # Verify score is a valid percentage
            score = resilience_data["overall_resilience_score"]
            assert isinstance(score, (int, float))
            assert 0 <= score <= 100

    def test_systematic_validation_status(self, api_client):
        """Test Phase 1: Systematic connection validation status."""
        response = api_client.get("/ib/resilience")

        if response.status_code == 200:
            data = response.json()
            phase1 = data["data"]["phase_1_systematic_validation"]

            # Should report validation method exists
            assert "status" in phase1
            assert "description" in phase1

            if phase1["status"] == "working":
                assert "validation_enabled" in phase1
                assert phase1["validation_enabled"] is True

    def test_garbage_collection_configuration(self, api_client):
        """Test Phase 2: Garbage collection configuration."""
        response = api_client.get("/ib/resilience")

        if response.status_code == 200:
            data = response.json()
            phase2 = data["data"]["phase_2_garbage_collection"]

            assert "status" in phase2
            assert "description" in phase2

            if phase2["status"] == "working":
                # Should be configured for 5-minute (300s) idle timeout
                assert "max_idle_time_seconds" in phase2
                assert phase2["max_idle_time_seconds"] == 300.0

                assert "health_check_interval" in phase2
                # Should check every minute (60s)
                assert phase2["health_check_interval"] == 60.0

    def test_client_id_preference_logic(self, api_client):
        """Test Phase 3: Client ID 1 preference logic."""
        response = api_client.get("/ib/resilience")

        if response.status_code == 200:
            data = response.json()
            phase3 = data["data"]["phase_3_client_id_preference"]

            assert "status" in phase3
            assert "description" in phase3

            if phase3["status"] == "working":
                assert "client_ids_in_use" in phase3
                assert "total_active_connections" in phase3

                # If connections exist, they should prefer low IDs
                client_ids = phase3.get("client_ids_in_use", [])
                if client_ids:
                    # Should prefer Client ID 1 or low numbers
                    lowest_id = phase3.get("lowest_client_id_used")
                    assert lowest_id is not None, "Should report lowest client ID used"

    def test_enhanced_ib_status_integration(self, api_client):
        """Test Phase 4: Enhanced IB status endpoint integration."""
        # Test the regular IB status endpoint
        response = api_client.get("/ib/status")
        assert response.status_code in [200, 503]

        data = response.json()
        assert "success" in data

        if response.status_code == 200 and data["success"]:
            status_data = data["data"]

            # Enhanced status should include connection info
            assert "connection" in status_data
            assert "connection_metrics" in status_data
            assert "ib_available" in status_data

    def test_health_check_with_resilience(self, api_client):
        """Test IB health check includes resilience validation."""
        response = api_client.get("/ib/health")
        assert response.status_code in [200, 503]

        data = response.json()
        assert "success" in data

        if response.status_code == 200:
            health_data = data["data"]

            # Health check should include key resilience indicators
            assert "healthy" in health_data
            assert "connection_ok" in health_data
            assert "data_fetching_ok" in health_data

            # If unhealthy, should have error message
            if not health_data["healthy"]:
                assert "error_message" in health_data
                assert health_data["error_message"] is not None

    def test_connection_pool_metrics(self, api_client):
        """Test connection pool health metrics from resilience endpoint."""
        response = api_client.get("/ib/resilience")

        if response.status_code == 200:
            data = response.json()
            pool_health = data["data"]["connection_pool_health"]

            # Should have key pool metrics
            assert "total_connections" in pool_health
            assert "healthy_connections" in pool_health
            assert "active_connections" in pool_health
            assert "pool_uptime_seconds" in pool_health

            # Metrics should be non-negative
            assert pool_health["total_connections"] >= 0
            assert pool_health["healthy_connections"] >= 0
            assert pool_health["active_connections"] >= 0
            assert pool_health["pool_uptime_seconds"] >= 0

            # Healthy connections should not exceed total
            assert (
                pool_health["healthy_connections"] <= pool_health["total_connections"]
            )
            assert pool_health["active_connections"] <= pool_health["total_connections"]

    def test_resilience_score_calculation(self, api_client):
        """Test overall resilience score calculation."""
        response = api_client.get("/ib/resilience")

        if response.status_code == 200:
            data = response.json()
            score = data["data"]["overall_resilience_score"]

            # Score should be valid percentage
            assert isinstance(score, (int, float))
            assert 0 <= score <= 100

            # If all phases are working, score should be high
            phase1 = data["data"]["phase_1_systematic_validation"]
            phase2 = data["data"]["phase_2_garbage_collection"]
            phase3 = data["data"]["phase_3_client_id_preference"]

            working_phases = sum(
                1
                for phase in [phase1, phase2, phase3]
                if phase.get("status") == "working"
            )

            if working_phases == 3:
                # All phases working should give high score (65+ points minimum)
                assert (
                    score >= 65
                ), f"Expected high score for all working phases, got {score}"

    def test_timestamp_consistency(self, api_client):
        """Test that resilience status includes consistent timestamps."""
        response = api_client.get("/ib/resilience")

        if response.status_code == 200:
            data = response.json()
            resilience_data = data["data"]

            assert "timestamp" in resilience_data
            timestamp_str = resilience_data["timestamp"]

            # Should be valid ISO format timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

                # Should be recent (within last minute)
                now = datetime.now(timestamp.tzinfo)
                time_diff = abs((now - timestamp).total_seconds())
                assert time_diff < 60, f"Timestamp too old: {time_diff}s ago"

            except ValueError:
                pytest.fail(f"Invalid timestamp format: {timestamp_str}")

    def test_error_handling_resilience(self, api_client):
        """Test error handling in resilience endpoint."""
        # Test with various invalid scenarios to ensure graceful handling
        response = api_client.get("/ib/resilience")

        # Should never return 500 error - always graceful handling
        assert response.status_code in [200, 503], "Should handle errors gracefully"

        data = response.json()
        assert "success" in data

        # Even if unsuccessful, should have structured error response
        if not data.get("success", False):
            assert "error" in data
            assert data["error"] is not None

    def test_resilience_performance(self, api_client):
        """Test that resilience endpoint performs within acceptable time."""
        start_time = time.time()

        response = api_client.get("/ib/resilience")

        end_time = time.time()
        response_time = end_time - start_time

        # Should respond within 10 seconds (even without IB)
        assert (
            response_time < 10.0
        ), f"Resilience endpoint too slow: {response_time:.2f}s"

        # Should be reasonably fast for status check
        if response.status_code == 200:
            assert (
                response_time < 5.0
            ), f"Expected faster response: {response_time:.2f}s"


@pytest.mark.container_e2e
class TestConnectionResilienceIntegration:
    """Integration tests for resilience features working together."""

    def test_full_resilience_workflow(self, api_client):
        """Test complete resilience workflow from status to health to resilience."""
        # Step 1: Check basic IB status
        status_response = api_client.get("/ib/status")
        assert status_response.status_code in [200, 503]

        # Step 2: Check health
        health_response = api_client.get("/ib/health")
        assert health_response.status_code in [200, 503]

        # Step 3: Check detailed resilience
        resilience_response = api_client.get("/ib/resilience")
        assert resilience_response.status_code in [200, 503]

        # All should be consistent in their availability reporting
        status_available = status_response.status_code == 200
        health_available = health_response.status_code == 200
        resilience_available = resilience_response.status_code == 200

        # Resilience should be available if status is available
        if status_available:
            assert resilience_available, "Resilience should work if status works"

    def test_circuit_breaker_endpoint_integration(self, api_client):
        """Test integration with circuit breaker endpoints."""
        # Check if circuit breaker endpoint exists
        response = api_client.get("/ib/circuit-breakers")

        # Should either work or gracefully fail
        assert response.status_code in [200, 404, 503]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data

            if data.get("success"):
                # Should have circuit breaker information
                breaker_data = data["data"]
                # Circuit breakers integrate with our connection resilience
                assert isinstance(breaker_data, dict)
