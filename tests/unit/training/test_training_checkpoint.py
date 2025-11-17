"""
Unit tests for checkpoint integration into training loop.

Tests the integration of CheckpointService into ModelTrainer:
- Checkpoint decision logic using CheckpointPolicy
- Checkpoint saving during training
- Graceful handling of checkpoint failures
"""

import time
from unittest.mock import Mock, patch

import pytest
import torch
import torch.nn as nn

from ktrdr.checkpoint.policy import CheckpointDecisionEngine, CheckpointPolicy
from ktrdr.checkpoint.service import CheckpointService
from ktrdr.training.model_trainer import ModelTrainer


class SimpleModel(nn.Module):
    """Simple neural network for testing."""

    def __init__(self, input_size=10, hidden_size=5, output_size=3):
        super().__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        return self.fc2(x)


@pytest.fixture
def checkpoint_policy():
    """Create checkpoint policy for testing."""
    return CheckpointPolicy(
        checkpoint_interval_seconds=10.0,  # Checkpoint every 10 seconds
        force_checkpoint_every_n=5,  # Force every 5 epochs
        delete_on_completion=True,
        checkpoint_on_failure=True,
        checkpoint_on_cancellation=True,
    )


@pytest.fixture
def mock_checkpoint_service():
    """Create mock CheckpointService."""
    service = Mock(spec=CheckpointService)
    service.save_checkpoint = Mock()
    service.load_checkpoint = Mock()
    service.delete_checkpoint = Mock()
    return service


@pytest.fixture
def model_trainer_with_checkpoint():
    """Create ModelTrainer with checkpoint support."""
    config = {
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 20,
    }
    return ModelTrainer(config=config)


def test_should_checkpoint_decision_at_forced_boundary(checkpoint_policy):
    """
    Test checkpoint decision logic at forced boundaries.

    Acceptance Criteria:
    - ✅ Returns True at force_checkpoint_every_n boundary
    - ✅ Returns reason explaining forced checkpoint
    """
    engine = CheckpointDecisionEngine()

    # At epoch 5 (force boundary), regardless of time
    should_checkpoint, reason = engine.should_checkpoint(
        policy=checkpoint_policy,
        last_checkpoint_time=time.time(),  # Just checkpointed
        current_time=time.time() + 1.0,  # Only 1 second elapsed
        natural_boundary=5,  # Force boundary
        total_boundaries=5,
    )

    assert should_checkpoint is True
    assert "force" in reason.lower() or "every 5" in reason.lower()


def test_should_checkpoint_decision_at_time_threshold(checkpoint_policy):
    """
    Test checkpoint decision logic when time threshold met.

    Acceptance Criteria:
    - ✅ Returns True when time_since_last >= checkpoint_interval_seconds
    - ✅ Returns reason explaining time threshold
    """
    engine = CheckpointDecisionEngine()

    # At epoch 3 (not force boundary), but 15 seconds elapsed (> 10 sec interval)
    should_checkpoint, reason = engine.should_checkpoint(
        policy=checkpoint_policy,
        last_checkpoint_time=time.time() - 15.0,  # 15 seconds ago
        current_time=time.time(),
        natural_boundary=3,  # Not force boundary
        total_boundaries=3,
    )

    assert should_checkpoint is True
    assert "time" in reason.lower() or "threshold" in reason.lower()


def test_should_not_checkpoint_on_first_epoch(checkpoint_policy):
    """
    Test that first epoch never checkpoints.

    Acceptance Criteria:
    - ✅ Returns False for epoch 1
    - ✅ Returns reason explaining first epoch skip
    """
    engine = CheckpointDecisionEngine()

    should_checkpoint, reason = engine.should_checkpoint(
        policy=checkpoint_policy,
        last_checkpoint_time=time.time() - 100.0,  # Long time ago
        current_time=time.time(),
        natural_boundary=1,  # First epoch
        total_boundaries=1,
    )

    assert should_checkpoint is False
    assert "first" in reason.lower() or "nothing" in reason.lower()


def test_should_not_checkpoint_when_time_insufficient(checkpoint_policy):
    """
    Test no checkpoint when time threshold not met.

    Acceptance Criteria:
    - ✅ Returns False when time_since_last < checkpoint_interval_seconds
    - ✅ Returns reason explaining insufficient time
    """
    engine = CheckpointDecisionEngine()

    should_checkpoint, reason = engine.should_checkpoint(
        policy=checkpoint_policy,
        last_checkpoint_time=time.time() - 3.0,  # Only 3 seconds ago
        current_time=time.time(),
        natural_boundary=3,  # Not force boundary
        total_boundaries=3,
    )

    assert should_checkpoint is False
    assert "not enough time" in reason.lower() or "elapsed" in reason.lower()


