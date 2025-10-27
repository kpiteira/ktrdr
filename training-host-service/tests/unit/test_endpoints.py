"""
Unit tests for API endpoints.
"""

from unittest.mock import Mock, patch

from fastapi import status


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    def test_basic_health_check_gpu_available(self, client, mock_gpu_available):
        """Test basic health check with GPU available."""
        with patch("psutil.cpu_percent", return_value=25.0):
            with patch("psutil.virtual_memory") as mock_memory:
                mock_memory.return_value.percent = 60.0
                mock_memory.return_value.total = 16 * 1024**3

                response = client.get("/health/")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["healthy"] is True
                assert data["service"] == "training-host"
                assert data["gpu_status"]["available"] is True
                assert data["gpu_status"]["device_count"] == 1

    def test_basic_health_check_gpu_unavailable(self, client, mock_gpu_unavailable):
        """Test basic health check with GPU unavailable."""
        with patch("psutil.cpu_percent", return_value=25.0):
            with patch("psutil.virtual_memory") as mock_memory:
                mock_memory.return_value.percent = 60.0
                mock_memory.return_value.total = 16 * 1024**3

                response = client.get("/health/")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["healthy"] is True
                assert data["gpu_status"]["available"] is False
                assert data["gpu_status"]["device_count"] == 0

    def test_detailed_health_check(self, client, mock_gpu_available):
        """Test detailed health check endpoint."""
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value.percent = 65.0
            mock_memory.return_value.total = 32 * 1024**3

            response = client.get("/health/detailed")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["healthy"] is True
            assert data["gpu_available"] is True
            assert data["gpu_device_count"] == 1
            assert data["system_memory_usage_percent"] == 65.0
            assert "gpu_manager_status" in data


class TestTrainingEndpoints:
    """Test suite for training endpoints."""

    def test_start_training_success(self, client, mock_training_service):
        """Test successful training start."""
        # Use correct field names for the updated model
        training_config = {
            "model_configuration": {"type": "test"},
            "training_configuration": {"epochs": 10},
            "data_configuration": {"symbols": ["TEST"]},
        }

        with patch(
            "endpoints.training.get_service",
            return_value=mock_training_service,
        ):
            response = client.post("/training/start", json=training_config)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["session_id"] == "test-session-123"
            assert data["status"] == "started"
            assert "gpu_allocated" in data

    def test_start_training_with_custom_session_id(self, client, mock_training_service):
        """Test training start with custom session ID."""
        request_data = {
            "session_id": "my-custom-session",
            "model_configuration": {"type": "test"},
            "training_configuration": {"epochs": 10},
            "data_configuration": {"symbols": ["TEST"]},
        }

        with patch(
            "endpoints.training.get_service",
            return_value=mock_training_service,
        ):
            response = client.post("/training/start", json=request_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["session_id"] == "test-session-123"  # Mock returns fixed ID

    def test_start_training_service_error(self, client):
        """Test training start with service error."""
        training_config = {
            "model_configuration": {"type": "test"},
            "training_configuration": {"epochs": 10},
            "data_configuration": {"symbols": ["TEST"]},
        }

        with patch("endpoints.training.get_service") as mock_get_service:
            mock_service = Mock()
            mock_service.create_session.side_effect = Exception("GPU allocation failed")
            mock_get_service.return_value = mock_service

            response = client.post("/training/start", json=training_config)

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "GPU allocation failed" in response.json()["detail"]

    def test_list_training_sessions(self, client, mock_training_service):
        """Test listing training sessions."""
        with patch(
            "endpoints.training.get_service",
            return_value=mock_training_service,
        ):
            response = client.get("/training/sessions")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "total_sessions" in data
            assert "sessions" in data
            assert "timestamp" in data

    def test_evaluate_model_success(self, client, mock_gpu_available):
        """Test successful model evaluation."""
        request_data = {
            "model_path": "/path/to/model.pth",
            "data_config": {"test_data": "config"},
            "metrics": ["accuracy", "loss", "f1_score"],
        }

        response = client.post("/training/evaluate", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "evaluation_id" in data
        assert "results" in data
        assert "gpu_used" in data
        assert "evaluation_time_seconds" in data

    def test_cleanup_session_success(self, client, mock_training_service):
        """Test successful session cleanup."""
        with patch(
            "endpoints.training.get_service",
            return_value=mock_training_service,
        ):
            response = client.delete("/training/sessions/test-session-123")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["session_id"] == "test-session-123"
            assert data["status"] == "cleaned_up"

    def test_cleanup_session_service_error(self, client):
        """Test session cleanup with service error."""
        with patch("endpoints.training.get_service") as mock_get_service:
            mock_service = Mock()
            mock_service.cleanup_session.side_effect = Exception(
                "Cannot cleanup running session"
            )
            mock_get_service.return_value = mock_service

            response = client.delete("/training/sessions/running-session")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Cannot cleanup running session" in response.json()["detail"]


class TestRootEndpoint:
    """Test suite for root endpoint."""

    def test_root_endpoint_gpu_available(self, client, mock_gpu_available):
        """Test root endpoint with GPU available."""
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["service"] == "Training Host Service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        assert data["gpu_available"] is True
        assert data["gpu_device_count"] == 1

    def test_root_endpoint_gpu_unavailable(self, client, mock_gpu_unavailable):
        """Test root endpoint with GPU unavailable."""
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["gpu_available"] is False
        assert data["gpu_device_count"] == 0

    def test_basic_health_endpoint(self, client):
        """Test basic health endpoint."""
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["healthy"] is True
        assert data["service"] == "training-host"
        assert "timestamp" in data
