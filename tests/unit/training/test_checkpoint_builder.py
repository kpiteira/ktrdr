"""Unit tests for training checkpoint builder."""

import io
from unittest.mock import MagicMock

import pytest
import torch
import torch.nn as nn
import torch.optim as optim

from ktrdr.checkpoint.schemas import TrainingCheckpointState
from ktrdr.training.checkpoint_builder import (
    ArtifactValidationError,
    build_training_checkpoint_artifacts,
    build_training_checkpoint_state,
    validate_artifacts,
)
from ktrdr.training.model_trainer import TrainingMetrics


class TestBuildTrainingCheckpointState:
    """Tests for build_training_checkpoint_state function."""

    @pytest.fixture
    def mock_trainer(self):
        """Create a mock trainer with history."""
        trainer = MagicMock()
        trainer.history = [
            TrainingMetrics(
                epoch=0,
                train_loss=1.0,
                train_accuracy=0.5,
                val_loss=0.9,
                val_accuracy=0.55,
                learning_rate=0.001,
                duration=10.0,
            ),
            TrainingMetrics(
                epoch=1,
                train_loss=0.8,
                train_accuracy=0.6,
                val_loss=0.75,
                val_accuracy=0.62,
                learning_rate=0.001,
                duration=10.0,
            ),
            TrainingMetrics(
                epoch=2,
                train_loss=0.6,
                train_accuracy=0.7,
                val_loss=0.55,
                val_accuracy=0.68,
                learning_rate=0.0005,
                duration=10.0,
            ),
        ]
        trainer.best_val_accuracy = 0.68
        trainer.config = {"epochs": 100, "batch_size": 32}
        return trainer

    def test_extracts_current_epoch(self, mock_trainer):
        """Should extract current epoch from parameter."""
        state = build_training_checkpoint_state(
            trainer=mock_trainer,
            current_epoch=2,
        )

        assert state.epoch == 2

    def test_extracts_latest_metrics(self, mock_trainer):
        """Should extract latest train/val loss and accuracy."""
        state = build_training_checkpoint_state(
            trainer=mock_trainer,
            current_epoch=2,
        )

        assert state.train_loss == 0.6
        assert state.val_loss == 0.55
        assert state.train_accuracy == 0.7
        assert state.val_accuracy == 0.68

    def test_extracts_learning_rate(self, mock_trainer):
        """Should extract current learning rate."""
        state = build_training_checkpoint_state(
            trainer=mock_trainer,
            current_epoch=2,
        )

        assert state.learning_rate == 0.0005

    def test_extracts_best_val_loss(self, mock_trainer):
        """Should track best validation loss."""
        state = build_training_checkpoint_state(
            trainer=mock_trainer,
            current_epoch=2,
        )

        # Best val_loss is 0.55 at epoch 2
        assert state.best_val_loss == 0.55

    def test_extracts_training_history(self, mock_trainer):
        """Should extract training history for plotting."""
        state = build_training_checkpoint_state(
            trainer=mock_trainer,
            current_epoch=2,
        )

        assert "train_loss" in state.training_history
        assert "val_loss" in state.training_history
        assert state.training_history["train_loss"] == [1.0, 0.8, 0.6]
        assert state.training_history["val_loss"] == [0.9, 0.75, 0.55]

    def test_includes_original_request(self, mock_trainer):
        """Should include original request for resume."""
        original_request = {"symbol": "BTCUSD", "epochs": 100}

        state = build_training_checkpoint_state(
            trainer=mock_trainer,
            current_epoch=2,
            original_request=original_request,
        )

        assert state.original_request == original_request

    def test_handles_no_validation_metrics(self):
        """Should handle trainer with no validation metrics."""
        trainer = MagicMock()
        trainer.history = [
            TrainingMetrics(
                epoch=0,
                train_loss=1.0,
                train_accuracy=0.5,
                val_loss=None,
                val_accuracy=None,
                learning_rate=0.001,
                duration=10.0,
            ),
        ]
        trainer.best_val_accuracy = 0.0

        state = build_training_checkpoint_state(trainer=trainer, current_epoch=0)

        assert state.train_loss == 1.0
        # When no validation, val_loss defaults to inf
        assert state.val_loss == float("inf")
        assert state.val_accuracy is None

    def test_returns_dataclass(self, mock_trainer):
        """Should return TrainingCheckpointState instance."""
        state = build_training_checkpoint_state(
            trainer=mock_trainer,
            current_epoch=2,
        )

        assert isinstance(state, TrainingCheckpointState)


