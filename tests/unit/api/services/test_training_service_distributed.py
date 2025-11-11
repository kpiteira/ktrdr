"""
Unit tests for TrainingService distributed-only mode (Task 5.2).

Tests GPU-first CPU-fallback worker selection and distributed-only operation.
"""

from unittest.mock import MagicMock

import pytest

from ktrdr.api.models.workers import WorkerEndpoint, WorkerStatus, WorkerType
from ktrdr.api.services.training_service import TrainingService


class TestTrainingServiceDistributedOnly:
    """Test TrainingService distributed-only behavior (no local execution)."""

    def test_training_service_requires_worker_registry(self):
        """TrainingService should require WorkerRegistry parameter (not Optional)."""
        # This test will fail until we make worker_registry required
        with pytest.raises(
            TypeError, match="missing 1 required positional argument: 'worker_registry'"
        ):
            TrainingService()

    def test_select_training_worker_gpu_first(self):
        """Should select GPU worker when available (GPU-first priority)."""
        # Create mock WorkerRegistry
        mock_registry = MagicMock()

        # Create mock GPU worker
        gpu_worker = WorkerEndpoint(
            worker_id="gpu-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://gpu-worker:5004",
            status=WorkerStatus.AVAILABLE,
            capabilities={"gpu": True, "gpu_type": "CUDA", "cores": 8, "memory_gb": 32},
        )

        # Create mock CPU worker
        cpu_worker = WorkerEndpoint(
            worker_id="cpu-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://cpu-worker:5004",
            status=WorkerStatus.AVAILABLE,
            capabilities={"gpu": False, "cores": 4, "memory_gb": 16},
        )

        # Mock registry returns both GPU and CPU workers
        mock_registry.list_workers.return_value = [gpu_worker, cpu_worker]

        # Create service with registry
        service = TrainingService(worker_registry=mock_registry)

        # Select worker for training
        selected_worker = service._select_training_worker(context={})

        # Should select GPU worker (priority)
        assert selected_worker is not None
        assert selected_worker.worker_id == "gpu-worker-1"
        assert selected_worker.capabilities.get("gpu") is True

    def test_select_training_worker_cpu_fallback(self):
        """Should fallback to CPU worker when no GPU available (CPU fallback)."""
        # Create mock WorkerRegistry
        mock_registry = MagicMock()

        # Create only CPU worker (no GPU)
        cpu_worker = WorkerEndpoint(
            worker_id="cpu-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://cpu-worker:5004",
            status=WorkerStatus.AVAILABLE,
            capabilities={"gpu": False, "cores": 4, "memory_gb": 16},
        )

        # Mock registry returns only CPU worker
        mock_registry.list_workers.return_value = [cpu_worker]

        # Create service with registry
        service = TrainingService(worker_registry=mock_registry)

        # Select worker for training
        selected_worker = service._select_training_worker(context={})

        # Should select CPU worker (fallback)
        assert selected_worker is not None
        assert selected_worker.worker_id == "cpu-worker-1"
        assert selected_worker.capabilities.get("gpu") is False

    def test_select_training_worker_no_workers_available(self):
        """Should raise clear error when no workers available."""
        # Create mock WorkerRegistry with no workers
        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        # Create service with registry
        service = TrainingService(worker_registry=mock_registry)

        # Should raise clear error
        with pytest.raises(RuntimeError, match="No training workers available"):
            service._select_training_worker(context={})

    def test_select_training_worker_multiple_gpus(self):
        """Should select from multiple GPU workers (round-robin via registry)."""
        # Create mock WorkerRegistry
        mock_registry = MagicMock()

        # Create multiple GPU workers
        gpu_worker_1 = WorkerEndpoint(
            worker_id="gpu-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://gpu-worker-1:5004",
            status=WorkerStatus.AVAILABLE,
            capabilities={"gpu": True, "gpu_type": "CUDA", "cores": 8},
        )

        gpu_worker_2 = WorkerEndpoint(
            worker_id="gpu-worker-2",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://gpu-worker-2:5004",
            status=WorkerStatus.AVAILABLE,
            capabilities={"gpu": True, "gpu_type": "CUDA", "cores": 8},
        )

        # Mock registry returns both GPU workers
        mock_registry.list_workers.return_value = [gpu_worker_1, gpu_worker_2]

        # Create service with registry
        service = TrainingService(worker_registry=mock_registry)

        # Select worker for training
        selected_worker = service._select_training_worker(context={})

        # Should select one of the GPU workers
        assert selected_worker is not None
        assert selected_worker.worker_id in ["gpu-worker-1", "gpu-worker-2"]
        assert selected_worker.capabilities.get("gpu") is True

    def test_select_training_worker_gpu_busy_cpu_fallback(self):
        """Should fallback to CPU when all GPU workers are busy."""
        # Create mock WorkerRegistry
        mock_registry = MagicMock()

        # Create CPU worker (AVAILABLE) - only available worker
        cpu_worker = WorkerEndpoint(
            worker_id="cpu-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://cpu-worker:5004",
            status=WorkerStatus.AVAILABLE,
            capabilities={"gpu": False, "cores": 4},
        )

        # Mock registry returns only CPU worker (GPU workers are busy so filtered out by status)
        mock_registry.list_workers.return_value = [cpu_worker]

        # Create service with registry
        service = TrainingService(worker_registry=mock_registry)

        # Select worker for training
        selected_worker = service._select_training_worker(context={})

        # Should select CPU worker (GPU is busy/unavailable)
        assert selected_worker is not None
        assert selected_worker.worker_id == "cpu-worker-1"
        assert selected_worker.capabilities.get("gpu") is False

    def test_worker_selection_requires_workers(self):
        """_select_training_worker should raise clear error when no workers available."""
        # Create mock WorkerRegistry with no workers
        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        # Create service with empty registry
        service = TrainingService(worker_registry=mock_registry)

        # Should raise clear error
        with pytest.raises(RuntimeError, match="No training workers available"):
            service._select_training_worker(context={})

    def test_training_service_logs_gpu_first_cpu_fallback_mode(self):
        """TrainingService should log GPU-first CPU-fallback initialization."""
        mock_registry = MagicMock()

        # Create service - should log initialization mode
        service = TrainingService(worker_registry=mock_registry)

        # Service should be initialized
        assert service.worker_registry is mock_registry
        # Logger call would be checked via log capture in real test


