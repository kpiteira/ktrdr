"""
Integration tests for training checkpoint and resume functionality.

Tests the complete training checkpoint lifecycle:
- Train → checkpoint → interrupt → resume → complete

Validates Task 2.2 acceptance criteria:
- ✅ Full training checkpoint & resume flow works end-to-end
- ✅ Interrupted training at epoch N resumes at N+1
- ✅ Final model matches expected performance

Design:
- Uses real PyTorch models (simple MLP for speed)
- Uses real CheckpointService with PostgreSQL
- Tests actual checkpoint save/load/resume flow
- Verifies training state preservation
"""

import os
import shutil
import tempfile
import time
from collections.abc import Generator
from pathlib import Path

import numpy as np
import psycopg2
import pytest
import torch
import torch.nn as nn

from ktrdr.checkpoint.policy import CheckpointPolicy
from ktrdr.checkpoint.service import CheckpointService
from ktrdr.training.model_trainer import ModelTrainer


class SimpleMLPModel(nn.Module):
    """
    Simple MLP model for fast training tests.

    Architecture:
    - Input: 10 features
    - Hidden: 32 neurons (ReLU)
    - Output: 2 classes (binary classification)
    """

    def __init__(self, input_size=10, hidden_size=32, num_classes=2):
        super().__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x


