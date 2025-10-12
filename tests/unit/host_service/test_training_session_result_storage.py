"""
Unit tests for TrainingSession result storage (Task 3.3).

Tests that TrainingSession can store and retrieve the complete training result
from TrainingPipeline, enabling result harmonization between local and host paths.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

# Add training-host-service to path for imports
training_host_service_path = Path(__file__).parent.parent.parent.parent / "training-host-service"
if str(training_host_service_path) not in sys.path:
    sys.path.insert(0, str(training_host_service_path))

from services.training_service import TrainingSession  # noqa: E402


@pytest.fixture
def mock_training_result() -> dict[str, Any]:
    """Create a mock training result matching TrainingPipeline output format."""
    return {
        "model_path": "/path/to/model.pt",
        "training_metrics": {
            "final_train_loss": 0.123,
            "final_val_loss": 0.145,
            "final_train_accuracy": 0.89,
            "final_val_accuracy": 0.87,
            "epochs_completed": 100,
            "early_stopped": False,
            "training_time_minutes": 5.2,
            "best_epoch": 85,
            "final_learning_rate": 0.0001,
        },
        "test_metrics": {
            "test_loss": 0.150,
            "test_accuracy": 0.86,
            "precision": 0.85,
            "recall": 0.84,
            "f1_score": 0.845,
        },
        "artifacts": {
            "feature_importance": {"rsi": 0.3, "macd": 0.25},
            "per_symbol_metrics": {"AAPL": {"accuracy": 0.87}},
        },
        "model_info": {
            "model_type": "MLPTradingModel",
            "num_features": 10,
            "hidden_layers": [64, 32],
        },
        "data_summary": {
            "symbols": ["AAPL"],
            "timeframes": ["1d"],
            "total_samples": 1000,
            "train_samples": 600,
            "val_samples": 200,
            "test_samples": 200,
        },
    }


@pytest.fixture
def training_session() -> TrainingSession:
    """Create a TrainingSession for testing."""
    config = {
        "strategy_yaml": "name: test",
        "symbols": ["AAPL"],
        "timeframes": ["1d"],
        "training_config": {"epochs": 100},
    }
    return TrainingSession(session_id="test-session-123", config=config)


class TestTrainingSessionResultStorage:
    """Test TrainingSession can store and retrieve training results."""

    def test_training_session_has_training_result_field(self, training_session):
        """Test that TrainingSession has training_result field."""
        # This test will FAIL until we add the field
        assert hasattr(training_session, "training_result")
        assert training_session.training_result is None

    def test_training_session_can_store_training_result(
        self, training_session, mock_training_result
    ):
        """Test that TrainingSession can store a complete training result."""
        # This test will FAIL until we add the field
        training_session.training_result = mock_training_result

        assert training_session.training_result is not None
        assert training_session.training_result["model_path"] == "/path/to/model.pt"
        assert training_session.training_result["training_metrics"]["final_train_loss"] == 0.123
        assert training_session.training_result["test_metrics"]["test_accuracy"] == 0.86

    def test_training_session_result_is_optional(self, training_session):
        """Test that training_result is optional (None initially)."""
        # This test will FAIL until we add the field
        assert training_session.training_result is None

    def test_training_session_can_update_training_result(
        self, training_session, mock_training_result
    ):
        """Test that training_result can be updated after initial storage."""
        # This test will FAIL until we add the field
        training_session.training_result = mock_training_result

        # Update with new result
        updated_result = mock_training_result.copy()
        updated_result["training_metrics"]["final_train_loss"] = 0.100
        training_session.training_result = updated_result

        assert training_session.training_result["training_metrics"]["final_train_loss"] == 0.100

    def test_training_session_result_preserves_all_fields(
        self, training_session, mock_training_result
    ):
        """Test that all fields in training result are preserved."""
        # This test will FAIL until we add the field
        training_session.training_result = mock_training_result

        # Verify all top-level keys are preserved
        expected_keys = {
            "model_path",
            "training_metrics",
            "test_metrics",
            "artifacts",
            "model_info",
            "data_summary",
        }
        assert set(training_session.training_result.keys()) == expected_keys

        # Verify nested structures are preserved
        assert "feature_importance" in training_session.training_result["artifacts"]
        assert "per_symbol_metrics" in training_session.training_result["artifacts"]


class TestTrainingSessionGetStatusWithResult:
    """Test that get_session_status returns training_result when completed."""

    def test_get_progress_dict_does_not_include_training_result(
        self, training_session, mock_training_result
    ):
        """Test that get_progress_dict() doesn't include training_result (only progress)."""
        # This is existing behavior - should continue to work
        training_session.training_result = mock_training_result
        training_session.status = "running"

        progress = training_session.get_progress_dict()

        # Progress dict should NOT include training_result
        assert "training_result" not in progress
        # It should only have progress-related fields (epoch, batch, progress_percent, etc.)
        assert "epoch" in progress
        assert "batch" in progress
        assert "progress_percent" in progress


# Note: Status endpoint tests will be in separate file for training_service.py