class TestBuildTrainingCheckpointArtifacts:
    """Tests for build_training_checkpoint_artifacts function."""

    @pytest.fixture
    def simple_model(self):
        """Create a simple model for testing."""
        return nn.Linear(10, 2)

    @pytest.fixture
    def optimizer(self, simple_model):
        """Create an optimizer for the model."""
        return optim.Adam(simple_model.parameters(), lr=0.001)

    @pytest.fixture
    def scheduler(self, optimizer):
        """Create a scheduler for the optimizer."""
        return optim.lr_scheduler.StepLR(optimizer, step_size=10)

    def test_returns_model_artifact(self, simple_model, optimizer):
        """Should return model.pt artifact."""
        artifacts = build_training_checkpoint_artifacts(
            model=simple_model,
            optimizer=optimizer,
        )

        assert "model.pt" in artifacts
        assert isinstance(artifacts["model.pt"], bytes)
        assert len(artifacts["model.pt"]) > 0

    def test_returns_optimizer_artifact(self, simple_model, optimizer):
        """Should return optimizer.pt artifact."""
        artifacts = build_training_checkpoint_artifacts(
            model=simple_model,
            optimizer=optimizer,
        )

        assert "optimizer.pt" in artifacts
        assert isinstance(artifacts["optimizer.pt"], bytes)
        assert len(artifacts["optimizer.pt"]) > 0

    def test_returns_scheduler_artifact_when_provided(
        self, simple_model, optimizer, scheduler
    ):
        """Should return scheduler.pt artifact when scheduler provided."""
        artifacts = build_training_checkpoint_artifacts(
            model=simple_model,
            optimizer=optimizer,
            scheduler=scheduler,
        )

        assert "scheduler.pt" in artifacts
        assert isinstance(artifacts["scheduler.pt"], bytes)

    def test_omits_scheduler_when_not_provided(self, simple_model, optimizer):
        """Should omit scheduler.pt when no scheduler."""
        artifacts = build_training_checkpoint_artifacts(
            model=simple_model,
            optimizer=optimizer,
            scheduler=None,
        )

        assert "scheduler.pt" not in artifacts

    def test_returns_best_model_when_provided(self, simple_model, optimizer):
        """Should return best_model.pt when best_model_state provided."""
        best_state = simple_model.state_dict()

        artifacts = build_training_checkpoint_artifacts(
            model=simple_model,
            optimizer=optimizer,
            best_model_state=best_state,
        )

        assert "best_model.pt" in artifacts
        assert isinstance(artifacts["best_model.pt"], bytes)

    def test_omits_best_model_when_not_provided(self, simple_model, optimizer):
        """Should omit best_model.pt when no best_model_state."""
        artifacts = build_training_checkpoint_artifacts(
            model=simple_model,
            optimizer=optimizer,
            best_model_state=None,
        )

        assert "best_model.pt" not in artifacts

    def test_artifacts_are_loadable(self, simple_model, optimizer, scheduler):
        """Artifacts should be loadable by torch.load."""
        best_state = simple_model.state_dict()

        artifacts = build_training_checkpoint_artifacts(
            model=simple_model,
            optimizer=optimizer,
            scheduler=scheduler,
            best_model_state=best_state,
        )

        # Verify each can be loaded
        model_state = torch.load(io.BytesIO(artifacts["model.pt"]), weights_only=True)
        assert (
            "weight" in model_state
            or "0.weight" in model_state
            or any("weight" in k for k in model_state.keys())
        )

        optimizer_state = torch.load(
            io.BytesIO(artifacts["optimizer.pt"]), weights_only=False
        )
        assert "state" in optimizer_state or "param_groups" in optimizer_state

        scheduler_state = torch.load(
            io.BytesIO(artifacts["scheduler.pt"]), weights_only=False
        )
        assert isinstance(scheduler_state, dict)

        best_model = torch.load(
            io.BytesIO(artifacts["best_model.pt"]), weights_only=True
        )
        assert (
            "weight" in best_model
            or "0.weight" in best_model
            or any("weight" in k for k in best_model.keys())
        )


class TestValidateArtifacts:
    """Tests for validate_artifacts function."""

    def test_valid_artifacts_with_required_only(self):
        """Should pass with only required artifacts."""
        artifacts = {
            "model.pt": b"model data",
            "optimizer.pt": b"optimizer data",
        }

        # Should not raise
        validate_artifacts(artifacts)

    def test_valid_artifacts_with_all(self):
        """Should pass with all artifacts."""
        artifacts = {
            "model.pt": b"model data",
            "optimizer.pt": b"optimizer data",
            "scheduler.pt": b"scheduler data",
            "best_model.pt": b"best model data",
        }

        # Should not raise
        validate_artifacts(artifacts)

    def test_raises_on_missing_model(self):
        """Should raise when model.pt is missing."""
        artifacts = {
            "optimizer.pt": b"optimizer data",
        }

        with pytest.raises(ArtifactValidationError) as exc_info:
            validate_artifacts(artifacts)

        assert "model.pt" in str(exc_info.value)

    def test_raises_on_missing_optimizer(self):
        """Should raise when optimizer.pt is missing."""
        artifacts = {
            "model.pt": b"model data",
        }

        with pytest.raises(ArtifactValidationError) as exc_info:
            validate_artifacts(artifacts)

        assert "optimizer.pt" in str(exc_info.value)

    def test_raises_on_empty_required_artifact(self):
        """Should raise when required artifact is empty bytes."""
        artifacts = {
            "model.pt": b"",  # Empty
            "optimizer.pt": b"optimizer data",
        }

        with pytest.raises(ArtifactValidationError) as exc_info:
            validate_artifacts(artifacts)

        assert "model.pt" in str(exc_info.value)

    def test_allows_missing_optional_artifacts(self):
        """Should allow missing optional artifacts."""
        artifacts = {
            "model.pt": b"model data",
            "optimizer.pt": b"optimizer data",
            # scheduler.pt and best_model.pt are optional
        }

        # Should not raise
        validate_artifacts(artifacts)

    def test_allows_unknown_artifacts(self):
        """Should allow additional unknown artifacts."""
        artifacts = {
            "model.pt": b"model data",
            "optimizer.pt": b"optimizer data",
            "custom.pt": b"custom data",  # Unknown but allowed
        }

        # Should not raise
        validate_artifacts(artifacts)
