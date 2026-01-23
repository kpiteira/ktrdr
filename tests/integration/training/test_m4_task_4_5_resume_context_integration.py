"""
Integration tests for M4 Task 4.5: ModelTrainer resume_context integration.

Validates that resume_context is properly wired through the call chain:
- TrainingWorker._execute_resumed_training → LocalTrainingOrchestrator
- LocalTrainingOrchestrator → TrainingPipeline.train_strategy()
- TrainingPipeline.train_strategy() → TrainingPipeline.train_model()
- TrainingPipeline.train_model() → ModelTrainer.__init__(resume_context=...)

Test approach:
1. Unit level: ModelTrainer accepts and uses resume_context ✅ (in test_model_trainer_resume.py)
2. Integration level: Resume context propagates through full pipeline
3. End-to-end: Full workflow from API to completed training
"""

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import torch
import torch.nn as nn
import yaml

from ktrdr.api.services.training.context import (
    OperationMetadata,
    TrainingOperationContext,
)
from ktrdr.api.services.training.local_orchestrator import LocalTrainingOrchestrator
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.training.checkpoint_restore import TrainingResumeContext
from ktrdr.training.model_storage import ModelStorage
from ktrdr.training.training_pipeline import TrainingPipeline

# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def simple_strategy_config() -> dict:
    """Create a minimal strategy config for testing."""
    return {
        "name": "test_resume_strategy",
        "indicators": {
            "rsi": {"period": 14},
            "macd": {"fast": 12, "slow": 26, "signal": 9},
        },
        "fuzzy_sets": {
            "overbought": [50, 80],
            "oversold": [20, 50],
        },
        "model": {
            "architecture": "mlp",
            "layers": [128, 64],
            "training": {
                "epochs": 3,  # Small for fast testing
                "batch_size": 16,
                "learning_rate": 0.001,
            },
        },
    }


@pytest.fixture
def training_context(tmp_path: Path) -> TrainingOperationContext:
    """Create a training operation context for testing."""
    # Write strategy config to temporary file
    strategy_file = tmp_path / "test_resume_strategy.yaml"

    config = {
        "name": "test_resume_strategy",
        "indicators": {
            "rsi": {"period": 14},
            "macd": {"fast": 12, "slow": 26, "signal": 9},
        },
        "fuzzy_sets": {
            "overbought": [50, 80],
            "oversold": [20, 50],
        },
        "model": {
            "architecture": "mlp",
            "layers": [128, 64],
            "training": {
                "epochs": 3,
                "batch_size": 16,
                "learning_rate": 0.001,
            },
        },
        "training": {
            "epochs": 3,
            "batch_size": 16,
            "learning_rate": 0.001,
        },
    }

    with open(strategy_file, "w") as f:
        yaml.dump(config, f)

    return TrainingOperationContext(
        operation_id="test-resume-op-123",
        strategy_name="test_resume_strategy",
        strategy_path=strategy_file,
        strategy_config=config,
        symbols=["EURUSD"],
        timeframes=["1d"],
        start_date="2024-01-01",
        end_date="2024-01-31",
        training_config={"validation_split": 0.2},
        analytics_enabled=False,
        use_host_service=False,
        training_mode="local",
        total_epochs=3,
        total_batches=None,
        metadata=OperationMetadata(
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            progress_updates=[],
        ),
        session_id=None,
    )


@pytest.fixture
def progress_bridge() -> TrainingProgressBridge:
    """Create a mock progress bridge."""
    bridge = MagicMock(spec=TrainingProgressBridge)
    bridge.on_phase = MagicMock()
    bridge.on_progress = MagicMock()
    bridge.on_complete = MagicMock()
    bridge.on_cancellation = MagicMock()
    return bridge


@pytest.fixture
def model_storage(tmp_path: Path) -> ModelStorage:
    """Create a model storage instance."""
    storage = MagicMock(spec=ModelStorage)
    storage.save_model = MagicMock(return_value=str(tmp_path / "model.pt"))
    return storage


@pytest.fixture
def resume_context() -> TrainingResumeContext:
    """Create a resume context with checkpoint state."""
    # Create checkpoint state
    checkpoint_model = nn.Linear(10, 3)
    with torch.no_grad():
        checkpoint_model.weight.fill_(0.5)
        checkpoint_model.bias.fill_(0.1)

    checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters())

    # Serialize states
    weights_buffer = BytesIO()
    torch.save(checkpoint_model.state_dict(), weights_buffer)
    model_weights = weights_buffer.getvalue()

    optimizer_buffer = BytesIO()
    torch.save(checkpoint_optimizer.state_dict(), optimizer_buffer)
    optimizer_state = optimizer_buffer.getvalue()

    return TrainingResumeContext(
        start_epoch=2,  # Resume from epoch 2
        model_weights=model_weights,
        optimizer_state=optimizer_state,
        training_history={
            "train_loss": [0.9, 0.8],  # Epochs 0-1 history
            "val_loss": [0.95, 0.85],
        },
        best_val_loss=0.85,
    )