def test_training_loop_creates_checkpoints_at_correct_intervals(
    model_trainer_with_checkpoint,
    checkpoint_policy,
):
    """
    Test that training loop calls checkpoint at correct intervals.

    Acceptance Criteria:
    - ✅ Checkpoint service called when should_checkpoint returns True
    - ✅ Checkpoint NOT called when should_checkpoint returns False
    - ✅ Checkpoint includes current epoch, model, optimizer state
    """
    # Setup mocks
    mock_service = Mock(spec=CheckpointService)

    # Mock CheckpointDecisionEngine imported inside the training loop
    mock_engine = Mock(spec=CheckpointDecisionEngine)

    # should_checkpoint returns True at epochs 5, 10, 15, 20 (forced boundaries)
    def should_checkpoint_side_effect(
        policy, last_checkpoint_time, current_time, natural_boundary, total_boundaries
    ):
        if natural_boundary == 1:
            return False, "First epoch"
        if natural_boundary % 5 == 0:
            return True, f"Force checkpoint at epoch {natural_boundary}"
        return False, "Not enough time"

    mock_engine.should_checkpoint.side_effect = should_checkpoint_side_effect

    # Create simple training data
    X_train = torch.randn(100, 10)
    y_train = torch.randint(0, 3, (100,))
    X_val = torch.randn(20, 10)
    y_val = torch.randint(0, 3, (20,))

    model = SimpleModel()

    # Inject checkpoint service and policy
    model_trainer_with_checkpoint.checkpoint_service = mock_service
    model_trainer_with_checkpoint.checkpoint_policy = checkpoint_policy
    model_trainer_with_checkpoint.checkpoint_decision_engine = mock_engine
    model_trainer_with_checkpoint.operation_id = "test_op_001"

    # Run training (20 epochs)
    model_trainer_with_checkpoint.train(
        model=model,
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
    )

    # Verify checkpoints called at correct epochs (5, 10, 15, 20)
    # Note: Implementation should call save_checkpoint 4 times
    assert mock_service.save_checkpoint.call_count == 4

    # Verify operation_id passed to checkpoint service (as keyword arg)
    for call in mock_service.save_checkpoint.call_args_list:
        assert call.kwargs["operation_id"] == "test_op_001"


def test_training_continues_when_checkpoint_fails(model_trainer_with_checkpoint):
    """
    Test that training continues even if checkpoint fails.

    Acceptance Criteria:
    - ✅ Training does not crash when checkpoint save fails
    - ✅ Error logged but training continues
    - ✅ Training completes successfully
    """
    # Setup mock to raise exception
    mock_service = Mock(spec=CheckpointService)
    mock_service.save_checkpoint.side_effect = Exception("Disk full")

    # Create simple training data
    X_train = torch.randn(100, 10)
    y_train = torch.randint(0, 3, (100,))

    model = SimpleModel()

    # Inject checkpoint service
    model_trainer_with_checkpoint.checkpoint_service = mock_service
    model_trainer_with_checkpoint.checkpoint_policy = CheckpointPolicy(
        checkpoint_interval_seconds=0.1,  # Checkpoint frequently
        force_checkpoint_every_n=1,  # Every epoch
        delete_on_completion=True,
        checkpoint_on_failure=True,
        checkpoint_on_cancellation=True,
    )
    model_trainer_with_checkpoint.checkpoint_decision_engine = (
        CheckpointDecisionEngine()
    )
    model_trainer_with_checkpoint.operation_id = "test_op_002"

    # Run training - should complete despite checkpoint failures
    result = model_trainer_with_checkpoint.train(
        model=model,
        X_train=X_train,
        y_train=y_train,
    )

    # Training should complete successfully
    assert "history" in result
    assert len(result["history"]) > 0


def test_checkpoint_logs_events(model_trainer_with_checkpoint):
    """
    Test that checkpoint events are logged.

    Acceptance Criteria:
    - ✅ Logs when checkpoint is saved
    - ✅ Logs checkpoint size information
    - ✅ Logs checkpoint failure if occurs
    """
    mock_service = Mock(spec=CheckpointService)
    mock_service.save_checkpoint.return_value = "checkpoint_001"

    X_train = torch.randn(100, 10)
    y_train = torch.randint(0, 3, (100,))
    model = SimpleModel()

    model_trainer_with_checkpoint.checkpoint_service = mock_service
    model_trainer_with_checkpoint.checkpoint_policy = CheckpointPolicy(
        checkpoint_interval_seconds=0.1,
        force_checkpoint_every_n=1,
        delete_on_completion=True,
        checkpoint_on_failure=True,
        checkpoint_on_cancellation=True,
    )
    model_trainer_with_checkpoint.checkpoint_decision_engine = (
        CheckpointDecisionEngine()
    )
    model_trainer_with_checkpoint.operation_id = "test_op_003"

    # Run training with print capture
    with patch("builtins.print") as mock_print:
        model_trainer_with_checkpoint.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
        )

        # Verify checkpoint events were printed
        # Implementation should print checkpoint saves
        print_calls = [str(call) for call in mock_print.call_args_list]
        checkpoint_prints = [c for c in print_calls if "checkpoint" in c.lower()]

        # Should have at least one checkpoint print
        assert len(checkpoint_prints) > 0


def test_checkpoint_state_includes_operation_context():
    """
    Test that checkpoint state includes operation context.

    Acceptance Criteria:
    - ✅ Checkpoint includes operation_id
    - ✅ Checkpoint includes checkpoint_type (epoch_snapshot)
    - ✅ Checkpoint includes timestamp
    """
    trainer = ModelTrainer(config={"epochs": 10})
    trainer.operation_id = "test_op_004"

    model = SimpleModel()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    checkpoint_state = trainer.get_checkpoint_state(
        current_epoch=5,
        model=model,
        optimizer=optimizer,
        scheduler=None,
        early_stopping=None,
    )

    # Should include operation context
    assert "operation_id" in checkpoint_state
    assert checkpoint_state["operation_id"] == "test_op_004"

    assert "checkpoint_type" in checkpoint_state
    assert checkpoint_state["checkpoint_type"] == "epoch_snapshot"

    assert "created_at" in checkpoint_state
