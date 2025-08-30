"""
Test configuration and fixtures for Training Host Service tests.
"""

import asyncio
import shutil

# Add parent directory to path for imports
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_gpu_available():
    """Mock torch.cuda.is_available to return True."""
    with patch("torch.cuda.is_available", return_value=True):
        with patch("torch.cuda.device_count", return_value=1):
            with patch("torch.cuda.get_device_properties") as mock_props:
                mock_props.return_value.total_memory = 8 * 1024**3  # 8GB
                with patch("torch.cuda.memory_allocated", return_value=0):
                    with patch("torch.cuda.get_device_name", return_value="Test GPU"):
                        yield


@pytest.fixture
def mock_gpu_unavailable():
    """Mock torch.cuda.is_available to return False."""
    with patch("torch.cuda.is_available", return_value=False):
        with patch("torch.cuda.device_count", return_value=0):
            yield


@pytest.fixture
def sample_training_config():
    """Provide sample training configuration."""
    return {
        "model_config": {
            "type": "mlp",
            "input_size": 50,
            "hidden_layers": [64, 32],
            "num_classes": 3,
            "dropout": 0.2,
        },
        "training_config": {
            "epochs": 10,
            "batch_size": 32,
            "learning_rate": 0.001,
            "optimizer": "adam",
            "loss_function": "cross_entropy",
        },
        "data_config": {
            "symbols": ["EURUSD", "GBPUSD"],
            "timeframes": ["15m", "1h"],
            "features": ["rsi", "sma", "ema"],
            "train_split": 0.8,
            "validation_split": 0.1,
        },
        "gpu_config": {"memory_fraction": 0.8, "enable_mixed_precision": True},
    }


@pytest.fixture
def mock_training_session():
    """Mock training session for testing."""
    session_mock = Mock()
    session_mock.session_id = "test-session-123"
    session_mock.status = "running"
    session_mock.current_epoch = 5
    session_mock.total_epochs = 10
    session_mock.current_batch = 50
    session_mock.total_batches = 100
    session_mock.metrics = {
        "train_loss": [1.0, 0.8, 0.6, 0.4, 0.3],
        "train_accuracy": [0.5, 0.6, 0.7, 0.8, 0.85],
        "val_loss": [1.1, 0.9, 0.7, 0.5, 0.4],
        "val_accuracy": [0.45, 0.55, 0.65, 0.75, 0.8],
    }
    session_mock.best_metrics = {
        "train_loss": 0.3,
        "train_accuracy": 0.85,
        "val_loss": 0.4,
        "val_accuracy": 0.8,
    }
    session_mock.start_time = datetime.fromisoformat("2024-01-01T10:00:00")
    session_mock.last_updated = datetime.fromisoformat("2024-01-01T10:30:00")
    session_mock.error = None

    # Mock methods
    session_mock.get_progress_dict.return_value = {
        "epoch": 5,
        "total_epochs": 10,
        "batch": 50,
        "total_batches": 100,
        "progress_percent": 50.0,
    }

    session_mock.get_resource_usage.return_value = {
        "gpu_allocated": True,
        "memory_monitoring": True,
        "performance_optimization": True,
        "gpu_memory": {
            "allocated_mb": 2048,
            "total_mb": 8192,
            "utilization_percent": 25.0,
        },
        "system_memory": {
            "process_mb": 1024,
            "system_percent": 60.0,
            "system_total_mb": 16384,
        },
    }

    return session_mock


@pytest.fixture
async def mock_training_service():
    """Mock training service for testing."""
    service = Mock()
    service.sessions = {}
    service.max_concurrent_sessions = 1
    service.session_timeout_minutes = 60
    service.global_gpu_manager = Mock()

    # Mock async methods
    async def mock_create_session(*args, **kwargs):
        return "test-session-123"

    async def mock_stop_session(*args, **kwargs):
        return True

    async def mock_cleanup_session(*args, **kwargs):
        return True

    async def mock_shutdown():
        pass

    service.create_session = mock_create_session
    service.stop_session = mock_stop_session
    service.get_session_status = Mock(
        return_value={
            "session_id": "test-session-123",
            "status": "running",
            "progress": {"epoch": 5, "total_epochs": 10, "progress_percent": 50.0},
            "metrics": {"current": {}, "best": {}},
            "resource_usage": {"gpu_allocated": True},
            "start_time": "2024-01-01T10:00:00",
            "last_updated": "2024-01-01T10:30:00",
            "error": None,
        }
    )
    service.list_sessions = Mock(return_value=[])
    service.cleanup_session = mock_cleanup_session
    service.shutdown = mock_shutdown

    yield service


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    from fastapi.testclient import TestClient

    # Import after patching to avoid import-time GPU checks
    with patch("torch.cuda.is_available", return_value=False):
        with patch("torch.cuda.device_count", return_value=0):
            from main import app

            client = TestClient(app)
            yield client


@pytest.fixture
def async_client():
    """Create an async test client for the FastAPI application."""
    import httpx

    with patch("torch.cuda.is_available", return_value=False):
        from main import app

        @pytest.fixture
        async def _async_client():
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                yield client

        return _async_client


# Performance test fixtures


@pytest.fixture
def performance_config():
    """Configuration for performance tests."""
    return {
        "max_sessions": 3,
        "requests_per_second": 10,
        "test_duration_seconds": 30,
        "acceptable_response_time_ms": 100,
        "acceptable_error_rate": 0.01,
    }


# Integration test fixtures


@pytest.fixture
def integration_config():
    """Configuration for integration tests."""
    return {
        "service_url": "http://localhost:5002",
        "health_check_timeout": 10,
        "training_timeout": 300,
        "cleanup_timeout": 30,
    }