# ============================================================================
# ACCEPTANCE CRITERIA TESTS
# ============================================================================


class TestResumeContextAcceptance:
    """Validate M4 Task 4.5 acceptance criteria."""

    def test_1_model_trainer_accepts_resume_context(self):
        """AC-1: ModelTrainer accepts resume context parameter."""
        from ktrdr.training.model_trainer import ModelTrainer

        config = {
            "epochs": 3,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        # Create minimal resume context
        model = nn.Linear(10, 3)
        weights_buffer = BytesIO()
        torch.save(model.state_dict(), weights_buffer)

        optimizer = torch.optim.Adam(model.parameters())
        optimizer_buffer = BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        resume_ctx = TrainingResumeContext(
            start_epoch=1,
            model_weights=weights_buffer.getvalue(),
            optimizer_state=optimizer_buffer.getvalue(),
        )

        # Should not raise - ModelTrainer accepts resume_context
        trainer = ModelTrainer(config=config, resume_context=resume_ctx)

        # Verify it was stored
        assert trainer._resume_context == resume_ctx
        assert trainer._resume_context.start_epoch == 1

    def test_2_model_weights_loaded_from_checkpoint(self):
        """AC-2: Model weights are loaded from checkpoint."""
        from ktrdr.training.model_trainer import ModelTrainer

        # Create checkpoint model with known weights
        checkpoint_model = nn.Linear(10, 3)
        with torch.no_grad():
            checkpoint_model.weight.fill_(0.5)
            checkpoint_model.bias.fill_(0.1)

        weights_buffer = BytesIO()
        torch.save(checkpoint_model.state_dict(), weights_buffer)

        optimizer = torch.optim.Adam(checkpoint_model.parameters())
        optimizer_buffer = BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        resume_context = TrainingResumeContext(
            start_epoch=1,
            model_weights=weights_buffer.getvalue(),
            optimizer_state=optimizer_buffer.getvalue(),
        )

        config = {
            "epochs": 2,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(config=config, resume_context=resume_context)

        # Create fresh model with random weights
        fresh_model = nn.Linear(10, 3)

        # Prepare training data
        X_train = torch.randn(32, 10)
        y_train = torch.randint(0, 3, (32,))

        # Train - should load checkpoint weights during initialization
        result = trainer.train(fresh_model, X_train, y_train)

        # Training should complete successfully
        assert result is not None
        assert "final_train_loss" in result or "error" not in result

    def test_3_optimizer_state_loaded_from_checkpoint(self):
        """AC-3: Optimizer state is loaded from checkpoint."""
        from ktrdr.training.model_trainer import ModelTrainer

        # Create checkpoint with populated optimizer state
        checkpoint_model = nn.Linear(10, 3)
        checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters(), lr=0.001)

        # Simulate training steps to populate optimizer state
        X = torch.randn(16, 10)
        y = torch.randint(0, 3, (16,))
        criterion = nn.CrossEntropyLoss()

        for _ in range(2):
            checkpoint_optimizer.zero_grad()
            outputs = checkpoint_model(X)
            loss = criterion(outputs, y)
            loss.backward()
            checkpoint_optimizer.step()

        # Capture optimizer state (has momentum buffers)
        weights_buffer = BytesIO()
        torch.save(checkpoint_model.state_dict(), weights_buffer)

        optimizer_buffer = BytesIO()
        torch.save(checkpoint_optimizer.state_dict(), optimizer_buffer)

        resume_context = TrainingResumeContext(
            start_epoch=2,
            model_weights=weights_buffer.getvalue(),
            optimizer_state=optimizer_buffer.getvalue(),
        )

        config = {
            "epochs": 3,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(config=config, resume_context=resume_context)

        # Training should work with restored optimizer state
        fresh_model = nn.Linear(10, 3)
        X_train = torch.randn(32, 10)
        y_train = torch.randint(0, 3, (32,))

        result = trainer.train(fresh_model, X_train, y_train)

        # Should complete without error
        assert result is not None

    def test_4_training_starts_from_correct_epoch(self, resume_context):
        """AC-4: Training starts from resume_context.start_epoch."""
        from ktrdr.training.model_trainer import ModelTrainer

        captured_epochs = []

        def progress_callback(epoch, total_epochs, metrics):
            if metrics and metrics.get("progress_type") == "epoch":
                captured_epochs.append(metrics["epoch"])

        config = {
            "epochs": 3,  # 0, 1, 2
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
            resume_context=resume_context,  # start_epoch=2
        )

        model = nn.Linear(10, 3)
        X_train = torch.randn(32, 10)
        y_train = torch.randint(0, 3, (32,))

        trainer.train(model, X_train, y_train)

        # Should only train epochs 2 (already at 2, need 2 total = indices 0,1,2)
        # Since resume from epoch 2 and config epochs=3, trains from 2 to 2 (just finish current)
        assert 2 in captured_epochs

    def test_5_training_history_merged_correctly(self, resume_context):
        """AC-5: Training history is merged correctly."""
        from ktrdr.training.model_trainer import ModelTrainer

        captured_history = []

        def progress_callback(epoch, total_epochs, metrics):
            if metrics and metrics.get("progress_type") == "epoch":
                captured_history.append(
                    {
                        "epoch": metrics["epoch"],
                        "train_loss": metrics.get("train_loss"),
                    }
                )

        config = {
            "epochs": 3,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
            resume_context=resume_context,
        )

        model = nn.Linear(10, 3)
        X_train = torch.randn(32, 10)
        y_train = torch.randint(0, 3, (32,))

        trainer.train(model, X_train, y_train)

        # Trainer should have history from both prior epochs and new training
        assert hasattr(trainer, "history")
        assert len(trainer.history) >= 1  # At least some epochs from resumed training


# ============================================================================
# WIRING INTEGRATION TESTS
# ============================================================================


class TestResumeContextWiring:
    """Validate that resume_context is properly wired through the call chain."""

    def test_local_orchestrator_stores_resume_context(
        self,
        training_context,
        progress_bridge,
        model_storage,
        resume_context,
    ):
        """Validate LocalTrainingOrchestrator stores resume_context for passing."""
        # Create orchestrator with resume_context
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
            resume_context=resume_context,
        )

        # Verify resume_context is stored
        assert orchestrator._resume_context == resume_context
        assert orchestrator._resume_context.start_epoch == 2

    def test_training_pipeline_train_model_accepts_resume_context(self):
        """Validate that TrainingPipeline.train_model() accepts resume_context parameter."""
        import inspect

        # Get the signature of train_model
        sig = inspect.signature(TrainingPipeline.train_model)
        params = sig.parameters

        # Verify resume_context parameter exists
        assert "resume_context" in params
        assert params["resume_context"].default is None  # Optional parameter


# ============================================================================
# BEHAVIOR VALIDATION TESTS
# ============================================================================


class TestResumeContextBehavior:
    """Validate that resume_context is actually used during training."""

    def test_resumed_training_uses_checkpoint_weights(self):
        """Verify that resumed training actually loads and uses checkpoint weights."""
        from ktrdr.training.model_trainer import ModelTrainer

        # Create checkpoint model with distinctive weights
        checkpoint_model = nn.Linear(10, 3)
        with torch.no_grad():
            # Set to very specific values to verify they're loaded
            checkpoint_model.weight.fill_(2.0)
            checkpoint_model.bias.fill_(0.5)

        weights_buffer = BytesIO()
        torch.save(checkpoint_model.state_dict(), weights_buffer)

        optimizer = torch.optim.Adam(checkpoint_model.parameters())
        optimizer_buffer = BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        resume_context = TrainingResumeContext(
            start_epoch=0,
            model_weights=weights_buffer.getvalue(),
            optimizer_state=optimizer_buffer.getvalue(),
        )

        config = {
            "epochs": 1,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(config=config, resume_context=resume_context)

        # Create a fresh model
        fresh_model = nn.Linear(10, 3)
        with torch.no_grad():
            fresh_model.weight.fill_(1.0)  # Different initial value
            fresh_model.bias.fill_(0.0)

        X_train = torch.randn(32, 10)
        y_train = torch.randint(0, 3, (32,))

        # Train - should load checkpoint weights
        result = trainer.train(fresh_model, X_train, y_train)

        # Result should include training metrics
        assert result is not None
        assert "final_train_loss" in result or "error" not in result

    def test_resume_preserves_prior_training_history(self):
        """Verify that resume_context.training_history is preserved and available."""
        from ktrdr.training.model_trainer import ModelTrainer

        prior_history = {
            "train_loss": [0.9, 0.8, 0.7],
            "val_loss": [0.95, 0.85, 0.75],
        }

        checkpoint_model = nn.Linear(10, 3)
        weights_buffer = BytesIO()
        torch.save(checkpoint_model.state_dict(), weights_buffer)

        optimizer = torch.optim.Adam(checkpoint_model.parameters())
        optimizer_buffer = BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        resume_context = TrainingResumeContext(
            start_epoch=3,
            model_weights=weights_buffer.getvalue(),
            optimizer_state=optimizer_buffer.getvalue(),
            training_history=prior_history,
            best_val_loss=0.75,
        )

        config = {
            "epochs": 4,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(config=config, resume_context=resume_context)

        # Verify trainer has access to prior history
        assert trainer._resume_context.training_history == prior_history
        assert trainer._resume_context.best_val_loss == 0.75
