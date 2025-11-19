"""Unit tests for TrainingProgressBridge checkpoint state caching.

This module tests the checkpoint state caching functionality added in Task 3.7,
which enables cancellation checkpoints to contain full domain state (model artifacts)
instead of just lightweight progress metadata.
"""

from pathlib import Path

import pytest

from ktrdr.api.models.operations import OperationMetadata
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge


@pytest.fixture
def training_context():
    """Create minimal training context for testing."""
    metadata = OperationMetadata(
        parameters={"test": "params"},
        timestamps={},
    )
    return TrainingOperationContext(
        operation_id="test_op_001",
        strategy_name="test_strategy",
        strategy_path=Path("/tmp/test_strategy.yaml"),
        strategy_config={},
        symbols=["AAPL"],
        timeframes=["1h"],
        start_date="2024-01-01",
        end_date="2024-12-31",
        training_config={},
        analytics_enabled=False,
        use_host_service=False,
        training_mode="local",
        total_epochs=100,
        total_batches=None,
        metadata=metadata,
        session_id=None,
    )


@pytest.fixture
def progress_bridge(training_context):
    """Create TrainingProgressBridge for testing."""
    return TrainingProgressBridge(
        context=training_context,
        update_progress_callback=lambda **kwargs: None,  # Mock callback
    )


class TestTrainingProgressBridgeCheckpointCaching:
    """Test suite for checkpoint state caching in TrainingProgressBridge."""

    def test_set_latest_checkpoint_state_caches_data_and_artifacts(
        self, progress_bridge
    ):
        """Test that set_latest_checkpoint_state() caches checkpoint data and artifacts."""
        checkpoint_data = {
            "epoch": 45,
            "train_loss": 0.65,
            "val_accuracy": 0.72,
            "training_history": [
                {"epoch": 0, "train_loss": 0.9},
                {"epoch": 44, "train_loss": 0.65},
            ],
        }

        artifacts = {
            "model.pt": b"mock_model_state_dict_data",
            "optimizer.pt": b"mock_optimizer_state_dict_data",
        }

        # Cache checkpoint state
        progress_bridge.set_latest_checkpoint_state(checkpoint_data, artifacts)

        # Verify cached data is accessible (internal state check)
        assert progress_bridge._latest_checkpoint_data == checkpoint_data
        assert progress_bridge._latest_artifacts == artifacts

    @pytest.mark.asyncio
    async def test_get_state_returns_cached_checkpoint_data(self, progress_bridge):
        """Test that get_state() returns cached checkpoint data with artifacts."""
        checkpoint_data = {
            "epoch": 45,
            "train_loss": 0.65,
            "config": {"learning_rate": 0.001},
        }

        artifacts = {
            "model.pt": b"model_data",
            "optimizer.pt": b"optimizer_data",
        }

        # Cache state
        progress_bridge.set_latest_checkpoint_state(checkpoint_data, artifacts)

        # Get state (should include cached data + artifacts)
        state = await progress_bridge.get_state()

        # Verify state contains progress info
        assert state["operation_id"] == "test_op_001"
        assert state["operation_type"] == "training"
        assert state["status"] == "running"

        # Verify state contains cached checkpoint data
        assert state["epoch"] == 45
        assert state["train_loss"] == 0.65
        assert state["config"] == {"learning_rate": 0.001}

        # Verify state contains artifacts
        assert "artifacts" in state
        assert state["artifacts"] == artifacts

    @pytest.mark.asyncio
    async def test_get_state_without_cached_data_returns_basic_state(
        self, progress_bridge
    ):
        """Test that get_state() returns basic state when no checkpoint cached."""
        # Update progress first
        progress_bridge.on_epoch(epoch=10, total_epochs=100, metrics={"train_loss": 0.8})

        # Get state without caching checkpoint data
        state = await progress_bridge.get_state()

        # Should return basic state
        assert state["operation_id"] == "test_op_001"
        assert state["operation_type"] == "training"
        assert state["status"] == "running"
        assert "progress" in state
        assert state["progress"]["percentage"] > 0  # Some progress

        # Should have empty artifacts (no checkpoint cached)
        assert state["artifacts"] == {}

    @pytest.mark.asyncio
    async def test_get_state_includes_current_progress(self, progress_bridge):
        """Test that get_state() includes current progress info."""
        # Update progress
        progress_bridge.on_epoch(epoch=50, total_epochs=100, metrics={"train_loss": 0.5})

        # Get state (should include current progress)
        state = await progress_bridge.get_state()

        # Verify progress included
        assert "progress" in state
        assert state["progress"]["percentage"] > 0
        assert state["progress"]["message"]  # Should have message

    @pytest.mark.asyncio
    async def test_multiple_set_checkpoint_state_updates_cache(self, progress_bridge):
        """Test that calling set_latest_checkpoint_state() multiple times updates cache."""
        # First checkpoint
        checkpoint_data_1 = {"epoch": 10, "train_loss": 0.9}
        artifacts_1 = {"model.pt": b"model_v1"}
        progress_bridge.set_latest_checkpoint_state(checkpoint_data_1, artifacts_1)

        # Second checkpoint (should replace first)
        checkpoint_data_2 = {"epoch": 20, "train_loss": 0.7}
        artifacts_2 = {"model.pt": b"model_v2", "optimizer.pt": b"opt_v2"}
        progress_bridge.set_latest_checkpoint_state(checkpoint_data_2, artifacts_2)

        # Get state (should have second checkpoint)
        state = await progress_bridge.get_state()

        assert state["epoch"] == 20
        assert state["train_loss"] == 0.7
        assert state["artifacts"]["model.pt"] == b"model_v2"
        assert "optimizer.pt" in state["artifacts"]

    @pytest.mark.asyncio
    async def test_get_state_started_at_included(self, progress_bridge):
        """Test that get_state() includes started_at timestamp if available."""
        # Simulate started_at being set (normally done by ProgressBridge base class)
        # For this test, we'll just verify it's included if present
        from datetime import datetime

        progress_bridge.started_at = datetime.now()

        state = await progress_bridge.get_state()

        # Should include started_at
        assert state["started_at"] is not None
        assert isinstance(state["started_at"], str)  # ISO format
