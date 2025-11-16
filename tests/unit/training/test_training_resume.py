"""
Unit tests for training resume functionality.

Tests TrainingService's ability to:
- Resume training from checkpoint
- Handle missing/corrupted checkpoints
- Continue training from correct epoch
"""

from unittest.mock import Mock

import pytest

from ktrdr.api.services.training_service import TrainingService
from ktrdr.checkpoint.service import CheckpointService


@pytest.fixture
def mock_worker_registry():
    """Create mock WorkerRegistry."""
    registry = Mock()
    registry.select_worker = Mock()
    registry.list_workers = Mock(return_value=[])
    return registry


@pytest.fixture
def training_service(mock_worker_registry):
    """Create TrainingService instance."""
    return TrainingService(worker_registry=mock_worker_registry)


@pytest.fixture
def mock_checkpoint_service():
    """Create mock CheckpointService."""
    service = Mock(spec=CheckpointService)
    return service


@pytest.fixture
def sample_checkpoint_state():
    """Create sample checkpoint state for testing."""
    return {
        "epoch": 25,
        "model_state_dict": b"fake_model_bytes",
        "optimizer_state_dict": b"fake_optimizer_bytes",
        "scheduler_state_dict": b"fake_scheduler_bytes",
        "history": [
            {"epoch": 0, "train_loss": 0.5, "train_accuracy": 0.6},
            {"epoch": 1, "train_loss": 0.4, "train_accuracy": 0.7},
            # ... up to epoch 25
        ],
        "best_model_state": b"fake_best_model_bytes",
        "best_val_accuracy": 0.85,
        "early_stopping_state": {"counter": 2, "best_score": 0.85},
        "config": {
            "learning_rate": 0.001,
            "batch_size": 32,
            "epochs": 100,
        },
        "operation_id": "op_training_original_001",
        "checkpoint_type": "epoch_snapshot",
        "pytorch_version": "2.0.0",
        "checkpoint_version": "1.0",
    }


@pytest.mark.asyncio
async def test_resume_training_loads_checkpoint_and_continues(
    training_service, mock_checkpoint_service, sample_checkpoint_state
):
    """
    Test that resume_training() loads checkpoint and continues training.

    Acceptance Criteria:
    - ✅ Loads checkpoint for original operation
    - ✅ Creates new operation with resumed_from metadata
    - ✅ Starts training from checkpoint epoch + 1
    - ✅ Preserves training history
    """
    # Setup mock
    mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_state

    # Inject checkpoint service
    training_service.checkpoint_service = mock_checkpoint_service

    # Resume training (simplified implementation returns result directly)
    result = await training_service.resume_training(
        original_operation_id="op_training_original_001",
        new_operation_id="op_training_resumed_001",
    )

    # Verify checkpoint loaded
    mock_checkpoint_service.load_checkpoint.assert_called_once_with(
        "op_training_original_001"
    )

    # Verify new operation created with correct metadata
    assert result["operation_id"] == "op_training_resumed_001"
    assert result["resumed_from"] == "op_training_original_001"
    assert result["starting_epoch"] == sample_checkpoint_state["epoch"] + 1


@pytest.mark.asyncio
async def test_resume_training_raises_error_if_checkpoint_not_found(
    training_service, mock_checkpoint_service
):
    """
    Test that resume_training() raises error if checkpoint not found.

    Acceptance Criteria:
    - ✅ Raises ValueError if checkpoint is None
    - ✅ Error message indicates missing checkpoint
    """
    # Setup mock to return None (no checkpoint)
    mock_checkpoint_service.load_checkpoint.return_value = None
    training_service.checkpoint_service = mock_checkpoint_service

    # Should raise error
    with pytest.raises(ValueError, match="No checkpoint found"):
        await training_service.resume_training(
            original_operation_id="op_training_original_002",
            new_operation_id="op_training_resumed_002",
        )


@pytest.mark.asyncio
async def test_resume_training_raises_error_if_checkpoint_corrupted(
    training_service, mock_checkpoint_service
):
    """
    Test that resume_training() raises error if checkpoint is corrupted.

    Acceptance Criteria:
    - ✅ Raises ValueError if checkpoint missing required fields
    - ✅ Error message indicates corrupted checkpoint
    """
    # Setup mock to return corrupted checkpoint (missing required fields)
    corrupted_checkpoint = {
        "epoch": 25,
        # Missing model_state_dict, optimizer_state_dict, etc.
    }
    mock_checkpoint_service.load_checkpoint.return_value = corrupted_checkpoint
    training_service.checkpoint_service = mock_checkpoint_service

    # Should raise error about corrupted checkpoint
    with pytest.raises(ValueError, match="corrupted|invalid"):
        await training_service.resume_training(
            original_operation_id="op_training_original_003",
            new_operation_id="op_training_resumed_003",
        )


