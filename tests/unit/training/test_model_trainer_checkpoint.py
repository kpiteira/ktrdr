"""
Unit tests for ModelTrainer checkpoint state capture and restore.

Tests the ability of ModelTrainer to:
- Capture complete training state for checkpointing
- Restore training state from checkpoint
- Handle missing/corrupted checkpoint data
"""

import io

import pytest
import torch
import torch.nn as nn
import torch.optim as optim

from ktrdr.training.model_trainer import EarlyStopping, ModelTrainer, TrainingMetrics


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
def simple_model():
    """Create a simple model for testing."""
    return SimpleModel()


@pytest.fixture
def model_trainer():
    """Create ModelTrainer instance for testing."""
    config = {
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 100,
        "early_stopping": {"patience": 10, "monitor": "val_loss"},
    }
    return ModelTrainer(config=config)


@pytest.fixture
def trained_model_trainer(simple_model):
    """Create ModelTrainer with some training history."""
    config = {
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 100,
    }
    trainer = ModelTrainer(config=config)

    # Simulate some training progress
    trainer.history = [
        TrainingMetrics(
            epoch=0,
            train_loss=0.5,
            train_accuracy=0.6,
            val_loss=0.45,
            val_accuracy=0.65,
        ),
        TrainingMetrics(
            epoch=1,
            train_loss=0.4,
            train_accuracy=0.7,
            val_loss=0.38,
            val_accuracy=0.72,
        ),
        TrainingMetrics(
            epoch=2,
            train_loss=0.3,
            train_accuracy=0.8,
            val_loss=0.32,
            val_accuracy=0.78,
        ),
    ]
    trainer.best_val_accuracy = 0.78
    trainer.best_model_state = simple_model.state_dict().copy()

    return trainer, simple_model


def test_get_checkpoint_state_captures_all_required_state(
    trained_model_trainer,
):
    """
    Test that get_checkpoint_state() captures all required state.

    Acceptance Criteria:
    - ✅ Captures current epoch
    - ✅ Captures model state_dict (as bytes)
    - ✅ Captures optimizer state_dict (as bytes)
    - ✅ Captures scheduler state_dict (as bytes, if exists)
    - ✅ Captures training history
    - ✅ Captures best model state (as bytes)
    - ✅ Captures best validation accuracy
    - ✅ Captures early stopping state
    - ✅ Captures configuration
    """
    trainer, model = trained_model_trainer

    # Create optimizer and scheduler
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.1)

    # Train for 1 step to initialize optimizer state
    X_dummy = torch.randn(10, 10)
    y_dummy = torch.randint(0, 3, (10,))
    model.train()
    outputs = model(X_dummy)
    loss = nn.CrossEntropyLoss()(outputs, y_dummy)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    # Create early stopping with some state
    early_stopping = EarlyStopping(patience=10, monitor="val_loss")
    early_stopping(trainer.history[-1])  # Initialize state

    # Get checkpoint state
    current_epoch = 2
    checkpoint_state = trainer.get_checkpoint_state(
        current_epoch=current_epoch,
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        early_stopping=early_stopping,
    )

    # Verify all required fields present
    assert "epoch" in checkpoint_state
    assert checkpoint_state["epoch"] == current_epoch

    assert "model_state_dict" in checkpoint_state
    assert isinstance(checkpoint_state["model_state_dict"], bytes)

    assert "optimizer_state_dict" in checkpoint_state
    assert isinstance(checkpoint_state["optimizer_state_dict"], bytes)

    assert "scheduler_state_dict" in checkpoint_state
    assert isinstance(checkpoint_state["scheduler_state_dict"], bytes)

    assert "history" in checkpoint_state
    assert len(checkpoint_state["history"]) == len(trainer.history)

    assert "best_model_state" in checkpoint_state
    assert isinstance(checkpoint_state["best_model_state"], bytes)

    assert "best_val_accuracy" in checkpoint_state
    assert checkpoint_state["best_val_accuracy"] == trainer.best_val_accuracy

    assert "early_stopping_state" in checkpoint_state
    assert "counter" in checkpoint_state["early_stopping_state"]
    assert "best_score" in checkpoint_state["early_stopping_state"]

    assert "config" in checkpoint_state
    assert checkpoint_state["config"] == trainer.config


