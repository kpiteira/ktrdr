"""Unit tests for training checkpoint restore functionality."""

import io
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import torch
import torch.nn as nn
import torch.optim as optim


class TestTrainingResumeContext:
    """Tests for TrainingResumeContext dataclass."""

    def test_context_has_required_fields(self):
        """Context should have all required fields for resume."""
        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        # Create context with all required fields
        context = TrainingResumeContext(
            start_epoch=10,
            model_weights=b"model bytes",
            optimizer_state=b"optimizer bytes",
        )

        assert context.start_epoch == 10
        assert context.model_weights == b"model bytes"
        assert context.optimizer_state == b"optimizer bytes"

    def test_context_has_optional_fields(self):
        """Context should support optional scheduler and best_model."""
        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        context = TrainingResumeContext(
            start_epoch=10,
            model_weights=b"model bytes",
            optimizer_state=b"optimizer bytes",
            scheduler_state=b"scheduler bytes",
            best_model_weights=b"best model bytes",
            training_history={"train_loss": [1.0, 0.8]},
            best_val_loss=0.5,
            original_request={"symbol": "BTCUSD"},
        )

        assert context.scheduler_state == b"scheduler bytes"
        assert context.best_model_weights == b"best model bytes"
        assert context.training_history == {"train_loss": [1.0, 0.8]}
        assert context.best_val_loss == 0.5
        assert context.original_request == {"symbol": "BTCUSD"}

    def test_context_defaults_for_optional_fields(self):
        """Optional fields should have sensible defaults."""
        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        context = TrainingResumeContext(
            start_epoch=10,
            model_weights=b"model bytes",
            optimizer_state=b"optimizer bytes",
        )

        assert context.scheduler_state is None
        assert context.best_model_weights is None
        assert context.training_history == {}
        assert context.best_val_loss == float("inf")
        assert context.original_request == {}


class TestRestoreFromCheckpoint:
    """Tests for restore_from_checkpoint function."""

    @pytest.fixture
    def mock_checkpoint_service(self):
        """Create a mock CheckpointService."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def sample_checkpoint_data(self):
        """Create sample checkpoint data."""
        from ktrdr.checkpoint.checkpoint_service import CheckpointData

        # Create real PyTorch state dicts for testing
        model = nn.Linear(10, 2)
        optimizer = optim.Adam(model.parameters(), lr=0.001)
        scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10)

        # Serialize to bytes
        model_buffer = io.BytesIO()
        torch.save(model.state_dict(), model_buffer)

        optimizer_buffer = io.BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        scheduler_buffer = io.BytesIO()
        torch.save(scheduler.state_dict(), scheduler_buffer)

        best_model_buffer = io.BytesIO()
        torch.save(model.state_dict(), best_model_buffer)

        return CheckpointData(
            operation_id="op_123",
            checkpoint_type="periodic",
            created_at=datetime.now(),
            state={
                "epoch": 9,
                "train_loss": 0.5,
                "val_loss": 0.4,
                "train_accuracy": 0.75,
                "val_accuracy": 0.78,
                "learning_rate": 0.001,
                "best_val_loss": 0.35,
                "training_history": {
                    "train_loss": [1.0, 0.8, 0.6, 0.5],
                    "val_loss": [0.9, 0.7, 0.5, 0.4],
                },
                "original_request": {"symbol": "BTCUSD", "epochs": 100},
            },
            artifacts_path="/checkpoints/op_123",
            artifacts={
                "model.pt": model_buffer.getvalue(),
                "optimizer.pt": optimizer_buffer.getvalue(),
                "scheduler.pt": scheduler_buffer.getvalue(),
                "best_model.pt": best_model_buffer.getvalue(),
            },
        )

    @pytest.mark.asyncio
    async def test_loads_checkpoint_from_service(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should load checkpoint from CheckpointService."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        _context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        mock_checkpoint_service.load_checkpoint.assert_called_once_with(
            "op_123", load_artifacts=True
        )
        assert _context is not None  # Use the variable

    @pytest.mark.asyncio
    async def test_raises_when_no_checkpoint(self, mock_checkpoint_service):
        """Should raise when checkpoint not found."""
        from ktrdr.training.checkpoint_restore import (
            CheckpointNotFoundError,
            restore_from_checkpoint,
        )

        mock_checkpoint_service.load_checkpoint.return_value = None

        with pytest.raises(CheckpointNotFoundError) as exc_info:
            await restore_from_checkpoint(
                checkpoint_service=mock_checkpoint_service,
                operation_id="op_123",
            )

        assert "op_123" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_start_epoch_is_checkpoint_epoch_plus_one(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Resume should start from checkpoint epoch + 1."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        # Checkpoint at epoch 9, resume from epoch 10
        assert context.start_epoch == 10

    @pytest.mark.asyncio
    async def test_model_weights_extracted(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should extract model weights from checkpoint."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        # Verify model weights are bytes
        assert isinstance(context.model_weights, bytes)
        assert len(context.model_weights) > 0

        # Verify they can be loaded by torch
        model_state = torch.load(io.BytesIO(context.model_weights), weights_only=True)
        assert isinstance(model_state, dict)

    @pytest.mark.asyncio
    async def test_optimizer_state_extracted(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should extract optimizer state from checkpoint."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        # Verify optimizer state is bytes
        assert isinstance(context.optimizer_state, bytes)
        assert len(context.optimizer_state) > 0

        # Verify it can be loaded by torch
        opt_state = torch.load(io.BytesIO(context.optimizer_state), weights_only=False)
        assert "state" in opt_state or "param_groups" in opt_state

    @pytest.mark.asyncio
    async def test_scheduler_state_extracted_when_present(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should extract scheduler state when in checkpoint."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        # Verify scheduler state is present
        assert context.scheduler_state is not None
        assert isinstance(context.scheduler_state, bytes)

    @pytest.mark.asyncio
    async def test_scheduler_state_none_when_not_present(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should return None scheduler_state when not in checkpoint."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        # Remove scheduler from artifacts
        del sample_checkpoint_data.artifacts["scheduler.pt"]
        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        assert context.scheduler_state is None

    @pytest.mark.asyncio
    async def test_best_model_weights_extracted_when_present(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should extract best_model weights when in checkpoint."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        assert context.best_model_weights is not None
        assert isinstance(context.best_model_weights, bytes)

    @pytest.mark.asyncio
    async def test_training_history_restored(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should restore training history from checkpoint state."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        assert context.training_history == {
            "train_loss": [1.0, 0.8, 0.6, 0.5],
            "val_loss": [0.9, 0.7, 0.5, 0.4],
        }

    @pytest.mark.asyncio
    async def test_best_val_loss_restored(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should restore best validation loss from checkpoint state."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        assert context.best_val_loss == 0.35

    @pytest.mark.asyncio
    async def test_original_request_restored(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should restore original training request from checkpoint state."""
        from ktrdr.training.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_123",
        )

        assert context.original_request == {"symbol": "BTCUSD", "epochs": 100}


