"""
Unit tests for Backtesting Remote API.

DEPRECATED: This tests the legacy remote_api.py which is being replaced by backtest_worker.py.
Tests are skipped as this module is deprecated.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skip(
    reason="remote_api.py is deprecated, replaced by backtest_worker.py"
)


@pytest.fixture
def mock_operations_service():
    """Create mock OperationsService."""
    mock_service = MagicMock()
    mock_service._cache_ttl = 1.0
    mock_service.get_operation = AsyncMock()
    mock_service.get_operation_metrics = AsyncMock()
    mock_service.cancel_operation = AsyncMock()
    mock_service.list_operations = AsyncMock()
    return mock_service


@pytest.fixture
def mock_backtesting_service():
    """Create mock BacktestingService."""
    mock_service = MagicMock()
    mock_service._use_remote = False  # Remote API always runs in local mode
    mock_service.run_backtest = AsyncMock()
    return mock_service


@pytest.fixture
def test_client(mock_operations_service, mock_backtesting_service):
    """Create FastAPI test client with mocked services."""
    with patch("ktrdr.backtesting.remote_api.get_operations_service") as mock_get_ops:
        with patch(
            "ktrdr.backtesting.remote_api.get_backtest_service"
        ) as mock_get_backtest:
            mock_get_ops.return_value = mock_operations_service
            mock_get_backtest.return_value = mock_backtesting_service

            # Import app after patching
            # Manually set module-level variables for the test
            import ktrdr.backtesting.remote_api as remote_api_module
            from ktrdr.backtesting.remote_api import app

            remote_api_module._operations_service = mock_operations_service
            remote_api_module._backtesting_service = mock_backtesting_service

            with TestClient(app) as client:
                yield client


class TestRemoteAPIInitialization:
    """Test remote API initialization and configuration."""

    def test_app_title_and_description(self):
        """Test FastAPI app has correct title and description."""
        from ktrdr.backtesting.remote_api import app

        assert app.title == "Backtesting Remote Service"
        assert "local mode" in app.description.lower()

    def test_startup_forces_local_mode(self):
        """Test startup event forces USE_REMOTE_BACKTEST_SERVICE=false."""
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "ktrdr.backtesting.remote_api.get_operations_service"
            ) as mock_get_ops:
                with patch(
                    "ktrdr.backtesting.remote_api.get_backtest_service"
                ) as mock_get_backtest:
                    mock_ops = MagicMock()
                    mock_ops._cache_ttl = 1.0
                    mock_get_ops.return_value = mock_ops

                    mock_backtest = MagicMock()
                    mock_backtest._use_remote = False
                    mock_get_backtest.return_value = mock_backtest

                    import asyncio

                    from ktrdr.backtesting.remote_api import startup_event

                    # Run startup
                    asyncio.run(startup_event())

                    # Verify environment was forced to local
                    import os

                    assert os.environ.get("USE_REMOTE_BACKTEST_SERVICE") == "false"


class TestHealthEndpoints:
    """Test health check and info endpoints."""

    def test_root_endpoint_returns_service_info(self, test_client):
        """Test root endpoint returns service information."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Backtesting Remote Service"
        assert data["mode"] == "local"
        assert "timestamp" in data

    def test_health_check_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["service"] == "backtest-remote"