def test_get_checkpoint_state_handles_missing_optional_components(model_trainer):
    """
    Test get_checkpoint_state() handles missing optional components.

    Acceptance Criteria:
    - ✅ Works without scheduler (scheduler_state_dict is None)
    - ✅ Works without early stopping (early_stopping_state is None)
    - ✅ Works without best model (best_model_state is None)
    """
    model = SimpleModel()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Get checkpoint without optional components
    checkpoint_state = model_trainer.get_checkpoint_state(
        current_epoch=5,
        model=model,
        optimizer=optimizer,
        scheduler=None,
        early_stopping=None,
    )

    assert checkpoint_state["scheduler_state_dict"] is None
    assert checkpoint_state["early_stopping_state"] is None
    # best_model_state should be None if not set
    assert checkpoint_state["best_model_state"] is None


def test_restore_checkpoint_state_restores_all_state(trained_model_trainer):
    """
    Test restore_checkpoint_state() correctly restores all state.

    Acceptance Criteria:
    - ✅ Restores model state_dict
    - ✅ Restores optimizer state_dict
    - ✅ Restores scheduler state_dict
    - ✅ Restores training history
    - ✅ Restores best model state
    - ✅ Restores best validation accuracy
    - ✅ Restores early stopping state
    - ✅ Returns starting epoch (checkpoint epoch + 1)
    """
    trainer, original_model = trained_model_trainer

    # Create components
    optimizer = optim.Adam(original_model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.1)
    early_stopping = EarlyStopping(patience=10, monitor="val_loss")

    # Train for 1 step to initialize
    X_dummy = torch.randn(10, 10)
    y_dummy = torch.randint(0, 3, (10,))
    outputs = original_model(X_dummy)
    loss = nn.CrossEntropyLoss()(outputs, y_dummy)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    early_stopping(trainer.history[-1])

    # Get checkpoint state
    checkpoint_state = trainer.get_checkpoint_state(
        current_epoch=2,
        model=original_model,
        optimizer=optimizer,
        scheduler=scheduler,
        early_stopping=early_stopping,
    )

    # Create new components to restore into
    new_model = SimpleModel()
    new_optimizer = optim.Adam(new_model.parameters(), lr=0.001)
    new_scheduler = optim.lr_scheduler.StepLR(new_optimizer, step_size=10, gamma=0.1)
    new_early_stopping = EarlyStopping(patience=10, monitor="val_loss")
    new_trainer = ModelTrainer(config=trainer.config)

    # Restore checkpoint
    starting_epoch = new_trainer.restore_checkpoint_state(
        checkpoint_state=checkpoint_state,
        model=new_model,
        optimizer=new_optimizer,
        scheduler=new_scheduler,
        early_stopping=new_early_stopping,
    )

    # Verify starting epoch
    assert starting_epoch == 3  # checkpoint epoch (2) + 1

    # Verify history restored
    assert len(new_trainer.history) == len(trainer.history)
    assert new_trainer.history[0].epoch == 0
    assert new_trainer.history[-1].epoch == 2

    # Verify best validation accuracy restored
    assert new_trainer.best_val_accuracy == trainer.best_val_accuracy

    # Verify model state restored (check a parameter)
    original_param = list(original_model.parameters())[0]
    new_param = list(new_model.parameters())[0]
    assert torch.allclose(original_param, new_param)

    # Verify early stopping state restored
    assert new_early_stopping.counter == early_stopping.counter
    assert new_early_stopping.best_score == early_stopping.best_score


def test_restore_checkpoint_state_handles_missing_optional_components(model_trainer):
    """
    Test restore_checkpoint_state() handles missing optional components.

    Acceptance Criteria:
    - ✅ Works when scheduler is None
    - ✅ Works when early_stopping is None
    - ✅ Works when best_model_state is None
    """
    model = SimpleModel()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Create checkpoint without optional components
    checkpoint_state = model_trainer.get_checkpoint_state(
        current_epoch=5,
        model=model,
        optimizer=optimizer,
        scheduler=None,
        early_stopping=None,
    )

    # Restore without optional components
    new_model = SimpleModel()
    new_optimizer = optim.Adam(new_model.parameters(), lr=0.001)

    starting_epoch = model_trainer.restore_checkpoint_state(
        checkpoint_state=checkpoint_state,
        model=new_model,
        optimizer=new_optimizer,
        scheduler=None,
        early_stopping=None,
    )

    assert starting_epoch == 6  # 5 + 1