class TestValidateTrainingArtifacts:
    """Tests for artifact validation before restore."""

    @pytest.mark.asyncio
    async def test_raises_when_model_missing(self):
        """Should raise CheckpointCorruptedError when model.pt missing."""
        from ktrdr.checkpoint.checkpoint_service import CheckpointData
        from ktrdr.training.checkpoint_restore import (
            CheckpointCorruptedError,
            restore_from_checkpoint,
        )

        checkpoint_data = CheckpointData(
            operation_id="op_123",
            checkpoint_type="periodic",
            created_at=datetime.now(),
            state={"epoch": 9, "train_loss": 0.5, "val_loss": 0.4},
            artifacts_path="/checkpoints/op_123",
            artifacts={
                # Missing model.pt
                "optimizer.pt": b"optimizer bytes",
            },
        )

        mock_service = AsyncMock()
        mock_service.load_checkpoint.return_value = checkpoint_data

        with pytest.raises(CheckpointCorruptedError) as exc_info:
            await restore_from_checkpoint(
                checkpoint_service=mock_service,
                operation_id="op_123",
            )

        assert "model.pt" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_when_optimizer_missing(self):
        """Should raise CheckpointCorruptedError when optimizer.pt missing."""
        from ktrdr.checkpoint.checkpoint_service import CheckpointData
        from ktrdr.training.checkpoint_restore import (
            CheckpointCorruptedError,
            restore_from_checkpoint,
        )

        checkpoint_data = CheckpointData(
            operation_id="op_123",
            checkpoint_type="periodic",
            created_at=datetime.now(),
            state={"epoch": 9, "train_loss": 0.5, "val_loss": 0.4},
            artifacts_path="/checkpoints/op_123",
            artifacts={
                "model.pt": b"model bytes",
                # Missing optimizer.pt
            },
        )

        mock_service = AsyncMock()
        mock_service.load_checkpoint.return_value = checkpoint_data

        with pytest.raises(CheckpointCorruptedError) as exc_info:
            await restore_from_checkpoint(
                checkpoint_service=mock_service,
                operation_id="op_123",
            )

        assert "optimizer.pt" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_when_artifacts_empty(self):
        """Should raise CheckpointCorruptedError when artifacts are empty."""
        from ktrdr.checkpoint.checkpoint_service import CheckpointData
        from ktrdr.training.checkpoint_restore import (
            CheckpointCorruptedError,
            restore_from_checkpoint,
        )

        checkpoint_data = CheckpointData(
            operation_id="op_123",
            checkpoint_type="periodic",
            created_at=datetime.now(),
            state={"epoch": 9, "train_loss": 0.5, "val_loss": 0.4},
            artifacts_path="/checkpoints/op_123",
            artifacts={
                "model.pt": b"",  # Empty
                "optimizer.pt": b"optimizer bytes",
            },
        )

        mock_service = AsyncMock()
        mock_service.load_checkpoint.return_value = checkpoint_data

        with pytest.raises(CheckpointCorruptedError) as exc_info:
            await restore_from_checkpoint(
                checkpoint_service=mock_service,
                operation_id="op_123",
            )

        assert (
            "model.pt" in str(exc_info.value) or "empty" in str(exc_info.value).lower()
        )


