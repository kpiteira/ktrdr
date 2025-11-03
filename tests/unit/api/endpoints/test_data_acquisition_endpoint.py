"""
Tests for Data Acquisition API endpoint.

Tests the new POST /data/acquire/download endpoint that uses DataAcquisitionService.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ktrdr.api.endpoints.data import get_acquisition_service, router
from ktrdr.data.acquisition.acquisition_service import DataAcquisitionService


@pytest.fixture
def app():
    """Create FastAPI test app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_acquisition_service():
    """Mock DataAcquisitionService."""
    service = MagicMock(spec=DataAcquisitionService)
    service.download_data = AsyncMock()
    return service


class TestDataAcquireDownloadEndpoint:
    """Tests for POST /data/acquire/download endpoint."""

    def test_download_endpoint_exists(self, client):
        """Test that the POST /data/acquire/download endpoint exists."""
        # This should fail initially - endpoint doesn't exist yet
        response = client.post(
            "/data/acquire/download",
            json={
                "symbol": "AAPL",
                "timeframe": "1d",
                "mode": "tail",
            },
        )
        # Should not be 404
        assert (
            response.status_code != 404
        ), "Endpoint /data/acquire/download should exist"

    def test_download_with_valid_request(self, app, mock_acquisition_service):
        """Test download with valid request returns operation info."""
        # Mock the download_data response
        mock_acquisition_service.download_data.return_value = {
            "operation_id": "op_test_123",
            "status": "started",
            "message": "Download started",
        }

        # Override the dependency
        app.dependency_overrides[get_acquisition_service] = (
            lambda: mock_acquisition_service
        )

        # Create client AFTER overriding dependencies
        client = TestClient(app)
        response = client.post(
            "/data/acquire/download",
            json={
                "symbol": "AAPL",
                "timeframe": "1d",
                "mode": "tail",
            },
        )

        # Clear override
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "operation_id" in data
        assert data["operation_id"] == "op_test_123"
        assert data["status"] == "started"

    def test_download_with_backfill_mode(self, app, mock_acquisition_service):
        """Test download with backfill mode."""
        mock_acquisition_service.download_data.return_value = {
            "operation_id": "op_backfill_456",
            "status": "started",
            "message": "Backfill started",
        }

        # Override the dependency
        app.dependency_overrides[get_acquisition_service] = (
            lambda: mock_acquisition_service
        )

        client = TestClient(app)
        response = client.post(
            "/data/acquire/download",
            json={
                "symbol": "EURUSD",
                "timeframe": "1h",
                "mode": "backfill",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
        )

        # Clear override
        app.dependency_overrides.clear()

        assert response.status_code == 200
        # Verify service was called with correct parameters
        mock_acquisition_service.download_data.assert_called_once_with(
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-12-31",
            mode="backfill",
        )

    def test_download_with_full_mode(self, app, mock_acquisition_service):
        """Test download with full mode."""
        mock_acquisition_service.download_data.return_value = {
            "operation_id": "op_full_789",
            "status": "started",
            "message": "Full download started",
        }

        # Override the dependency
        app.dependency_overrides[get_acquisition_service] = (
            lambda: mock_acquisition_service
        )

        client = TestClient(app)
        response = client.post(
            "/data/acquire/download",
            json={
                "symbol": "MSFT",
                "timeframe": "1d",
                "mode": "full",
                "start_date": "2023-01-01",
            },
        )

        # Clear override
        app.dependency_overrides.clear()

        assert response.status_code == 200
        mock_acquisition_service.download_data.assert_called_once()

    def test_download_missing_symbol(self, client):
        """Test download with missing symbol returns error."""
        response = client.post(
            "/data/acquire/download",
            json={
                "timeframe": "1d",
                "mode": "tail",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_download_missing_timeframe(self, client):
        """Test download with missing timeframe returns error."""
        response = client.post(
            "/data/acquire/download",
            json={
                "symbol": "AAPL",
                "mode": "tail",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_download_invalid_mode(self, client):
        """Test download with invalid mode returns error."""
        # Invalid mode should either be rejected by request validation
        # or by the service
        response = client.post(
            "/data/acquire/download",
            json={
                "symbol": "AAPL",
                "timeframe": "1d",
                "mode": "invalid_mode",
            },
        )
        # Should return error (either 400 or 422)
        assert response.status_code in [400, 422]

    def test_download_service_error_handling(self, app, mock_acquisition_service):
        """Test that service errors are properly handled."""
        # Mock service raising an error
        mock_acquisition_service.download_data.side_effect = Exception("Service error")

        # Override the dependency
        app.dependency_overrides[get_acquisition_service] = (
            lambda: mock_acquisition_service
        )

        client = TestClient(app)
        response = client.post(
            "/data/acquire/download",
            json={
                "symbol": "AAPL",
                "timeframe": "1d",
                "mode": "tail",
            },
        )

        # Clear override
        app.dependency_overrides.clear()

        # Should return error status code
        assert response.status_code >= 400

    def test_download_with_date_range(self, app, mock_acquisition_service):
        """Test download with custom date range."""
        mock_acquisition_service.download_data.return_value = {
            "operation_id": "op_range_999",
            "status": "started",
            "message": "Download with date range started",
        }

        # Override the dependency
        app.dependency_overrides[get_acquisition_service] = (
            lambda: mock_acquisition_service
        )

        client = TestClient(app)
        response = client.post(
            "/data/acquire/download",
            json={
                "symbol": "AAPL",
                "timeframe": "1h",
                "mode": "full",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-12-31T23:59:59Z",
            },
        )

        # Clear override
        app.dependency_overrides.clear()

        assert response.status_code == 200
        # Verify dates were passed correctly
        mock_acquisition_service.download_data.assert_called_once()
        call_kwargs = mock_acquisition_service.download_data.call_args.kwargs
        assert "start_date" in call_kwargs
        assert "end_date" in call_kwargs


class TestGetAcquisitionServiceDependency:
    """Tests for get_acquisition_service dependency injection."""

    def test_get_acquisition_service_returns_instance(self):
        """Test that get_acquisition_service returns DataAcquisitionService instance."""
        from ktrdr.api.dependencies import get_acquisition_service

        service = get_acquisition_service()
        assert isinstance(service, DataAcquisitionService)

    def test_get_acquisition_service_singleton_behavior(self):
        """Test that get_acquisition_service returns singleton instance."""
        from ktrdr.api.dependencies import get_acquisition_service

        service1 = get_acquisition_service()
        service2 = get_acquisition_service()

        # Should return same instance (singleton)
        assert service1 is service2
