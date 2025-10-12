"""
Unit tests for HostTrainingOrchestrator result storage (Task 3.3).

Tests that HostTrainingOrchestrator stores the TrainingPipeline result
in the session for retrieval by the status endpoint.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

# Add training-host-service to path for imports
training_host_service_path = Path(__file__).parent.parent.parent.parent / "training-host-service"
if str(training_host_service_path) not in sys.path:
    sys.path.insert(0, str(training_host_service_path))

from orchestrator import HostTrainingOrchestrator  # noqa: E402


class MockTrainingSession:
    """Mock TrainingSession for testing."""

    def __init__(self, session_id: str, config: dict[str, Any]):
        self.session_id = session_id
        self.config = config
        self.status = "initializing"
        self.message = "Initializing"
        self.stop_requested = False
        self.training_result = None  # NEW: Field for storing result

    def update_progress(self, epoch: int, batch: int, metrics: dict[str, Any]) -> None:
        """Update progress tracking."""
        pass


@pytest.fixture
def mock_session():
    """Create a mock training session."""
    strategy_yaml = """
name: "test_strategy"
training_data:
  symbols: ["AAPL"]
  timeframes: ["1d"]
indicators:
  - name: "rsi"
    period: 14
fuzzy_sets:
  rsi:
    low:
      type: "trapezoid"
      params: [0, 0, 30, 40]
neural:
  layers: [64, 32]
  dropout: 0.2
training:
  epochs: 5
  batch_size: 32
"""
    config = {
        "strategy_yaml": strategy_yaml,
        "symbols": ["AAPL"],
        "timeframes": ["1d"],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "training_config": {"epochs": 5},
    }
    return MockTrainingSession(session_id="test-session-456", config=config)


@pytest.fixture
def mock_training_result() -> dict[str, Any]:
    """Create a mock training result from TrainingPipeline."""
    return {
        "model_path": "/models/test_model.pt",
        "training_metrics": {
            "final_train_loss": 0.234,
            "final_val_loss": 0.256,
            "epochs_completed": 5,
        },
        "test_metrics": {
            "test_accuracy": 0.78,
            "test_loss": 0.260,
        },
        "artifacts": {
            "feature_importance": {},
        },
        "model_info": {
            "model_type": "MLPTradingModel",
        },
        "data_summary": {
            "symbols": ["AAPL"],
            "timeframes": ["1d"],
        },
    }


class TestHostTrainingOrchestratorResultStorage:
    """Test that HostTrainingOrchestrator stores result in session."""

    @pytest.mark.asyncio
    @patch("orchestrator.TrainingPipeline")
    @patch("orchestrator.DataManager")
    @patch("orchestrator.DeviceManager")
    async def test_orchestrator_stores_result_in_session(
        self,
        mock_device_manager,
        mock_data_manager,
        mock_training_pipeline,
        mock_session,
        mock_training_result,
    ):
        """Test that orchestrator stores TrainingPipeline result in session.training_result."""
        # This test will FAIL until we implement result storage

        # Setup mocks
        mock_training_pipeline.train_strategy.return_value = mock_training_result
        mock_device_manager.get_device_info = Mock(
            return_value={"device_type": "cpu", "device_name": "CPU"}
        )

        # Create orchestrator
        mock_model_storage = Mock()
        orchestrator = HostTrainingOrchestrator(mock_session, mock_model_storage)

        # Run training
        result = await orchestrator.run()

        # Verify result was stored in session
        assert mock_session.training_result is not None
        assert mock_session.training_result["model_path"] == "/models/test_model.pt"
        assert "training_metrics" in mock_session.training_result
        assert "test_metrics" in mock_session.training_result

    @pytest.mark.asyncio
    @patch("orchestrator.TrainingPipeline")
    @patch("orchestrator.DataManager")
    @patch("orchestrator.DeviceManager")
    async def test_orchestrator_stores_result_before_completion(
        self,
        mock_device_manager,
        mock_data_manager,
        mock_training_pipeline,
        mock_session,
        mock_training_result,
    ):
        """Test that result is stored BEFORE setting status to 'completed'."""
        # This test will FAIL until we implement result storage

        # Setup mocks
        mock_training_pipeline.train_strategy.return_value = mock_training_result
        mock_device_manager.get_device_info = Mock(
            return_value={"device_type": "mps", "device_name": "Apple MPS"}
        )

        # Create orchestrator
        mock_model_storage = Mock()
        orchestrator = HostTrainingOrchestrator(mock_session, mock_model_storage)

        # Run training
        await orchestrator.run()

        # Verify result was stored
        assert mock_session.training_result is not None
        # Verify status is completed
        assert mock_session.status == "completed"

    @pytest.mark.asyncio
    @patch("orchestrator.TrainingPipeline")
    @patch("orchestrator.DataManager")
    @patch("orchestrator.DeviceManager")
    async def test_orchestrator_result_includes_host_metadata(
        self,
        mock_device_manager,
        mock_data_manager,
        mock_training_pipeline,
        mock_session,
        mock_training_result,
    ):
        """Test that stored result includes host-specific metadata."""
        # This test will FAIL until we implement result storage

        # Setup mocks
        mock_training_pipeline.train_strategy.return_value = mock_training_result
        mock_device_manager.get_device_info = Mock(
            return_value={
                "device_type": "cuda",
                "device_name": "NVIDIA RTX 3090",
            }
        )

        # Create orchestrator
        mock_model_storage = Mock()
        orchestrator = HostTrainingOrchestrator(mock_session, mock_model_storage)

        # Run training
        await orchestrator.run()

        # Verify stored result includes resource_usage
        assert mock_session.training_result is not None
        assert "resource_usage" in mock_session.training_result
        assert mock_session.training_result["resource_usage"]["gpu_used"] is True
        assert mock_session.training_result["resource_usage"]["gpu_name"] == "NVIDIA RTX 3090"

    @pytest.mark.asyncio
    @patch("orchestrator.TrainingPipeline")
    @patch("orchestrator.DataManager")
    async def test_orchestrator_does_not_store_result_on_failure(
        self,
        mock_data_manager,
        mock_training_pipeline,
        mock_session,
    ):
        """Test that training_result is NOT set if training fails."""
        # This test verifies existing behavior - should already pass

        # Setup mocks to raise exception
        mock_training_pipeline.train_strategy.side_effect = RuntimeError("Training failed")

        # Create orchestrator
        mock_model_storage = Mock()
        orchestrator = HostTrainingOrchestrator(mock_session, mock_model_storage)

        # Run training (should fail)
        with pytest.raises(RuntimeError):
            await orchestrator.run()

        # Verify result was NOT stored (should remain None)
        assert mock_session.training_result is None
        assert mock_session.status == "failed"