class TestBacktestStartEndpoint:
    """Test /backtests/start endpoint."""

    def test_start_backtest_success(self, test_client, mock_backtesting_service):
        """Test successful backtest start."""
        # Mock service response
        mock_backtesting_service.run_backtest.return_value = {
            "success": True,
            "operation_id": "op_test_123",
            "status": "started",
            "message": "Backtest started",
            "symbol": "AAPL",
            "timeframe": "1h",
        }

        # Make request
        response = test_client.post(
            "/backtests/start",
            json={
                "strategy_name": "test_strategy",
                "symbol": "AAPL",
                "timeframe": "1h",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100000.0,
                "commission": 0.001,
                "slippage": 0.001,
            },
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "op_test_123"
        assert data["status"] == "started"
        assert data["mode"] == "local"  # Remote API always returns local mode

        # Verify service was called
        mock_backtesting_service.run_backtest.assert_called_once()
        call_kwargs = mock_backtesting_service.run_backtest.call_args[1]
        assert call_kwargs["symbol"] == "AAPL"
        assert call_kwargs["timeframe"] == "1h"

    def test_start_backtest_validation_error(
        self, test_client, mock_backtesting_service
    ):
        """Test backtest start with validation error."""
        # Mock service to raise ValueError
        mock_backtesting_service.run_backtest.side_effect = ValueError(
            "Invalid configuration"
        )

        # Make request
        response = test_client.post(
            "/backtests/start",
            json={
                "strategy_name": "test_strategy",
                "symbol": "AAPL",
                "timeframe": "1h",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
        )

        # Verify error response
        assert response.status_code == 400
        assert "Invalid configuration" in response.json()["detail"]

    def test_start_backtest_internal_error(self, test_client, mock_backtesting_service):
        """Test backtest start with internal error."""
        # Mock service to raise general exception
        mock_backtesting_service.run_backtest.side_effect = Exception("Internal error")

        # Make request
        response = test_client.post(
            "/backtests/start",
            json={
                "strategy_name": "test_strategy",
                "symbol": "AAPL",
                "timeframe": "1h",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
        )

        # Verify error response
        assert response.status_code == 500
        assert "Internal" in response.json()["detail"]


class TestOperationsEndpoints:
    """Test operations endpoints (proxy to OperationsService)."""

    def test_get_operation_success(self, test_client, mock_operations_service):
        """Test GET /api/v1/operations/{id} success."""
        # Mock operation data
        mock_operations_service.get_operation.return_value = {
            "operation_id": "op_test_123",
            "status": "RUNNING",
            "progress": {"percentage": 50.0},
        }

        # Make request
        response = test_client.get("/api/v1/operations/op_test_123")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["operation_id"] == "op_test_123"
        assert data["status"] == "RUNNING"

        # Verify service was called
        mock_operations_service.get_operation.assert_called_once_with(
            operation_id="op_test_123",
            force_refresh=False,
        )

    def test_get_operation_with_force_refresh(
        self, test_client, mock_operations_service
    ):
        """Test GET /api/v1/operations/{id} with force_refresh=true."""
        mock_operations_service.get_operation.return_value = {
            "operation_id": "op_test_123",
        }

        # Make request with force_refresh
        response = test_client.get("/api/v1/operations/op_test_123?force_refresh=true")

        assert response.status_code == 200

        # Verify force_refresh was passed
        mock_operations_service.get_operation.assert_called_once_with(
            operation_id="op_test_123",
            force_refresh=True,
        )

    def test_get_operation_not_found(self, test_client, mock_operations_service):
        """Test GET /api/v1/operations/{id} when operation not found."""
        # Mock service to return None
        mock_operations_service.get_operation.return_value = None

        # Make request
        response = test_client.get("/api/v1/operations/nonexistent")

        # Verify 404 response
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_metrics_success(self, test_client, mock_operations_service):
        """Test GET /api/v1/operations/{id}/metrics success."""
        # Mock metrics data
        mock_operations_service.get_operation_metrics.return_value = (
            {"bars": [{"bar_idx": 100}]},
            100,
        )

        # Make request
        response = test_client.get("/api/v1/operations/op_test_123/metrics?cursor=0")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert data["cursor"] == 100

        # Verify service was called
        mock_operations_service.get_operation_metrics.assert_called_once_with(
            operation_id="op_test_123",
            cursor=0,
        )

    def test_get_metrics_not_found(self, test_client, mock_operations_service):
        """Test GET /api/v1/operations/{id}/metrics when operation not found."""
        # Mock service to raise KeyError
        mock_operations_service.get_operation_metrics.side_effect = KeyError(
            "Operation not found"
        )

        # Make request
        response = test_client.get("/api/v1/operations/nonexistent/metrics")

        # Verify 404 response
        assert response.status_code == 404

    def test_cancel_operation_success(self, test_client, mock_operations_service):
        """Test DELETE /api/v1/operations/{id}/cancel success."""
        # Mock cancellation result
        mock_operations_service.cancel_operation.return_value = {
            "operation_id": "op_test_123",
            "status": "cancelled",
        }

        # Make request
        response = test_client.delete("/api/v1/operations/op_test_123/cancel")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["operation_id"] == "op_test_123"

        # Verify service was called
        mock_operations_service.cancel_operation.assert_called_once_with(
            operation_id="op_test_123"
        )

    def test_cancel_operation_not_found(self, test_client, mock_operations_service):
        """Test DELETE /api/v1/operations/{id}/cancel when operation not found."""
        # Mock service to raise KeyError
        mock_operations_service.cancel_operation.side_effect = KeyError(
            "Operation not found"
        )

        # Make request
        response = test_client.delete("/api/v1/operations/nonexistent/cancel")

        # Verify 404 response
        assert response.status_code == 404

    def test_list_operations_success(self, test_client, mock_operations_service):
        """Test GET /api/v1/operations success."""
        # Mock operations list
        mock_operations_service.list_operations.return_value = (
            [{"operation_id": "op_1"}, {"operation_id": "op_2"}],
            2,
            2,
        )

        # Make request
        response = test_client.get("/api/v1/operations")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["operations"]) == 2
        assert data["total"] == 2

    def test_list_operations_with_filters(self, test_client, mock_operations_service):
        """Test GET /api/v1/operations with filters."""
        mock_operations_service.list_operations.return_value = ([], 0, 0)

        # Make request with filters (use lowercase enum value)
        response = test_client.get(
            "/api/v1/operations?operation_type=backtesting&active_only=true&limit=50"
        )

        assert response.status_code == 200

        # Verify filters were passed (FastAPI converts to OperationType enum)
        from ktrdr.api.models.operations import OperationType

        mock_operations_service.list_operations.assert_called_once_with(
            operation_type=OperationType.BACKTESTING,
            active_only=True,
            limit=50,
            offset=0,
        )


class TestCORSConfiguration:
    """Test CORS middleware configuration."""

    def test_cors_allows_all_origins(self):
        """Test that CORS middleware allows all origins (for container communication)."""
        from ktrdr.backtesting.remote_api import app

        # Check middleware is configured
        cors_middleware = None
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware):
                cors_middleware = middleware
                break

        assert cors_middleware is not None, "CORS middleware should be configured"
