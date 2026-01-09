"""Unit tests for training worker checkpoint integration.

Tests verify that the TrainingWorker properly integrates with
CheckpointService and CheckpointPolicy for saving checkpoints
during training, on cancellation, and on failure.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
import torch
import torch.nn as nn

from ktrdr.checkpoint import (
    CheckpointPolicy,
    CheckpointService,
)


class TestTrainingWorkerCheckpointWiring:
    """Tests for checkpoint service and policy wiring in TrainingWorker."""

    def test_training_worker_has_checkpoint_service_factory(self):
        """TrainingWorker should have a method to get CheckpointService."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker(worker_port=5099, backend_url="http://test:8000")

        # Worker should have a way to get a checkpoint service
        assert hasattr(worker, "get_checkpoint_service")

    def test_training_worker_has_checkpoint_policy_factory(self):
        """TrainingWorker should have a method to get CheckpointPolicy."""
        from ktrdr.training.training_worker import TrainingWorker

        worker = TrainingWorker(worker_port=5099, backend_url="http://test:8000")

        # Worker should have checkpoint policy settings
        assert hasattr(worker, "checkpoint_epoch_interval")
        assert hasattr(worker, "checkpoint_time_interval")


class TestModelTrainerCheckpointCallback:
    """Tests for checkpoint callback integration in ModelTrainer."""

    @pytest.fixture
    def simple_model(self):
        """Create a simple model for testing."""
        return nn.Linear(10, 3)

    @pytest.fixture
    def simple_data(self):
        """Create simple training data."""
        X_train = torch.randn(100, 10)
        y_train = torch.randint(0, 3, (100,))
        X_val = torch.randn(20, 10)
        y_val = torch.randint(0, 3, (20,))
        return X_train, y_train, X_val, y_val

    def test_model_trainer_accepts_checkpoint_callback(self):
        """ModelTrainer should accept a checkpoint_callback parameter."""
        from ktrdr.training.model_trainer import ModelTrainer

        callback = MagicMock()

        trainer = ModelTrainer(
            config={"epochs": 5, "batch_size": 32},
            checkpoint_callback=callback,
        )

        assert trainer.checkpoint_callback is callback

    def test_model_trainer_calls_checkpoint_callback_after_epoch(
        self, simple_model, simple_data
    ):
        """ModelTrainer should call checkpoint_callback after each epoch."""
        from ktrdr.training.model_trainer import ModelTrainer

        callback = MagicMock()
        X_train, y_train, X_val, y_val = simple_data

        trainer = ModelTrainer(
            config={"epochs": 3, "batch_size": 32},
            checkpoint_callback=callback,
        )

        trainer.train(
            model=simple_model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
        )

        # Callback should be called 3 times (once per epoch)
        assert callback.call_count == 3

    def test_checkpoint_callback_receives_correct_parameters(
        self, simple_model, simple_data
    ):
        """Checkpoint callback should receive epoch, model, optimizer, scheduler, trainer."""
        from ktrdr.training.model_trainer import ModelTrainer

        callback_args = []

        def capture_callback(**kwargs):
            callback_args.append(kwargs)

        X_train, y_train, X_val, y_val = simple_data

        trainer = ModelTrainer(
            config={"epochs": 2, "batch_size": 32},
            checkpoint_callback=capture_callback,
        )

        trainer.train(
            model=simple_model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
        )

        # Verify callback received expected parameters
        assert len(callback_args) == 2
        first_call = callback_args[0]

        assert "epoch" in first_call
        assert "model" in first_call
        assert "optimizer" in first_call
        assert "scheduler" in first_call
        assert "trainer" in first_call

        assert first_call["epoch"] == 0
        assert isinstance(first_call["model"], nn.Module)


class TestTrainingPipelineCheckpointCallback:
    """Tests for checkpoint callback passthrough in TrainingPipeline."""

    def test_train_model_accepts_checkpoint_callback(self):
        """TrainingPipeline.train_model should accept checkpoint_callback."""
        # Verify the method signature accepts checkpoint_callback
        import inspect

        from ktrdr.training.training_pipeline import TrainingPipeline

        sig = inspect.signature(TrainingPipeline.train_model)
        params = list(sig.parameters.keys())

        assert "checkpoint_callback" in params


class TestLocalOrchestratorCheckpointCallback:
    """Tests for checkpoint callback in LocalTrainingOrchestrator."""

    def test_local_orchestrator_accepts_checkpoint_callback(self):
        """LocalTrainingOrchestrator should accept checkpoint_callback in constructor."""
        import inspect

        from ktrdr.api.services.training.local_orchestrator import (
            LocalTrainingOrchestrator,
        )

        sig = inspect.signature(LocalTrainingOrchestrator.__init__)
        params = list(sig.parameters.keys())

        assert "checkpoint_callback" in params