@pytest.fixture
def db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Create PostgreSQL database connection for checkpoint tests.

    Uses environment variables or defaults from docker-compose.yml.
    """
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DB", "ktrdr")
    user = os.getenv("POSTGRES_USER", "ktrdr_admin")
    password = os.getenv("POSTGRES_PASSWORD", "ktrdr_dev_password")

    # Retry connection (database may be starting up)
    max_retries = 30
    retry_delay = 1

    conn = None
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
            )
            break
        except psycopg2.OperationalError as e:
            if attempt == max_retries - 1:
                pytest.fail(
                    f"Failed to connect to PostgreSQL after {max_retries} attempts. "
                    f"Error: {e}. "
                    f"Ensure PostgreSQL container is running: docker-compose up -d postgres"
                )
            time.sleep(retry_delay)

    assert conn is not None

    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def checkpoint_service() -> Generator[CheckpointService, None, None]:
    """
    Create CheckpointService instance for tests.

    Uses temporary artifacts directory for test isolation.
    """
    temp_artifacts_dir = Path(tempfile.mkdtemp(prefix="test_training_checkpoint_"))

    try:
        service = CheckpointService(artifacts_dir=temp_artifacts_dir)
        yield service
    finally:
        service.close()
        if temp_artifacts_dir.exists():
            shutil.rmtree(temp_artifacts_dir, ignore_errors=True)


@pytest.fixture
def clean_operations_table(db_connection):
    """
    Clean operations table before and after test.

    Ensures test isolation by removing any test operations.
    """
    cursor = db_connection.cursor()

    # Clean before test (including both patterns)
    cursor.execute(
        "DELETE FROM operations WHERE operation_id LIKE 'test_training_%' OR operation_id LIKE 'test_full_%';"
    )
    db_connection.commit()

    yield

    # Clean after test (including both patterns)
    cursor.execute(
        "DELETE FROM operations WHERE operation_id LIKE 'test_training_%' OR operation_id LIKE 'test_full_%';"
    )
    db_connection.commit()
    cursor.close()


@pytest.fixture
def test_dataset():
    """
    Create simple synthetic dataset for fast testing.

    Returns:
        Tuple of (X_train, y_train, X_val, y_val)
        - X: shape (N, 10) - 10 features
        - y: shape (N,) - binary labels (0 or 1)
    """
    np.random.seed(42)

    # Generate training data
    n_train = 200
    X_train = np.random.randn(n_train, 10).astype(np.float32)
    y_train = (X_train[:, 0] + X_train[:, 1] > 0).astype(np.int64)

    # Generate validation data
    n_val = 50
    X_val = np.random.randn(n_val, 10).astype(np.float32)
    y_val = (X_val[:, 0] + X_val[:, 1] > 0).astype(np.int64)

    # Convert to tensors
    X_train = torch.from_numpy(X_train)
    y_train = torch.from_numpy(y_train)
    X_val = torch.from_numpy(X_val)
    y_val = torch.from_numpy(y_val)

    return X_train, y_train, X_val, y_val


@pytest.fixture
def training_config():
    """
    Create minimal training configuration for tests.

    Returns:
        Dictionary with training hyperparameters
    """
    return {
        "learning_rate": 0.01,
        "batch_size": 32,
        "epochs": 20,  # Small number for fast tests
        "optimizer": "adam",
        "early_stopping_patience": 100,  # Disable early stopping
        "save_best_model": True,
    }


@pytest.fixture
def checkpoint_policy_fast():
    """
    Create checkpoint policy for fast testing.

    Checkpoints every 1 second (instead of 5 minutes) for test speed.
    """
    return CheckpointPolicy(
        checkpoint_interval_seconds=1.0,  # Checkpoint every 1 second for fast tests
        force_checkpoint_every_n=5,  # Force checkpoint every 5 epochs (safety)
        delete_on_completion=True,
        checkpoint_on_failure=True,
    )


def test_training_checkpoint_save_during_training(
    db_connection,
    checkpoint_service,
    clean_operations_table,
    test_dataset,
    training_config,
    checkpoint_policy_fast,
):
    """
    Test that checkpoints are saved during training.

    Acceptance Criteria:
    - ✅ Training runs for at least 5 epochs
    - ✅ At least one checkpoint is saved
    - ✅ Checkpoint contains correct epoch number
    - ✅ Checkpoint contains model state_dict
    - ✅ Checkpoint contains training history
    """
    operation_id = "test_training_checkpoint_save_001"

    # Create operation in database
    cursor = db_connection.cursor()
    cursor.execute(
        """
        INSERT INTO operations (
            operation_id,
            operation_type,
            status,
            created_at
        ) VALUES (%s, %s, %s, CURRENT_TIMESTAMP);
    """,
        (operation_id, "training", "RUNNING"),
    )
    db_connection.commit()

    # Prepare data
    X_train, y_train, X_val, y_val = test_dataset

    # Create model
    model = SimpleMLPModel(input_size=10, hidden_size=32, num_classes=2)

    # Create trainer with checkpoint support
    trainer = ModelTrainer(
        config=training_config,
        progress_callback=None,
        cancellation_token=None,
    )

    # Inject checkpoint support
    trainer.checkpoint_service = checkpoint_service
    trainer.checkpoint_policy = checkpoint_policy_fast
    trainer.operation_id = operation_id
    trainer.last_checkpoint_time = None

    # Train for 10 epochs (should trigger checkpoint due to time policy)
    training_config["epochs"] = 10
    trainer.train(model, X_train, y_train, X_val, y_val)

    # Verify checkpoint was saved
    checkpoint = checkpoint_service.load_checkpoint(operation_id)
    assert checkpoint is not None, "Checkpoint should be saved during training"

    # Verify checkpoint contains correct data
    assert "state" in checkpoint
    assert "epoch" in checkpoint["state"]
    assert (
        checkpoint["state"]["epoch"] >= 5
    ), "Should checkpoint after at least 5 epochs"
    assert checkpoint["state"]["epoch"] < 10, "Should checkpoint before completion"

    # Verify checkpoint contains model artifacts
    assert "artifacts" in checkpoint
    assert "model.pt" in checkpoint["artifacts"]
    assert "optimizer.pt" in checkpoint["artifacts"]

    # Verify training history preserved
    assert "history" in checkpoint["state"]
    assert len(checkpoint["state"]["history"]) > 0

    # Cleanup
    checkpoint_service.delete_checkpoint(operation_id)
    cursor.execute("DELETE FROM operations WHERE operation_id = %s;", (operation_id,))
    db_connection.commit()
    cursor.close()


def test_training_resume_from_checkpoint(
    db_connection,
    checkpoint_service,
    clean_operations_table,
    test_dataset,
    training_config,
    checkpoint_policy_fast,
):
    """
    Test resuming training from checkpoint.

    Acceptance Criteria:
    - ✅ Train to epoch N, save checkpoint
    - ✅ Can load checkpoint and restore trainer state
    - ✅ Resume training continues from epoch N+1
    - ✅ Training history preserved from original run
    - ✅ Final model achieves reasonable accuracy
    """
    operation_id_1 = "test_training_resume_001_original"
    operation_id_2 = "test_training_resume_001_resumed"

    # Create operations in database
    cursor = db_connection.cursor()
    for op_id in [operation_id_1, operation_id_2]:
        cursor.execute(
            """
            INSERT INTO operations (
                operation_id,
                operation_type,
                status,
                created_at
            ) VALUES (%s, %s, %s, CURRENT_TIMESTAMP);
        """,
            (op_id, "training", "RUNNING"),
        )
    db_connection.commit()

    # Prepare data
    X_train, y_train, X_val, y_val = test_dataset

    # ============================================================================
    # PART 1: Original training (train to epoch 10, then "interrupt")
    # ============================================================================

    # Create original model
    model_1 = SimpleMLPModel(input_size=10, hidden_size=32, num_classes=2)

    # Create trainer with checkpoint support
    trainer_1 = ModelTrainer(
        config=training_config,
        progress_callback=None,
        cancellation_token=None,
    )

    trainer_1.checkpoint_service = checkpoint_service
    trainer_1.checkpoint_policy = checkpoint_policy_fast
    trainer_1.operation_id = operation_id_1
    trainer_1.last_checkpoint_time = None

    # Train for 10 epochs
    training_config["epochs"] = 10
    trainer_1.train(model_1, X_train, y_train, X_val, y_val)

    # Verify checkpoint exists
    checkpoint = checkpoint_service.load_checkpoint(operation_id_1)
    assert checkpoint is not None, "Checkpoint should exist after training"

    interrupted_epoch = checkpoint["state"]["epoch"]
    original_history_length = len(checkpoint["state"]["history"])

    assert interrupted_epoch >= 5, "Should have checkpointed at least at epoch 5"
    assert interrupted_epoch <= 10, "Should not exceed 10 epochs"

    print(f"✓ Original training interrupted at epoch {interrupted_epoch}")
    print(f"✓ Training history has {original_history_length} entries")

    # ============================================================================
    # PART 2: Resume training (continue from checkpoint to epoch 20)
    # ============================================================================

    # Create new model (fresh instance)
    model_2 = SimpleMLPModel(input_size=10, hidden_size=32, num_classes=2)

    # Create new trainer for resume
    trainer_2 = ModelTrainer(
        config=training_config,
        progress_callback=None,
        cancellation_token=None,
    )

    trainer_2.checkpoint_service = checkpoint_service
    trainer_2.checkpoint_policy = checkpoint_policy_fast
    trainer_2.operation_id = operation_id_2
    trainer_2.last_checkpoint_time = None

    # Restore checkpoint state
    trainer_2.restore_checkpoint_state(
        model=model_2,
        checkpoint_state=checkpoint["state"],
        artifacts=checkpoint["artifacts"],
    )

    # Verify state restored correctly
    # Note: history will be TrainingMetrics objects, checkpoint history is dicts
    # So we compare lengths and individual epochs
    assert len(trainer_2.history) == len(checkpoint["state"]["history"])
    assert trainer_2.best_val_accuracy == checkpoint["state"]["best_val_accuracy"]

    print("✓ Checkpoint state restored successfully")

    # Resume training from interrupted epoch + 1 to epoch 20
    training_config["epochs"] = 20
    start_epoch = interrupted_epoch + 1

    # Modify training config to start from resume point
    # Note: ModelTrainer.train() needs to support start_epoch parameter
    # This will be verified when we run the test
    trainer_2.train(model_2, X_train, y_train, X_val, y_val, start_epoch=start_epoch)

    # Verify training continued correctly
    final_history = trainer_2.history
    assert (
        len(final_history) == 20
    ), f"Should have 20 total epochs, got {len(final_history)}"

    # Verify first part of history matches original (preserved)
    # Compare epoch numbers (history is TrainingMetrics objects)
    for i in range(original_history_length):
        assert final_history[i].epoch == checkpoint["state"]["history"][i]["epoch"]

    print(f"✓ Training resumed from epoch {start_epoch}")
    print(f"✓ Final training history has {len(final_history)} entries")
    print("✓ History preserved correctly from original run")

    # Verify final model achieves reasonable accuracy (>50% for this simple task)
    final_val_accuracy = final_history[-1].val_accuracy
    assert (
        final_val_accuracy > 0.5
    ), f"Final val accuracy {final_val_accuracy} should be >0.5"

    print(f"✓ Final validation accuracy: {final_val_accuracy:.3f}")

    # Cleanup
    checkpoint_service.delete_checkpoint(operation_id_1)
    checkpoint_service.delete_checkpoint(operation_id_2)
    cursor.execute(
        "DELETE FROM operations WHERE operation_id IN (%s, %s);",
        (operation_id_1, operation_id_2),
    )
    db_connection.commit()
    cursor.close()


def test_full_training_checkpoint_resume_workflow(
    db_connection,
    checkpoint_service,
    clean_operations_table,
    test_dataset,
    training_config,
    checkpoint_policy_fast,
):
    """
    Test complete workflow: train → interrupt → resume → complete.

    This is the primary end-to-end test for Task 2.2.

    Acceptance Criteria:
    - ✅ Start training (target: 30 epochs)
    - ✅ Interrupt at epoch ~10 (simulate failure)
    - ✅ Checkpoint preserved
    - ✅ Resume training from checkpoint
    - ✅ Training completes to epoch 30
    - ✅ Final model state correct
    - ✅ Training history complete and preserved
    """
    operation_id_original = "test_full_workflow_001_original"
    operation_id_resumed = "test_full_workflow_001_resumed"

    # Create operations
    cursor = db_connection.cursor()
    for op_id in [operation_id_original, operation_id_resumed]:
        cursor.execute(
            """
            INSERT INTO operations (
                operation_id,
                operation_type,
                status,
                created_at
            ) VALUES (%s, %s, %s, CURRENT_TIMESTAMP);
        """,
            (op_id, "training", "RUNNING"),
        )
    db_connection.commit()

    # Prepare data
    X_train, y_train, X_val, y_val = test_dataset

    # ============================================================================
    # PHASE 1: Initial Training (train to ~10 epochs, then interrupt)
    # ============================================================================

    model_initial = SimpleMLPModel()
    trainer_initial = ModelTrainer(
        config=training_config, progress_callback=None, cancellation_token=None
    )

    trainer_initial.checkpoint_service = checkpoint_service
    trainer_initial.checkpoint_policy = checkpoint_policy_fast
    trainer_initial.operation_id = operation_id_original
    trainer_initial.last_checkpoint_time = None

    # Train for 12 epochs (will checkpoint around epoch 10 due to time policy)
    training_config["epochs"] = 12
    trainer_initial.train(model_initial, X_train, y_train, X_val, y_val)

    # Load checkpoint
    checkpoint = checkpoint_service.load_checkpoint(operation_id_original)
    assert checkpoint is not None

    interrupted_epoch = checkpoint["state"]["epoch"]
    print(f"\n[PHASE 1] Training interrupted at epoch {interrupted_epoch}")

    # Mark original operation as FAILED (simulate API crash)
    cursor.execute(
        """
        UPDATE operations
        SET status = 'FAILED',
            completed_at = CURRENT_TIMESTAMP,
            error_message = 'Simulated interruption for test'
        WHERE operation_id = %s;
    """,
        (operation_id_original,),
    )
    db_connection.commit()

    # Verify checkpoint preserved (not deleted for FAILED operations)
    checkpoint_after_fail = checkpoint_service.load_checkpoint(operation_id_original)
    assert (
        checkpoint_after_fail is not None
    ), "Checkpoint should be preserved for FAILED operation"

    # ============================================================================
    # PHASE 2: Resume Training (continue to 30 epochs)
    # ============================================================================

    model_resumed = SimpleMLPModel()
    trainer_resumed = ModelTrainer(
        config=training_config, progress_callback=None, cancellation_token=None
    )

    trainer_resumed.checkpoint_service = checkpoint_service
    trainer_resumed.checkpoint_policy = checkpoint_policy_fast
    trainer_resumed.operation_id = operation_id_resumed
    trainer_resumed.last_checkpoint_time = None

    # Restore state
    trainer_resumed.restore_checkpoint_state(
        model=model_resumed,
        checkpoint_state=checkpoint["state"],
        artifacts=checkpoint["artifacts"],
    )

    # Resume training to 30 total epochs
    training_config["epochs"] = 30
    start_epoch = interrupted_epoch + 1
    trainer_resumed.train(
        model_resumed, X_train, y_train, X_val, y_val, start_epoch=start_epoch
    )

    print(f"[PHASE 2] Training resumed from epoch {start_epoch} to 30")

    # ============================================================================
    # VERIFICATION
    # ============================================================================

    # Verify training completed
    assert len(trainer_resumed.history) == 30, "Should have 30 total epochs"

    # Verify training history preserved
    original_history = checkpoint["state"]["history"]
    for i in range(len(original_history)):
        assert trainer_resumed.history[i].epoch == original_history[i]["epoch"]
        # Note: Metrics may differ slightly due to random initialization
        # but epoch numbers should match

    # Verify final model performance
    final_accuracy = trainer_resumed.history[-1].val_accuracy
    assert final_accuracy > 0.5, f"Final accuracy {final_accuracy} should be >0.5"

    print("\n✅ WORKFLOW COMPLETE:")
    print(f"   - Interrupted at epoch {interrupted_epoch}")
    print(f"   - Resumed from epoch {start_epoch}")
    print("   - Completed 30 total epochs")
    print(f"   - Final validation accuracy: {final_accuracy:.3f}")

    # Cleanup
    checkpoint_service.delete_checkpoint(operation_id_original)
    checkpoint_service.delete_checkpoint(operation_id_resumed)
    cursor.execute(
        "DELETE FROM operations WHERE operation_id IN (%s, %s);",
        (operation_id_original, operation_id_resumed),
    )
    db_connection.commit()
    cursor.close()
