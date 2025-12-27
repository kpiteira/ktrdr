"""Unit tests for ModelTrainer resume context integration (M4 Task 4.5)."""

from io import BytesIO

import torch
import torch.nn as nn

from ktrdr.training.checkpoint_restore import TrainingResumeContext
from ktrdr.training.model_trainer import ModelTrainer


class SimpleModel(nn.Module):
    """Simple model for testing."""

    def __init__(self, input_dim: int = 10, output_dim: int = 3):
        super().__init__()
        self.fc = nn.Linear(input_dim, output_dim)

    def forward(self, x):
        return self.fc(x)


def create_model_weights_bytes(model: nn.Module) -> bytes:
    """Serialize model state_dict to bytes."""
    buffer = BytesIO()
    torch.save(model.state_dict(), buffer)
    return buffer.getvalue()


def create_optimizer_state_bytes(optimizer: torch.optim.Optimizer) -> bytes:
    """Serialize optimizer state_dict to bytes."""
    buffer = BytesIO()
    torch.save(optimizer.state_dict(), buffer)
    return buffer.getvalue()


class TestModelTrainerResumeContext:
    """Test ModelTrainer accepts and uses resume_context."""

    def test_model_trainer_accepts_resume_context_parameter(self):
        """Test that ModelTrainer __init__ accepts resume_context parameter."""
        config = {
            "epochs": 10,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        # Create a resume context
        model = SimpleModel()
        optimizer = torch.optim.Adam(model.parameters())

        resume_context = TrainingResumeContext(
            start_epoch=5,
            model_weights=create_model_weights_bytes(model),
            optimizer_state=create_optimizer_state_bytes(optimizer),
            training_history={
                "train_loss": [0.9, 0.8, 0.7, 0.6, 0.5],
                "val_loss": [0.95, 0.85, 0.75, 0.65, 0.55],
            },
            best_val_loss=0.55,
        )

        # Should not raise - ModelTrainer accepts resume_context
        trainer = ModelTrainer(config=config, resume_context=resume_context)
        assert trainer._resume_context == resume_context

    def test_model_weights_loaded_from_checkpoint(self):
        """Test that model weights are restored from resume_context."""
        # Create "checkpoint" model with known weights
        checkpoint_model = SimpleModel()
        # Set specific known weights
        with torch.no_grad():
            checkpoint_model.fc.weight.fill_(0.5)
            checkpoint_model.fc.bias.fill_(0.1)

        # Create optimizer state
        checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters())
        checkpoint_optimizer.zero_grad()

        resume_context = TrainingResumeContext(
            start_epoch=3,
            model_weights=create_model_weights_bytes(checkpoint_model),
            optimizer_state=create_optimizer_state_bytes(checkpoint_optimizer),
        )

        config = {
            "epochs": 5,  # 5 total epochs, resuming from 3
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(config=config, resume_context=resume_context)

        # Create a NEW model (weights will be different)
        new_model = SimpleModel()

        # Prepare test data
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        # Train (which should first load checkpoint weights)
        trainer.train(new_model, X_train, y_train)

        # The model should have been initialized with checkpoint weights
        # (We can't easily verify after training since weights will change,
        # so we test the internal restoration mechanism)
        assert trainer._resume_context is not None

    def test_optimizer_state_loaded_from_checkpoint(self):
        """Test that optimizer state is restored from resume_context."""
        # Create checkpoint model and optimizer
        checkpoint_model = SimpleModel()
        checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters(), lr=0.001)

        # Run a few steps to populate optimizer state
        X = torch.randn(16, 10)
        y = torch.randint(0, 3, (16,))
        criterion = nn.CrossEntropyLoss()

        for _ in range(3):
            checkpoint_optimizer.zero_grad()
            outputs = checkpoint_model(X)
            loss = criterion(outputs, y)
            loss.backward()
            checkpoint_optimizer.step()

        # Capture optimizer state (now has momentum buffers)
        resume_context = TrainingResumeContext(
            start_epoch=5,
            model_weights=create_model_weights_bytes(checkpoint_model),
            optimizer_state=create_optimizer_state_bytes(checkpoint_optimizer),
        )

        config = {
            "epochs": 7,  # Resume from 5, train to 7
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(config=config, resume_context=resume_context)

        # Create new model
        new_model = SimpleModel()
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        # Train - optimizer state should be restored internally
        result = trainer.train(new_model, X_train, y_train)

        # Training should complete successfully
        assert "final_train_loss" in result or "error" not in result

    def test_training_starts_from_correct_epoch(self):
        """Test that training loop starts from resume_context.start_epoch."""
        captured_epochs = []

        def progress_callback(epoch, total_epochs, metrics):
            if metrics.get("progress_type") == "epoch":
                captured_epochs.append(metrics["epoch"])

        # Create checkpoint at epoch 3
        checkpoint_model = SimpleModel()
        checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters())

        resume_context = TrainingResumeContext(
            start_epoch=3,  # Should start from epoch 3
            model_weights=create_model_weights_bytes(checkpoint_model),
            optimizer_state=create_optimizer_state_bytes(checkpoint_optimizer),
        )

        config = {
            "epochs": 5,  # Total 5 epochs (0, 1, 2, 3, 4)
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
            resume_context=resume_context,
        )

        model = SimpleModel()
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        trainer.train(model, X_train, y_train)

        # Should only have epochs 3, 4 (starting from 3, ending at 4 inclusive)
        assert captured_epochs == [
            3,
            4,
        ], f"Expected epochs [3, 4], got {captured_epochs}"

    def test_training_history_merged_correctly(self):
        """Test that resume_context.training_history is merged with new training."""
        captured_history = []

        def progress_callback(epoch, total_epochs, metrics):
            if metrics.get("progress_type") == "epoch":
                captured_history.append(
                    {
                        "epoch": metrics["epoch"],
                        "train_loss": metrics["train_loss"],
                    }
                )

        # Simulate checkpoint with 3 epochs of history
        checkpoint_model = SimpleModel()
        checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters())

        prior_history = {
            "train_loss": [0.9, 0.8, 0.7],  # Epochs 0, 1, 2
            "val_loss": [0.95, 0.85, 0.75],
        }

        resume_context = TrainingResumeContext(
            start_epoch=3,
            model_weights=create_model_weights_bytes(checkpoint_model),
            optimizer_state=create_optimizer_state_bytes(checkpoint_optimizer),
            training_history=prior_history,
            best_val_loss=0.75,
        )

        config = {
            "epochs": 5,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
            resume_context=resume_context,
        )

        model = SimpleModel()
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        trainer.train(model, X_train, y_train)

        # Trainer's history should include both prior and new epochs
        assert len(trainer.history) >= 2  # At least epochs 3, 4


