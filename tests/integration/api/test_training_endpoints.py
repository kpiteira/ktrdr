"""
Integration tests for Training API endpoints.

Tests the training endpoints that start training operations and retrieve results
with properly mocked external dependencies.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_training_service():
    """Create a mock TrainingService for testing endpoints."""
    service_mock = AsyncMock()

    # Mock successful start_training response
    service_mock.start_training.return_value = {
        "success": True,
        "task_id": "op_training_12345",
        "status": "training_started",
        "message": "Training started successfully",
        "symbols": ["AAPL"],
        "timeframes": ["1h"],
        "strategy_name": "rsi_mean_reversion",
        "estimated_duration_minutes": 30,
    }

    # Mock successful get_model_performance response
    service_mock.get_model_performance.return_value = {
        "success": True,
        "training_metrics": {
            "accuracy": 0.85,
            "loss": 0.15,
            "val_accuracy": 0.82,
            "val_loss": 0.18,
        },
        "test_metrics": {
            "accuracy": 0.80,
            "precision": 0.83,
            "recall": 0.78,
            "f1_score": 0.80,
        },
        "model_info": {
            "model_type": "mlp",
            "total_parameters": 1024,
            "training_time_seconds": 1800,
        },
    }

    return service_mock


@pytest.fixture
def client_with_mocked_training(client, mock_training_service):
    """Create a test client with mocked training service dependency."""
    from ktrdr.api.endpoints.training import get_training_service

    # Override the training service dependency
    client.app.dependency_overrides[get_training_service] = (
        lambda: mock_training_service
    )

    yield client

    # Clean up after test
    client.app.dependency_overrides.clear()


class TestTrainingEndpoints:
    """Test training API endpoints."""

    @pytest.mark.api
    def test_start_training_success(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test starting a training operation successfully."""

        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
        }

        response = client_with_mocked_training.post(
            "/api/v1/trainings/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_id"] == "op_training_12345"
        assert data["status"] == "training_started"
        assert data["symbols"] == ["AAPL"]
        assert data["timeframes"] == ["1h"]
        assert data["estimated_duration_minutes"] == 30

        # Verify the response structure matches expected format
        assert data["message"] == "Training started successfully"
        assert data["strategy_name"] == "rsi_mean_reversion"

        # Verify the service was called with correct parameters
        mock_training_service.start_training.assert_called_once_with(
            symbols=["AAPL"],
            timeframes=["1h"],
            strategy_name="rsi_mean_reversion",
            start_date="2024-01-01",
            end_date="2024-06-01",
            task_id=None,
            detailed_analytics=False,
        )

    @pytest.mark.api
    @patch("ktrdr.api.endpoints.training.get_training_service")
    def test_start_training_with_optional_params(
        self, mock_get_service, client, mock_training_service
    ):
        """Test starting training with optional parameters."""
        mock_get_service.return_value = mock_training_service
        # Update mock response for this test
        mock_training_service.start_training.return_value["symbols"] = ["MSFT"]
        mock_training_service.start_training.return_value["timeframes"] = ["1d"]

        payload = {
            "symbols": ["MSFT"],
            "timeframes": ["1d"],
            "strategy_name": "rsi_mean_reversion",
            "task_id": "custom_task_id",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_id"] == "op_training_12345"
        assert data["status"] == "training_started"
        assert data["symbols"] == ["MSFT"]
        assert data["timeframes"] == ["1d"]

        # Verify service call
        mock_training_service.start_training.assert_called_once_with(
            symbols=["MSFT"],
            timeframes=["1d"],
            strategy_name="rsi_mean_reversion",
            start_date=None,
            end_date=None,
            task_id="custom_task_id",
            detailed_analytics=False,
        )

    @pytest.mark.api
    def test_start_training_validation_error(self, client, mock_training_service):
        """Test starting training with invalid parameters."""
        # No need to patch for validation errors - they're caught by Pydantic before service call
        payload = {
            "symbol": "",  # Invalid field name - should be "symbols"
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        assert response.status_code == 422  # Validation error

    @pytest.mark.api
    @patch("ktrdr.api.endpoints.training.get_training_service")
    def test_start_training_service_error(
        self, mock_get_service, client, mock_training_service
    ):
        """Test handling service errors during training start."""
        # Configure service to raise an exception
        from ktrdr.errors import DataError

        mock_training_service.start_training.side_effect = DataError(
            "Insufficient training data"
        )
        mock_get_service.return_value = mock_training_service

        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        # Should return 500 error when service fails
        assert response.status_code == 500
        assert "Insufficient training data" in response.json()["detail"]

    @pytest.mark.api
    @patch("ktrdr.api.endpoints.training.get_training_service")
    def test_get_model_performance_success(
        self, mock_get_service, client, mock_training_service
    ):
        """Test getting model performance for completed training."""
        mock_get_service.return_value = mock_training_service

        response = client.get("/api/v1/trainings/completed_training_789/performance")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "training_metrics" in data
        assert "test_metrics" in data
        assert "model_info" in data

        # Verify service was called
        mock_training_service.get_model_performance.assert_called_once_with(
            "completed_training_789"
        )

    @pytest.mark.api
    @patch("ktrdr.api.endpoints.training.get_training_service")
    def test_get_model_performance_not_completed(
        self, mock_get_service, client, mock_training_service
    ):
        """Test getting performance for non-completed training."""
        from ktrdr.errors import DataError

        mock_training_service.get_model_performance.side_effect = DataError(
            "Training not completed"
        )
        mock_get_service.return_value = mock_training_service

        response = client.get("/api/v1/trainings/running_training/performance")

        assert response.status_code == 500
        assert "Training not completed" in response.json()["detail"]

    @pytest.mark.api
    def test_training_config_validation(self, client, mock_training_service):
        """Test training configuration validation."""
        # Test with missing required fields
        payload = {
            "symbol": "",  # Empty symbol should be invalid
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        # Should be caught by Pydantic validation
        assert response.status_code == 422

    @pytest.mark.api
    @patch("ktrdr.api.endpoints.training.get_training_service")
    def test_training_config_defaults(
        self, mock_get_service, client, mock_training_service
    ):
        """Test that training configuration uses proper defaults."""
        mock_get_service.return_value = mock_training_service

        # Minimal payload - should use defaults for most config
        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["strategy_name"] == "rsi_mean_reversion"
        assert data["timeframes"] == ["1h"]

    @pytest.mark.api
    @patch("ktrdr.api.endpoints.training.get_training_service")
    def test_training_large_config(
        self, mock_get_service, client, mock_training_service
    ):
        """Test training with large/complex configuration."""
        mock_get_service.return_value = mock_training_service

        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1m"],
            "strategy_name": "rsi_mean_reversion",
            "start_date": "2020-01-01",  # Long training period
            "end_date": "2024-01-01",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.api
    def test_training_endpoints_error_handling(self, client, mock_training_service):
        """Test general error handling in training endpoints."""
        # Test non-existent training ID
        response = client.get("/api/v1/trainings/error_training")

        assert response.status_code == 404

    @pytest.mark.api
    def test_training_status_completed(self, client, mock_training_service):
        """Test getting status for completed training."""
        response = client.get("/api/v1/trainings/completed_training")

        # With real service, non-existent training returns 404
        assert response.status_code == 404

    @pytest.mark.api
    @patch("ktrdr.api.endpoints.training.get_training_service")
    def test_training_with_custom_task_id(
        self, mock_get_service, client, mock_training_service
    ):
        """Test starting training with custom task ID."""
        mock_get_service.return_value = mock_training_service

        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
            "task_id": "my_custom_training_id",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_id"] == "op_training_12345"

    @pytest.mark.api
    @patch("ktrdr.api.endpoints.training.get_training_service")
    def test_training_with_multiple_timeframes(
        self, mock_get_service, client, mock_training_service
    ):
        """Test training with multiple timeframes."""
        mock_get_service.return_value = mock_training_service
        # Update mock response for multiple timeframes
        mock_training_service.start_training.return_value["timeframes"] = ["1h", "1d"]

        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h", "1d"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["timeframes"] == ["1h", "1d"]
        assert data["strategy_name"] == "rsi_mean_reversion"

    @pytest.mark.api
    def test_training_with_empty_timeframes(self, client, mock_training_service):
        """Test training with empty timeframes list."""
        payload = {
            "symbols": ["AAPL"],
            "timeframes": [],  # Empty list should be invalid
            "strategy_name": "rsi_mean_reversion",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        assert response.status_code == 422  # Validation error