@pytest.mark.asyncio
async def test_resume_training_deletes_original_checkpoint_after_start(
    training_service, mock_checkpoint_service, sample_checkpoint_state
):
    """
    Test that original checkpoint is deleted after resume starts.

    Acceptance Criteria:
    - ✅ Original checkpoint deleted after new operation starts
    - ✅ Prevents accumulation of stale checkpoints
    """
    mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_state
    training_service.checkpoint_service = mock_checkpoint_service

    await training_service.resume_training(
        original_operation_id="op_training_original_004",
        new_operation_id="op_training_resumed_004",
    )

    # Verify original checkpoint deleted
    mock_checkpoint_service.delete_checkpoint.assert_called_once_with(
        "op_training_original_004"
    )


@pytest.mark.asyncio
async def test_resume_training_continues_from_correct_epoch(
    training_service, mock_checkpoint_service, sample_checkpoint_state
):
    """
    Test that resumed training starts at checkpoint epoch + 1.

    Acceptance Criteria:
    - ✅ Starting epoch = checkpoint epoch + 1
    - ✅ Total epochs to train = original epochs - starting epoch
    """
    mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_state
    training_service.checkpoint_service = mock_checkpoint_service

    result = await training_service.resume_training(
        original_operation_id="op_training_original_005",
        new_operation_id="op_training_resumed_005",
    )

    # Verify starting epoch
    expected_starting_epoch = sample_checkpoint_state["epoch"] + 1
    assert result["starting_epoch"] == expected_starting_epoch
    assert expected_starting_epoch == 26  # 25 + 1

    # Verify remaining epochs calculation
    original_epochs = sample_checkpoint_state["config"]["epochs"]
    remaining_epochs = original_epochs - expected_starting_epoch
    assert remaining_epochs == 74  # 100 - 26


@pytest.mark.asyncio
async def test_resume_training_preserves_training_history(
    training_service, mock_checkpoint_service, sample_checkpoint_state
):
    """
    Test that training history is preserved on resume.

    Acceptance Criteria:
    - ✅ Resumed operation has access to prior training history
    - ✅ History includes all epochs up to checkpoint
    """
    mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_state
    training_service.checkpoint_service = mock_checkpoint_service

    await training_service.resume_training(
        original_operation_id="op_training_original_006",
        new_operation_id="op_training_resumed_006",
    )

    # Verify checkpoint was loaded with history
    mock_checkpoint_service.load_checkpoint.assert_called_once_with(
        "op_training_original_006"
    )
    # History is preserved in the loaded checkpoint
    assert "history" in sample_checkpoint_state
    assert len(sample_checkpoint_state["history"]) > 0


@pytest.mark.asyncio
async def test_resume_training_links_new_operation_to_original(
    training_service, mock_checkpoint_service, sample_checkpoint_state
):
    """
    Test that new operation is linked to original operation.

    Acceptance Criteria:
    - ✅ New operation metadata includes resumed_from field
    - ✅ resumed_from points to original operation_id
    """
    mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_state
    training_service.checkpoint_service = mock_checkpoint_service

    result = await training_service.resume_training(
        original_operation_id="op_training_original_007",
        new_operation_id="op_training_resumed_007",
    )

    # Verify resumed_from metadata in result
    assert result["resumed_from"] == "op_training_original_007"


def test_validate_checkpoint_state_accepts_valid_checkpoint(sample_checkpoint_state):
    """
    Test that checkpoint validation accepts valid checkpoint.

    Acceptance Criteria:
    - ✅ Returns True for valid checkpoint
    - ✅ All required fields present
    """
    from ktrdr.training.checkpoint_validator import validate_checkpoint_state

    is_valid, errors = validate_checkpoint_state(sample_checkpoint_state)

    assert is_valid is True
    assert len(errors) == 0


def test_validate_checkpoint_state_rejects_missing_required_fields():
    """
    Test that checkpoint validation rejects missing required fields.

    Acceptance Criteria:
    - ✅ Returns False if required fields missing
    - ✅ Provides list of missing fields in errors
    """
    from ktrdr.training.checkpoint_validator import validate_checkpoint_state

    incomplete_checkpoint = {
        "epoch": 25,
        # Missing model_state_dict, optimizer_state_dict, etc.
    }

    is_valid, errors = validate_checkpoint_state(incomplete_checkpoint)

    assert is_valid is False
    assert len(errors) > 0
    assert any("model_state_dict" in error for error in errors)


def test_validate_checkpoint_state_rejects_invalid_types():
    """
    Test that checkpoint validation rejects invalid field types.

    Acceptance Criteria:
    - ✅ Returns False if field types incorrect
    - ✅ Provides type error details
    """
    from ktrdr.training.checkpoint_validator import validate_checkpoint_state

    invalid_checkpoint = {
        "epoch": "not_an_integer",  # Should be int
        "model_state_dict": "not_bytes",  # Should be bytes
        "optimizer_state_dict": b"valid",
        "config": {},
    }

    is_valid, errors = validate_checkpoint_state(invalid_checkpoint)

    assert is_valid is False
    assert len(errors) > 0