class TestTrainingWorkerRestoreMethod:
    """Tests for TrainingWorker.restore_from_checkpoint method."""

    @pytest.fixture
    def mock_training_worker(self):
        """Create a mock TrainingWorker for testing."""
        from ktrdr.training.training_worker import TrainingWorker

        # Use patch to avoid actual initialization
        with patch.object(TrainingWorker, "__init__", lambda self: None):
            worker = TrainingWorker()
            worker._checkpoint_dir = "/tmp/checkpoints"
            worker.get_checkpoint_service = MagicMock()
            return worker

    @pytest.fixture
    def sample_checkpoint_data(self):
        """Create sample checkpoint data."""
        from ktrdr.checkpoint.checkpoint_service import CheckpointData

        # Create real PyTorch state dicts for testing
        model = nn.Linear(10, 2)
        optimizer = optim.Adam(model.parameters(), lr=0.001)

        model_buffer = io.BytesIO()
        torch.save(model.state_dict(), model_buffer)

        optimizer_buffer = io.BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        return CheckpointData(
            operation_id="op_123",
            checkpoint_type="cancellation",
            created_at=datetime.now(),
            state={
                "epoch": 24,
                "train_loss": 0.3,
                "val_loss": 0.25,
                "training_history": {"train_loss": [1.0, 0.5, 0.3]},
                "original_request": {"symbol": "EURUSD"},
            },
            artifacts_path="/checkpoints/op_123",
            artifacts={
                "model.pt": model_buffer.getvalue(),
                "optimizer.pt": optimizer_buffer.getvalue(),
            },
        )

    @pytest.mark.asyncio
    async def test_worker_has_restore_method(self, mock_training_worker):
        """TrainingWorker should have restore_from_checkpoint method."""
        assert hasattr(mock_training_worker, "restore_from_checkpoint")
        assert callable(mock_training_worker.restore_from_checkpoint)

    @pytest.mark.asyncio
    async def test_restore_uses_checkpoint_service(
        self, mock_training_worker, sample_checkpoint_data
    ):
        """Worker restore should use CheckpointService."""
        mock_service = AsyncMock()
        mock_service.load_checkpoint.return_value = sample_checkpoint_data
        mock_training_worker.get_checkpoint_service.return_value = mock_service

        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        context = await mock_training_worker.restore_from_checkpoint("op_123")

        mock_service.load_checkpoint.assert_called_once()
        assert isinstance(context, TrainingResumeContext)

    @pytest.mark.asyncio
    async def test_restore_returns_resume_context(
        self, mock_training_worker, sample_checkpoint_data
    ):
        """Worker restore should return TrainingResumeContext."""
        mock_service = AsyncMock()
        mock_service.load_checkpoint.return_value = sample_checkpoint_data
        mock_training_worker.get_checkpoint_service.return_value = mock_service

        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        context = await mock_training_worker.restore_from_checkpoint("op_123")

        assert isinstance(context, TrainingResumeContext)
        # Resume from next epoch after checkpoint
        assert context.start_epoch == 25
        assert context.original_request == {"symbol": "EURUSD"}
