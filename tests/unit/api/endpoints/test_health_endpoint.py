"""Unit tests for health endpoint with orphan detector integration.

Tests that the /health endpoint returns orphan detector status when available.
This is part of M2 Task 2.3 (Add Health Check to Orphan Detector).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpointWithOrphanDetector:
    """Test health endpoint includes orphan detector status."""

    @pytest.fixture
    def mock_orphan_detector(self):
        """Create a mock OrphanOperationDetector."""
        detector = MagicMock()
        detector.get_status.return_value = {
            "running": True,
            "potential_orphans_count": 2,
            "last_check": "2024-12-21T10:30:00+00:00",
            "orphan_timeout_seconds": 60,
            "check_interval_seconds": 15,
        }
        return detector

    @pytest.fixture
    def client(self):
        """Create a test client with mocked lifespan."""
        from ktrdr.api.main import create_application

        app = create_application()
        return TestClient(app)

    def test_health_endpoint_includes_orphan_detector_status(
        self, client, mock_orphan_detector
    ):
        """Health endpoint should include orphan_detector field with status."""
        # Patch the helper function that gets status
        with patch(
            "ktrdr.api.endpoints._get_orphan_detector_status",
            return_value=mock_orphan_detector.get_status(),
        ):
            response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        # Should still have basic health fields
        assert "status" in data
        assert data["status"] == "ok"
        assert "version" in data

        # Should include orphan_detector status
        assert "orphan_detector" in data
        orphan_status = data["orphan_detector"]
        assert orphan_status["running"] is True
        assert orphan_status["potential_orphans_count"] == 2
        assert orphan_status["last_check"] == "2024-12-21T10:30:00+00:00"
        assert orphan_status["orphan_timeout_seconds"] == 60
        assert orphan_status["check_interval_seconds"] == 15

    def test_health_endpoint_orphan_detector_not_running(self, client):
        """Health endpoint should reflect detector not running status."""
        not_running_status = {
            "running": False,
            "potential_orphans_count": 0,
            "last_check": None,
            "orphan_timeout_seconds": 60,
            "check_interval_seconds": 15,
        }

        with patch(
            "ktrdr.api.endpoints._get_orphan_detector_status",
            return_value=not_running_status,
        ):
            response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        orphan_status = data["orphan_detector"]
        assert orphan_status["running"] is False
        assert orphan_status["last_check"] is None

    def test_health_endpoint_orphan_detector_not_initialized(self, client):
        """Health endpoint should handle when detector is not yet initialized."""
        # The helper returns None when detector is not initialized
        with patch(
            "ktrdr.api.endpoints._get_orphan_detector_status",
            return_value=None,
        ):
            response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        # Should still return ok status
        assert data["status"] == "ok"

        # Should indicate detector is not available (None)
        assert "orphan_detector" in data
        assert data["orphan_detector"] is None

    def test_health_endpoint_response_format_matches_smoke_test(
        self, client, mock_orphan_detector
    ):
        """Response format should match expected smoke test output.

        Smoke test: curl http://localhost:8000/api/v1/health | jq '.orphan_detector'
        """
        with patch(
            "ktrdr.api.endpoints._get_orphan_detector_status",
            return_value=mock_orphan_detector.get_status(),
        ):
            response = client.get("/api/v1/health")

        data = response.json()

        # Verify jq '.orphan_detector' would return a valid object
        orphan_detector = data.get("orphan_detector")
        assert orphan_detector is not None
        assert isinstance(orphan_detector, dict)

        # Verify expected keys are present
        expected_keys = {"running", "potential_orphans_count", "last_check"}
        assert expected_keys.issubset(set(orphan_detector.keys()))