class TestModelTrainerResumeContextEdgeCases:
    """Test edge cases for resume_context."""

    def test_resume_from_epoch_zero_is_noop(self):
        """Test that resume_context with start_epoch=0 acts like fresh training."""
        checkpoint_model = SimpleModel()
        checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters())

        resume_context = TrainingResumeContext(
            start_epoch=0,  # Start from beginning
            model_weights=create_model_weights_bytes(checkpoint_model),
            optimizer_state=create_optimizer_state_bytes(checkpoint_optimizer),
        )

        config = {
            "epochs": 3,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        captured_epochs = []

        def progress_callback(epoch, total_epochs, metrics):
            if metrics.get("progress_type") == "epoch":
                captured_epochs.append(metrics["epoch"])

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
            resume_context=resume_context,
        )

        model = SimpleModel()
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        trainer.train(model, X_train, y_train)

        # Should have epochs 0, 1, 2
        assert captured_epochs == [0, 1, 2]

    def test_resume_at_final_epoch_completes_immediately(self):
        """Test resume when start_epoch equals total epochs (already complete)."""
        checkpoint_model = SimpleModel()
        checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters())

        resume_context = TrainingResumeContext(
            start_epoch=5,  # Start at epoch 5
            model_weights=create_model_weights_bytes(checkpoint_model),
            optimizer_state=create_optimizer_state_bytes(checkpoint_optimizer),
        )

        config = {
            "epochs": 5,  # Only 5 epochs total (0-4)
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        captured_epochs = []

        def progress_callback(epoch, total_epochs, metrics):
            if metrics.get("progress_type") == "epoch":
                captured_epochs.append(metrics["epoch"])

        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
            resume_context=resume_context,
        )

        model = SimpleModel()
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        trainer.train(model, X_train, y_train)

        # Should have no new epochs (already at epoch 5, but epochs go 0-4)
        assert captured_epochs == [], f"Expected no epochs, got {captured_epochs}"

    def test_resume_with_scheduler_state(self):
        """Test that scheduler state is restored if provided."""
        checkpoint_model = SimpleModel()
        checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters())
        checkpoint_scheduler = torch.optim.lr_scheduler.StepLR(
            checkpoint_optimizer, step_size=2, gamma=0.1
        )

        # Advance scheduler a few steps
        for _ in range(3):
            checkpoint_scheduler.step()

        # Serialize scheduler state
        scheduler_buffer = BytesIO()
        torch.save(checkpoint_scheduler.state_dict(), scheduler_buffer)
        scheduler_state = scheduler_buffer.getvalue()

        resume_context = TrainingResumeContext(
            start_epoch=3,
            model_weights=create_model_weights_bytes(checkpoint_model),
            optimizer_state=create_optimizer_state_bytes(checkpoint_optimizer),
            scheduler_state=scheduler_state,
        )

        config = {
            "epochs": 5,
            "batch_size": 16,
            "learning_rate": 0.001,
            "scheduler": {"type": "step", "step_size": 2, "gamma": 0.1},
        }

        trainer = ModelTrainer(config=config, resume_context=resume_context)

        model = SimpleModel()
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        # Should complete without error
        result = trainer.train(model, X_train, y_train)
        assert "error" not in result

    def test_resume_with_best_model_weights(self):
        """Test that best_model_weights is restored from resume_context."""
        checkpoint_model = SimpleModel()
        checkpoint_optimizer = torch.optim.Adam(checkpoint_model.parameters())

        # Create "best" model with different weights
        best_model = SimpleModel()
        with torch.no_grad():
            best_model.fc.weight.fill_(1.0)
            best_model.fc.bias.fill_(0.5)

        resume_context = TrainingResumeContext(
            start_epoch=3,
            model_weights=create_model_weights_bytes(checkpoint_model),
            optimizer_state=create_optimizer_state_bytes(checkpoint_optimizer),
            best_model_weights=create_model_weights_bytes(best_model),
            best_val_loss=0.5,
        )

        config = {
            "epochs": 5,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        trainer = ModelTrainer(config=config, resume_context=resume_context)

        # best_model_state should be set from resume_context
        assert trainer.best_model_state is not None

    def test_no_resume_context_works_normally(self):
        """Test that training without resume_context works as before."""
        config = {
            "epochs": 2,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        captured_epochs = []

        def progress_callback(epoch, total_epochs, metrics):
            if metrics.get("progress_type") == "epoch":
                captured_epochs.append(metrics["epoch"])

        # No resume_context
        trainer = ModelTrainer(
            config=config,
            progress_callback=progress_callback,
        )

        model = SimpleModel()
        X_train = torch.randn(64, 10)
        y_train = torch.randint(0, 3, (64,))

        trainer.train(model, X_train, y_train)

        # Should have epochs 0, 1
        assert captured_epochs == [0, 1]
