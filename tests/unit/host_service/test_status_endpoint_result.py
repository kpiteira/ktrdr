"""
Unit tests for status endpoint returning training_result (Task 3.3).

Tests that the get_session_status method returns the complete training result
when status is 'completed', enabling harmonization with local training format.
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

from services.training_service import TrainingService, TrainingSession  # noqa: E402


@pytest.fixture
def mock_training_result() -> dict[str, Any]:
    """Create a mock training result."""
    return {
        "model_path": "/models/strategy_v1.pt",
        "training_metrics": {
            "final_train_loss": 0.156,
            "final_val_loss": 0.178,
            "epochs_completed": 100,
        },
        "test_metrics": {
            "test_accuracy": 0.82,
            "precision": 0.80,
        },
        "artifacts": {},
        "model_info": {},
        "data_summary": {},
        "resource_usage": {
            "gpu_used": True,
            "training_mode": "host",
        },
        "session_id": "test-session-789",
    }


@pytest.fixture
def training_service() -> TrainingService:
    """Create a TrainingService instance."""
    return TrainingService()


class TestStatusEndpointWithTrainingResult:
    """Test status endpoint returns training_result when completed."""

    def test_get_session_status_returns_training_result_when_completed(
        self,
        training_service,
        mock_training_result,
    ):
        """Test that get_session_status returns training_result when status='completed'."""
        # This test will FAIL until we implement the new behavior

        # Create session
        config = {"strategy_yaml": "name: test", "training_config": {"epochs": 100}}
        session_id = "test-session-789"
        session = TrainingSession(session_id, config)
        training_service.sessions[session_id] = session

        # Set session to completed with training result
        session.status = "completed"
        session.training_result = mock_training_result

        # Get status
        status_response = training_service.get_session_status(session_id)

        # Verify response includes complete training result
        assert status_response["model_path"] == "/models/strategy_v1.pt"
        assert "training_metrics" in status_response
        assert status_response["training_metrics"]["final_train_loss"] == 0.156
        assert "test_metrics" in status_response
        assert status_response["test_metrics"]["test_accuracy"] == 0.82
        assert "resource_usage" in status_response

    def test_get_session_status_includes_session_metadata(
        self,
        training_service,
        mock_training_result,
    ):
        """Test that response includes session metadata alongside training result."""
        # This test will FAIL until we implement the new behavior

        # Create session
        config = {"strategy_yaml": "name: test"}
        session_id = "test-session-790"
        session = TrainingSession(session_id, config)
        training_service.sessions[session_id] = session

        # Set session to completed with training result
        session.status = "completed"
        session.training_result = mock_training_result

        # Get status
        status_response = training_service.get_session_status(session_id)

        # Verify session metadata is included
        assert status_response["session_id"] == session_id
        assert status_response["status"] == "completed"
        assert "start_time" in status_response
        assert "last_updated" in status_response

    def test_get_session_status_returns_progress_when_running(
        self,
        training_service,
    ):
        """Test that get_session_status returns progress dict when status='running'."""
        # This test verifies existing behavior should continue to work

        # Create session
        config = {"strategy_yaml": "name: test", "training_config": {"epochs": 100}}
        session_id = "test-session-791"
        session = TrainingSession(session_id, config)
        training_service.sessions[session_id] = session

        # Set session to running (no training_result yet)
        session.status = "running"
        session.current_epoch = 50
        session.metrics = {"loss": 0.5}

        # Get status
        status_response = training_service.get_session_status(session_id)

        # Verify response contains progress (not training_result)
        assert status_response["status"] == "running"
        assert "progress" in status_response
        assert "metrics" in status_response
        # Should NOT have training_result fields
        assert "model_path" not in status_response

    def test_get_session_status_returns_progress_when_completed_without_result(
        self,
        training_service,
    ):
        """Test fallback when status='completed' but training_result is None."""
        # This test will FAIL until we implement the new behavior
        # This is an edge case - should not happen in practice, but good to handle

        # Create session
        config = {"strategy_yaml": "name: test"}
        session_id = "test-session-792"
        session = TrainingSession(session_id, config)
        training_service.sessions[session_id] = session

        # Set session to completed but WITHOUT training_result (edge case)
        session.status = "completed"
        session.training_result = None

        # Get status
        status_response = training_service.get_session_status(session_id)

        # Should fall back to progress format
        assert status_response["status"] == "completed"
        assert "progress" in status_response

    def test_get_session_status_preserves_all_training_result_fields(
        self,
        training_service,
        mock_training_result,
    ):
        """Test that all fields in training_result are preserved in response."""
        # This test will FAIL until we implement the new behavior

        # Create session
        config = {"strategy_yaml": "name: test"}
        session_id = "test-session-793"
        session = TrainingSession(session_id, config)
        training_service.sessions[session_id] = session

        # Set session to completed with full training result
        session.status = "completed"
        session.training_result = mock_training_result

        # Get status
        status_response = training_service.get_session_status(session_id)

        # Verify all training_result fields are in response
        expected_keys = {
            "model_path",
            "training_metrics",
            "test_metrics",
            "artifacts",
            "model_info",
            "data_summary",
            "resource_usage",
        }
        for key in expected_keys:
            assert key in status_response, f"Missing key: {key}"

    def test_get_session_status_raises_for_missing_session(
        self,
        training_service,
    ):
        """Test that get_session_status raises for non-existent session."""
        # This test verifies existing behavior should continue to work

        with pytest.raises(Exception, match="Session .* not found"):
            training_service.get_session_status("non-existent-session")