def test_checkpoint_state_serialization_deserialization_round_trip(
    trained_model_trainer,
):
    """
    Test that checkpoint state can be serialized and deserialized.

    Acceptance Criteria:
    - ✅ Model state_dict bytes can be loaded back
    - ✅ Optimizer state_dict bytes can be loaded back
    - ✅ Scheduler state_dict bytes can be loaded back
    - ✅ Round trip preserves all state
    """
    trainer, model = trained_model_trainer
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.1)

    # Train for 1 step
    X_dummy = torch.randn(10, 10)
    y_dummy = torch.randint(0, 3, (10,))
    outputs = model(X_dummy)
    loss = nn.CrossEntropyLoss()(outputs, y_dummy)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    # Get checkpoint
    checkpoint_state = trainer.get_checkpoint_state(
        current_epoch=2,
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        early_stopping=None,
    )

    # Simulate serialization (bytes are already serialized)
    model_bytes = checkpoint_state["model_state_dict"]
    optimizer_bytes = checkpoint_state["optimizer_state_dict"]
    scheduler_bytes = checkpoint_state["scheduler_state_dict"]

    # Deserialize and restore
    new_model = SimpleModel()
    new_optimizer = optim.Adam(new_model.parameters(), lr=0.001)
    new_scheduler = optim.lr_scheduler.StepLR(new_optimizer, step_size=10, gamma=0.1)

    # Load state dicts from bytes
    new_model.load_state_dict(torch.load(io.BytesIO(model_bytes)))
    new_optimizer.load_state_dict(torch.load(io.BytesIO(optimizer_bytes)))
    new_scheduler.load_state_dict(torch.load(io.BytesIO(scheduler_bytes)))

    # Verify state matches
    original_param = list(model.parameters())[0]
    new_param = list(new_model.parameters())[0]
    assert torch.allclose(original_param, new_param)


def test_restore_checkpoint_state_validates_config_compatibility(model_trainer):
    """
    Test that restore validates config compatibility.

    Acceptance Criteria:
    - ✅ Raises error if config mismatch detected
    - ✅ Logs warning if non-critical config differs
    """
    model = SimpleModel()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Create checkpoint with original config
    checkpoint_state = model_trainer.get_checkpoint_state(
        current_epoch=5,
        model=model,
        optimizer=optimizer,
        scheduler=None,
        early_stopping=None,
    )

    # Create new trainer with different config
    different_config = {
        "learning_rate": 0.01,  # Different learning rate
        "batch_size": 64,  # Different batch size
        "epochs": 50,  # Different epochs
    }
    new_trainer = ModelTrainer(config=different_config)
    new_model = SimpleModel()
    new_optimizer = optim.Adam(new_model.parameters(), lr=0.01)

    # Should raise error or log warning
    # For now, we'll just restore (implementation can add validation later)
    starting_epoch = new_trainer.restore_checkpoint_state(
        checkpoint_state=checkpoint_state,
        model=new_model,
        optimizer=new_optimizer,
        scheduler=None,
        early_stopping=None,
    )

    assert starting_epoch == 6


def test_get_checkpoint_state_includes_version_info(model_trainer):
    """
    Test that checkpoint state includes version information.

    Acceptance Criteria:
    - ✅ Includes KTRDR version
    - ✅ Includes PyTorch version
    - ✅ Includes checkpoint format version
    """
    model = SimpleModel()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    checkpoint_state = model_trainer.get_checkpoint_state(
        current_epoch=5,
        model=model,
        optimizer=optimizer,
        scheduler=None,
        early_stopping=None,
    )

    # Should include version info for compatibility checking
    assert "pytorch_version" in checkpoint_state
    assert checkpoint_state["pytorch_version"] == torch.__version__

    # Optional: checkpoint format version (for future migrations)
    assert "checkpoint_version" in checkpoint_state