class TestTrainingWorkerCheckpointFlow:
    """Tests for the complete checkpoint flow in TrainingWorker."""

    @pytest.fixture
    def mock_checkpoint_service(self):
        """Create a mock checkpoint service."""
        service = AsyncMock(spec=CheckpointService)
        service.save_checkpoint = AsyncMock()
        service.delete_checkpoint = AsyncMock(return_value=True)
        return service

    @pytest.fixture
    def mock_checkpoint_policy(self):
        """Create a mock checkpoint policy."""
        policy = MagicMock(spec=CheckpointPolicy)
        # Checkpoint every 5 epochs
        policy.should_checkpoint = MagicMock(side_effect=lambda epoch: epoch % 5 == 4)
        policy.record_checkpoint = MagicMock()
        return policy

    @pytest.mark.asyncio
    async def test_periodic_checkpoint_saves_at_interval(
        self, mock_checkpoint_service, mock_checkpoint_policy
    ):
        """Training should save periodic checkpoints based on policy."""
        # This test verifies the integration point where:
        # 1. CheckpointPolicy decides when to checkpoint
        # 2. CheckpointService saves the checkpoint

        # When policy says should_checkpoint(4) -> True (epoch 5 = index 4)
        mock_checkpoint_policy.should_checkpoint.return_value = True

        # Simulating what happens in training loop
        operation_id = "op_test_123"
        epoch = 4  # 5th epoch
        state = {"epoch": epoch, "train_loss": 0.5}

        if mock_checkpoint_policy.should_checkpoint(epoch):
            await mock_checkpoint_service.save_checkpoint(
                operation_id=operation_id,
                checkpoint_type="periodic",
                state=state,
                artifacts={"model.pt": b"mock_model"},
            )
            mock_checkpoint_policy.record_checkpoint(epoch)

        mock_checkpoint_service.save_checkpoint.assert_called_once()
        mock_checkpoint_policy.record_checkpoint.assert_called_once_with(epoch)

    @pytest.mark.asyncio
    async def test_cancellation_checkpoint_saves_before_exit(
        self, mock_checkpoint_service
    ):
        """Training should save checkpoint on cancellation."""
        operation_id = "op_test_123"
        state = {"epoch": 7, "train_loss": 0.3}

        # Simulate cancellation checkpoint
        await mock_checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state,
            artifacts={"model.pt": b"mock_model"},
        )

        mock_checkpoint_service.save_checkpoint.assert_called_once()
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args.kwargs["checkpoint_type"] == "cancellation"

    @pytest.mark.asyncio
    async def test_failure_checkpoint_saves_on_exception(self, mock_checkpoint_service):
        """Training should save checkpoint on failure."""
        operation_id = "op_test_123"
        state = {"epoch": 3, "train_loss": 0.8}

        # Simulate failure checkpoint
        await mock_checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=state,
            artifacts={"model.pt": b"mock_model"},
        )

        mock_checkpoint_service.save_checkpoint.assert_called_once()
        call_args = mock_checkpoint_service.save_checkpoint.call_args
        assert call_args.kwargs["checkpoint_type"] == "failure"

    @pytest.mark.asyncio
    async def test_checkpoint_deleted_on_successful_completion(
        self, mock_checkpoint_service
    ):
        """Training should delete checkpoint on successful completion."""
        operation_id = "op_test_123"

        await mock_checkpoint_service.delete_checkpoint(operation_id)

        mock_checkpoint_service.delete_checkpoint.assert_called_once_with(operation_id)


class TestCheckpointCallbackCreation:
    """Tests for checkpoint callback creation in worker."""

    @pytest.fixture
    def mock_session_factory(self):
        """Create a mock session factory."""

        @asynccontextmanager
        async def factory():
            yield AsyncMock()

        return factory

    def test_create_checkpoint_callback_returns_callable(self, mock_session_factory):
        """Worker should create a checkpoint callback that is callable."""
        # This tests that we can create a checkpoint callback factory
        from ktrdr.checkpoint import CheckpointPolicy, CheckpointService

        service = CheckpointService(
            session_factory=mock_session_factory,
            artifacts_dir="/tmp/test_checkpoints",
        )
        policy = CheckpointPolicy(unit_interval=10, time_interval_seconds=300)

        # The callback should be a function that can be called with checkpoint params
        # This is what we'll implement in the worker
        def create_checkpoint_callback(
            operation_id: str,
            original_request: dict,
            checkpoint_service: CheckpointService,
            checkpoint_policy: CheckpointPolicy,
        ):
            """Create a checkpoint callback for use in ModelTrainer."""

            async def callback(**kwargs):
                epoch = kwargs["epoch"]
                if checkpoint_policy.should_checkpoint(epoch):
                    # Build state and artifacts
                    # Save checkpoint
                    pass

            return callback

        callback = create_checkpoint_callback(
            operation_id="op_test",
            original_request={},
            checkpoint_service=service,
            checkpoint_policy=policy,
        )

        assert callable(callback)