class TestTrainingServiceLegacyCodeRemoval:
    """Test that local execution mode has been removed."""

    def test_initialize_adapter_returns_none(self):
        """_initialize_adapter() should be no-op (returns None for distributed-only)."""
        mock_registry = MagicMock()
        service = TrainingService(worker_registry=mock_registry)

        # Method exists for base class compatibility but returns None
        result = service._initialize_adapter()
        assert result is None

    def test_no_run_local_training_method(self):
        """_run_local_training() method should not exist (legacy code removed)."""
        mock_registry = MagicMock()
        service = TrainingService(worker_registry=mock_registry)

        # This method should not exist anymore
        assert not hasattr(service, "_run_local_training")

    def test_adapter_attribute_is_none(self):
        """Adapter attribute should be None (no adapter in distributed-only mode)."""
        mock_registry = MagicMock()
        service = TrainingService(worker_registry=mock_registry)

        # Adapter exists (from base class) but is None
        assert service.adapter is None


class TestTrainingServiceWorkerSelection:
    """Test worker selection logic and error handling."""

    def test_worker_selection_filters_by_type(self):
        """Should only select TRAINING workers, not BACKTESTING."""
        mock_registry = MagicMock()

        # Create training worker
        training_worker = WorkerEndpoint(
            worker_id="training-worker",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://training:5004",
            status=WorkerStatus.AVAILABLE,
            capabilities={"gpu": False},
        )

        # Create backtesting worker (should be ignored)
        backtest_worker = WorkerEndpoint(
            worker_id="backtest-worker",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://backtest:5003",
            status=WorkerStatus.AVAILABLE,
            capabilities={},
        )

        # Mock registry returns both workers
        mock_registry.list_workers.return_value = [training_worker, backtest_worker]

        service = TrainingService(worker_registry=mock_registry)

        # Should only consider training workers
        selected_worker = service._select_training_worker(context={})

        assert selected_worker is not None
        assert selected_worker.worker_type == WorkerType.TRAINING

    def test_worker_selection_filters_by_status(self):
        """Should only select AVAILABLE workers, not BUSY or UNAVAILABLE."""
        mock_registry = MagicMock()

        # Create workers with different statuses
        available_worker = WorkerEndpoint(
            worker_id="available-worker",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://available:5004",
            status=WorkerStatus.AVAILABLE,
            capabilities={"gpu": False},
        )

        busy_worker = WorkerEndpoint(
            worker_id="busy-worker",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://busy:5004",
            status=WorkerStatus.BUSY,
            capabilities={"gpu": False},
        )

        unavailable_worker = WorkerEndpoint(
            worker_id="unavailable-worker",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://unavailable:5004",
            status=WorkerStatus.TEMPORARILY_UNAVAILABLE,
            capabilities={"gpu": False},
        )

        # Mock registry returns all workers
        mock_registry.list_workers.return_value = [
            available_worker,
            busy_worker,
            unavailable_worker,
        ]

        service = TrainingService(worker_registry=mock_registry)

        # Should only select available worker
        selected_worker = service._select_training_worker(context={})

        assert selected_worker is not None
        assert selected_worker.status == WorkerStatus.AVAILABLE
        assert selected_worker.worker_id == "available-worker"
