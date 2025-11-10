"""
Tests for GPU worker registration in training-host-service.

These tests verify that training-host-service correctly registers
with WorkerRegistry and reports GPU capabilities.

Task 5.6: Migrate training-host-service to WorkerAPIBase
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add training-host-service to path for imports
training_host_service_dir = (
    Path(__file__).parent.parent.parent.parent / "training-host-service"
)
sys.path.insert(0, str(training_host_service_dir))


class TestGPUWorkerRegistration:
    """Test GPU worker registration functionality."""

    @pytest.mark.asyncio
    async def test_worker_registers_with_gpu_true_cuda(self):
        """Worker registers with gpu:true capability when CUDA available."""
        from main import TrainingHostWorker

        # Use capabilities parameter to override GPU detection
        cuda_capabilities = {
            "gpu": True,
            "gpu_type": "CUDA",
            "gpu_count": 2,
        }

        worker = TrainingHostWorker(
            worker_port=5002,
            backend_url="http://test-backend:8000",
            capabilities=cuda_capabilities,
        )

        assert worker.capabilities["gpu"] is True
        assert worker.capabilities["gpu_type"] == "CUDA"
        assert worker.capabilities["gpu_count"] == 2

    @pytest.mark.asyncio
    async def test_worker_registers_with_gpu_true_mps(self):
        """Worker registers with gpu:true capability when MPS (Apple Silicon) available."""
        from main import TrainingHostWorker

        # Use capabilities parameter for MPS
        mps_capabilities = {
            "gpu": True,
            "gpu_type": "MPS",
            "gpu_count": 1,
        }

        worker = TrainingHostWorker(
            worker_port=5002,
            backend_url="http://test-backend:8000",
            capabilities=mps_capabilities,
        )

        assert worker.capabilities["gpu"] is True
        assert worker.capabilities["gpu_type"] == "MPS"
        assert worker.capabilities["gpu_count"] == 1

    @pytest.mark.asyncio
    async def test_worker_registers_with_gpu_false(self):
        """Worker registers with gpu:false when no GPU available."""
        from main import TrainingHostWorker

        # Use capabilities parameter for no GPU
        no_gpu_capabilities = {"gpu": False}

        worker = TrainingHostWorker(
            worker_port=5002,
            backend_url="http://test-backend:8000",
            capabilities=no_gpu_capabilities,
        )

        assert worker.capabilities["gpu"] is False
        assert "gpu_type" not in worker.capabilities
        assert "gpu_count" not in worker.capabilities

    @pytest.mark.asyncio
    async def test_worker_inherits_from_worker_api_base(self):
        """TrainingHostWorker inherits from WorkerAPIBase."""
        from main import TrainingHostWorker

        from ktrdr.workers.base import WorkerAPIBase

        worker = TrainingHostWorker(
            worker_port=5002,
            backend_url="http://test-backend:8000",
            capabilities={"gpu": False},  # Simplify for test
        )

        assert isinstance(worker, WorkerAPIBase)

    @pytest.mark.asyncio
    async def test_worker_has_operations_service_endpoints(self):
        """Worker exposes operations service endpoints via WorkerAPIBase."""
        from main import TrainingHostWorker

        worker = TrainingHostWorker(
            worker_port=5002,
            backend_url="http://test-backend:8000",
            capabilities={"gpu": False},
        )

        # Verify operations endpoints are registered
        routes = [route.path for route in worker.app.routes]

        assert "/api/v1/operations/{operation_id}" in routes
        assert "/api/v1/operations/{operation_id}/metrics" in routes
        assert "/api/v1/operations" in routes
        assert "/api/v1/operations/{operation_id}/cancel" in routes

    @pytest.mark.asyncio
    async def test_worker_health_endpoint_includes_gpu_status(self):
        """Worker health endpoint reports GPU status."""
        from fastapi.testclient import TestClient
        from main import TrainingHostWorker

        worker = TrainingHostWorker(
            worker_port=5002,
            backend_url="http://test-backend:8000",
            capabilities={"gpu": False},
        )

        client = TestClient(worker.app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert "healthy" in data
        assert data["healthy"] is True
        assert "service" in data
        assert "worker_status" in data  # idle or busy

    @pytest.mark.asyncio
    async def test_training_endpoints_still_available(self):
        """Domain-specific training endpoints are still available."""
        from main import TrainingHostWorker

        worker = TrainingHostWorker(
            worker_port=5002,
            backend_url="http://test-backend:8000",
            capabilities={"gpu": False},
        )

        # Verify training endpoints are registered
        routes = [route.path for route in worker.app.routes]

        # Check for actual training endpoints from training router
        assert "/training/start" in routes
        assert "/training/evaluate" in routes
        assert "/training/sessions" in routes
        assert "/training/result/{session_id}" in routes


class TestWorkerSelfRegistration:
    """Test worker self-registration with backend."""

    @pytest.mark.asyncio
    async def test_worker_self_registers_on_startup(self):
        """Worker calls backend's /workers/register endpoint on startup."""
        from main import TrainingHostWorker

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            worker = TrainingHostWorker(
                worker_port=5002,
                backend_url="http://test-backend:8000",
                capabilities={"gpu": False},
            )

            # Trigger self-registration
            await worker.self_register()

            # Verify registration was called
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args

            assert call_args[0][0] == "http://test-backend:8000/api/v1/workers/register"

            payload = call_args[1]["json"]
            assert "worker_id" in payload
            assert payload["worker_type"] == "training"
            assert "endpoint_url" in payload
            assert "capabilities" in payload

    @pytest.mark.asyncio
    async def test_gpu_capabilities_included_in_registration(self):
        """GPU capabilities are included in registration payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            from main import TrainingHostWorker

            cuda_capabilities = {
                "gpu": True,
                "gpu_type": "CUDA",
                "gpu_count": 1,
            }

            worker = TrainingHostWorker(
                worker_port=5002,
                backend_url="http://test-backend:8000",
                capabilities=cuda_capabilities,
            )

            await worker.self_register()

            # Check registration payload includes GPU info
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]

            assert payload["capabilities"]["gpu"] is True
            assert payload["capabilities"]["gpu_type"] == "CUDA"
            assert payload["capabilities"]["gpu_count"] == 1
