"""
Basic functionality tests for the training host service.
Tests core functionality without complex mocking.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_config_import():
    """Test that configuration can be imported and initialized."""
    with patch("torch.cuda.is_available", return_value=False):
        from config import get_host_service_config

        config = get_host_service_config()
        assert config.host_service.host == "127.0.0.1"
        assert config.host_service.port == 5002
        assert config.host_service.log_level == "INFO"


def test_training_session_basic():
    """Test basic TrainingSession functionality."""
    from services.training_service import TrainingSession

    config = {
        "model_config": {"type": "test"},
        "training_config": {"epochs": 10},
        "data_config": {"symbols": ["TEST"]},
    }

    session = TrainingSession("test-session", config)

    assert session.session_id == "test-session"
    assert session.config == config
    assert session.status == "initializing"
    assert session.current_epoch == 0
    assert session.total_epochs == 10


def test_training_session_progress():
    """Test training session progress tracking."""
    from services.training_service import TrainingSession

    config = {
        "model_config": {"type": "test"},
        "training_config": {"epochs": 10},
        "data_config": {"symbols": ["TEST"]},
    }

    session = TrainingSession("test-session", config)

    # Update progress
    metrics = {"loss": 0.5, "accuracy": 0.8}
    session.update_progress(5, 50, metrics)

    assert session.current_epoch == 5
    assert session.current_batch == 50
    assert session.metrics["loss"] == [0.5]
    assert session.metrics["accuracy"] == [0.8]

    # Test progress dict
    progress = session.get_progress_dict()
    assert progress["epoch"] == 5
    assert progress["total_epochs"] == 10
    assert progress["progress_percent"] == 50.0


def test_service_basic_operations():
    """Test basic TrainingService operations."""
    from services.training_service import TrainingService

    with patch.object(TrainingService, "_initialize_global_resources"):
        service = TrainingService(max_concurrent_sessions=2, session_timeout_minutes=30)

        assert service.max_concurrent_sessions == 2
        assert service.session_timeout_minutes == 30
        assert service.sessions == {}
        assert service.cleanup_task is None  # Should be None initially


def test_health_response_models():
    """Test health response model creation."""
    from endpoints.health import DetailedHealthResponse, HealthResponse

    # Test basic health response
    health_data = {
        "healthy": True,
        "service": "training-host",
        "timestamp": "2024-01-01T10:00:00",
        "gpu_status": {"available": False},
        "system_info": {"cpu_percent": 25.0},
    }

    health_response = HealthResponse(**health_data)
    assert health_response.healthy is True
    assert health_response.service == "training-host"

    # Test detailed health response
    detailed_data = {
        "healthy": True,
        "service": "training-host",
        "timestamp": "2024-01-01T10:00:00",
        "gpu_available": False,
        "gpu_device_count": 0,
        "gpu_memory_total_mb": 0.0,
        "gpu_memory_allocated_mb": 0.0,
        "active_training_sessions": 0,
        "system_memory_usage_percent": 60.0,
        "system_memory_total_mb": 16384.0,
        "uptime_seconds": 100.0,
        "gpu_manager_status": {"initialized": False},
    }

    detailed_response = DetailedHealthResponse(**detailed_data)
    assert detailed_response.healthy is True
    assert detailed_response.gpu_available is False


def test_training_request_models():
    """Test training request model creation."""
    from endpoints.training import TrainingStartRequest, TrainingStopRequest

    # Test training start request
    start_data = {
        "model_configuration": {"type": "test"},
        "training_configuration": {"epochs": 10},
        "data_configuration": {"symbols": ["TEST"]},
    }

    start_request = TrainingStartRequest(**start_data)
    assert start_request.model_configuration["type"] == "test"
    assert start_request.training_configuration["epochs"] == 10

    # Test training stop request
    stop_data = {"session_id": "test-session", "save_checkpoint": True}

    stop_request = TrainingStopRequest(**stop_data)
    assert stop_request.session_id == "test-session"
    assert stop_request.save_checkpoint is True


@pytest.mark.asyncio
async def test_async_basic_functionality():
    """Test async functionality works correctly."""
    import asyncio

    # Simple async test to verify async setup works
    async def dummy_async_operation():
        await asyncio.sleep(0.001)
        return "success"

    result = await dummy_async_operation()
    assert result == "success"
