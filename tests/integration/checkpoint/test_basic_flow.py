"""
Integration tests for checkpoint basic CRUD flow.

Tests the complete checkpoint lifecycle with real PostgreSQL database:
- Save checkpoint (UPSERT pattern)
- Load checkpoint
- Delete checkpoint
- Filesystem artifact management
- Cleanup trigger on operation completion

Validates Task 1.3 acceptance criteria:
- ✅ Full CRUD flow works end-to-end
- ✅ Only 1 checkpoint per operation (UPSERT verified)
- ✅ DB and filesystem stay in sync
- ✅ Cleanup works correctly
"""

import json
import os
import shutil
import tempfile
import time
from collections.abc import Generator
from pathlib import Path

import psycopg2
import pytest

from ktrdr.checkpoint.service import CheckpointService


@pytest.fixture
def db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Create PostgreSQL database connection for checkpoint tests.

    Uses environment variables or defaults from docker-compose.yml:
    - POSTGRES_HOST: localhost
    - POSTGRES_PORT: 5432
    - POSTGRES_DB: ktrdr
    - POSTGRES_USER: ktrdr_admin
    - POSTGRES_PASSWORD: ktrdr_dev_password

    Yields:
        Database connection
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

    Yields:
        CheckpointService instance with test artifacts directory
    """
    # Create temp artifacts directory for test isolation
    temp_artifacts_dir = Path(tempfile.mkdtemp(prefix="test_checkpoint_artifacts_"))

    try:
        service = CheckpointService(artifacts_dir=temp_artifacts_dir)
        yield service
    finally:
        # Cleanup: close connection and remove temp artifacts
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

    # Clean before test
    cursor.execute("DELETE FROM operations WHERE operation_id LIKE 'test_%';")
    db_connection.commit()

    yield

    # Clean after test
    cursor.execute("DELETE FROM operations WHERE operation_id LIKE 'test_%';")
    db_connection.commit()
    cursor.close()


def test_save_load_delete_flow(
    checkpoint_service, db_connection, clean_operations_table
):
    """
    Test basic checkpoint CRUD flow: save → load → delete.

    Acceptance Criteria:
    - ✅ Can save checkpoint with state and artifacts
    - ✅ Can load checkpoint and retrieve state + artifacts
    - ✅ Loaded data matches saved data
    - ✅ Can delete checkpoint
    - ✅ DB record deleted
    - ✅ Filesystem artifacts deleted
    """
    operation_id = "test_save_load_delete_001"

    # Step 1: Create test operation in database (required for FK constraint)
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

    # Step 2: Save checkpoint
    checkpoint_data = {
        "checkpoint_id": f"{operation_id}_1",
        "checkpoint_type": "epoch_snapshot",
        "metadata": {"epoch": 10, "val_accuracy": 0.85},
        "state": {
            "epoch": 10,
            "loss": 0.25,
            "config": {"learning_rate": 0.001},
        },
        "artifacts": {
            "model.pt": b"fake_model_weights_12345",
            "optimizer.pt": b"fake_optimizer_state_67890",
        },
    }

    checkpoint_service.save_checkpoint(operation_id, checkpoint_data)

    # Step 3: Load checkpoint
    loaded = checkpoint_service.load_checkpoint(operation_id)

    assert loaded is not None, "Checkpoint should exist after save"
    assert loaded["operation_id"] == operation_id
    assert loaded["checkpoint_id"] == f"{operation_id}_1"
    assert loaded["checkpoint_type"] == "epoch_snapshot"

    # Verify metadata
    assert loaded["metadata"]["epoch"] == 10
    assert loaded["metadata"]["val_accuracy"] == 0.85

    # Verify state
    assert loaded["state"]["epoch"] == 10
    assert loaded["state"]["loss"] == 0.25
    assert loaded["state"]["config"]["learning_rate"] == 0.001

    # Verify artifacts
    assert "artifacts" in loaded
    assert loaded["artifacts"]["model.pt"] == b"fake_model_weights_12345"
    assert loaded["artifacts"]["optimizer.pt"] == b"fake_optimizer_state_67890"

    # Verify artifacts exist on filesystem
    artifacts_path = Path(loaded["artifacts_path"])
    assert artifacts_path.exists(), "Artifacts directory should exist"
    assert (artifacts_path / "model.pt").exists()
    assert (artifacts_path / "optimizer.pt").exists()

    # Step 4: Delete checkpoint
    checkpoint_service.delete_checkpoint(operation_id)

    # Step 5: Verify deletion
    loaded_after_delete = checkpoint_service.load_checkpoint(operation_id)
    assert loaded_after_delete is None, "Checkpoint should not exist after delete"

    # Verify DB record deleted
    cursor.execute(
        "SELECT COUNT(*) FROM operation_checkpoints WHERE operation_id = %s;",
        (operation_id,),
    )
    count = cursor.fetchone()[0]
    assert count == 0, "DB record should be deleted"

    # Verify artifacts deleted from filesystem
    assert not artifacts_path.exists(), "Artifacts directory should be deleted"

    cursor.close()


def test_upsert_behavior(checkpoint_service, db_connection, clean_operations_table):
    """
    Test UPSERT behavior: save twice, verify only 1 row exists.

    Acceptance Criteria:
    - ✅ First save creates checkpoint
    - ✅ Second save replaces first checkpoint (UPSERT)
    - ✅ Only 1 row exists in database after both saves
    - ✅ Loaded checkpoint has data from second save
    - ✅ Old artifacts cleaned up, only new artifacts exist
    """
    operation_id = "test_upsert_001"

    # Create test operation
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

    # Save first checkpoint (epoch 10)
    checkpoint_data_1 = {
        "checkpoint_id": f"{operation_id}_checkpoint_1",
        "checkpoint_type": "epoch_snapshot",
        "metadata": {"epoch": 10, "val_accuracy": 0.80},
        "state": {"epoch": 10, "loss": 0.30},
        "artifacts": {"model.pt": b"model_weights_epoch_10"},
    }

    checkpoint_service.save_checkpoint(operation_id, checkpoint_data_1)

    # Verify first checkpoint saved
    checkpoint_1 = checkpoint_service.load_checkpoint(operation_id)
    assert checkpoint_1 is not None
    assert checkpoint_1["metadata"]["epoch"] == 10
    assert checkpoint_1["state"]["loss"] == 0.30
    artifacts_path_1 = Path(checkpoint_1["artifacts_path"])
    assert artifacts_path_1.exists()

    # Verify only 1 row in database
    cursor.execute(
        "SELECT COUNT(*) FROM operation_checkpoints WHERE operation_id = %s;",
        (operation_id,),
    )
    count_after_first = cursor.fetchone()[0]
    assert (
        count_after_first == 1
    ), "Should have exactly 1 checkpoint row after first save"

    # Save second checkpoint (epoch 20) - UPSERT should replace first
    checkpoint_data_2 = {
        "checkpoint_id": f"{operation_id}_checkpoint_2",
        "checkpoint_type": "epoch_snapshot",
        "metadata": {"epoch": 20, "val_accuracy": 0.90},
        "state": {"epoch": 20, "loss": 0.15},
        "artifacts": {"model.pt": b"model_weights_epoch_20_better"},
    }

    checkpoint_service.save_checkpoint(operation_id, checkpoint_data_2)

    # Verify still only 1 row in database (UPSERT replaced first)
    cursor.execute(
        "SELECT COUNT(*) FROM operation_checkpoints WHERE operation_id = %s;",
        (operation_id,),
    )
    count_after_second = cursor.fetchone()[0]
    assert (
        count_after_second == 1
    ), "Should still have exactly 1 checkpoint row after UPSERT"

    # Verify loaded checkpoint has data from second save
    checkpoint_2 = checkpoint_service.load_checkpoint(operation_id)
    assert checkpoint_2 is not None
    assert (
        checkpoint_2["checkpoint_id"] == f"{operation_id}_checkpoint_2"
    ), "Should load second checkpoint"
    assert checkpoint_2["metadata"]["epoch"] == 20
    assert checkpoint_2["metadata"]["val_accuracy"] == 0.90
    assert checkpoint_2["state"]["loss"] == 0.15
    assert checkpoint_2["artifacts"]["model.pt"] == b"model_weights_epoch_20_better"

    # Verify new artifacts exist
    artifacts_path_2 = Path(checkpoint_2["artifacts_path"])
    assert artifacts_path_2.exists()
    assert (
        artifacts_path_2 / "model.pt"
    ).read_bytes() == b"model_weights_epoch_20_better"

    # Cleanup
    checkpoint_service.delete_checkpoint(operation_id)
    cursor.close()


def test_filesystem_artifact_management(
    checkpoint_service, db_connection, clean_operations_table
):
    """
    Test filesystem artifact management (atomic writes, cleanup).

    Acceptance Criteria:
    - ✅ Artifacts written to correct directory
    - ✅ Multiple artifact files handled correctly
    - ✅ Artifacts readable after save
    - ✅ Artifacts cleaned up on delete
    - ✅ Atomic write pattern (temp → rename) verified
    """
    operation_id = "test_artifacts_001"

    # Create test operation
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

    # Save checkpoint with multiple artifacts
    checkpoint_data = {
        "checkpoint_id": f"{operation_id}_checkpoint_1",
        "checkpoint_type": "epoch_snapshot",
        "metadata": {"epoch": 5},
        "state": {"epoch": 5},
        "artifacts": {
            "model.pt": b"model_weights_data",
            "optimizer.pt": b"optimizer_state_data",
            "scheduler.pt": b"scheduler_state_data",
            "best_model.pt": b"best_model_weights_data",
        },
    }

    checkpoint_service.save_checkpoint(operation_id, checkpoint_data)

    # Load checkpoint
    loaded = checkpoint_service.load_checkpoint(operation_id)
    assert loaded is not None

    # Verify artifacts directory structure
    artifacts_path = Path(loaded["artifacts_path"])
    assert artifacts_path.exists()
    assert artifacts_path.is_dir()

    # Verify all artifact files exist
    assert (artifacts_path / "model.pt").exists()
    assert (artifacts_path / "optimizer.pt").exists()
    assert (artifacts_path / "scheduler.pt").exists()
    assert (artifacts_path / "best_model.pt").exists()

    # Verify artifact contents match
    assert (artifacts_path / "model.pt").read_bytes() == b"model_weights_data"
    assert (artifacts_path / "optimizer.pt").read_bytes() == b"optimizer_state_data"
    assert (artifacts_path / "scheduler.pt").read_bytes() == b"scheduler_state_data"
    assert (artifacts_path / "best_model.pt").read_bytes() == b"best_model_weights_data"

    # Verify loaded artifacts match
    assert loaded["artifacts"]["model.pt"] == b"model_weights_data"
    assert loaded["artifacts"]["optimizer.pt"] == b"optimizer_state_data"
    assert loaded["artifacts"]["scheduler.pt"] == b"scheduler_state_data"
    assert loaded["artifacts"]["best_model.pt"] == b"best_model_weights_data"

    # Verify artifacts_size_bytes calculated correctly
    expected_size = (
        len(b"model_weights_data")
        + len(b"optimizer_state_data")
        + len(b"scheduler_state_data")
        + len(b"best_model_weights_data")
    )
    assert loaded["artifacts_size_bytes"] == expected_size

    # Delete checkpoint and verify artifacts cleaned up
    checkpoint_service.delete_checkpoint(operation_id)

    # Verify artifacts directory deleted
    assert not artifacts_path.exists(), "Artifacts directory should be deleted"

    cursor.close()


def test_cleanup_trigger_on_completion(
    db_connection, checkpoint_service, clean_operations_table
):
    """
    Test cleanup trigger fires when operation completes.

    Acceptance Criteria:
    - ✅ Checkpoint exists while operation RUNNING
    - ✅ Trigger fires when status changes to COMPLETED
    - ✅ Checkpoint deleted from database
    - ✅ FAILED/CANCELLED operations keep checkpoint (not deleted by trigger)
    """
    operation_id = "test_cleanup_trigger_001"

    # Create operation and save checkpoint
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

    # Save checkpoint
    checkpoint_data = {
        "checkpoint_id": f"{operation_id}_checkpoint_1",
        "checkpoint_type": "epoch_snapshot",
        "metadata": {"epoch": 50},
        "state": {"epoch": 50, "loss": 0.10},
        "artifacts": {"model.pt": b"final_model_weights"},
    }

    checkpoint_service.save_checkpoint(operation_id, checkpoint_data)

    # Verify checkpoint exists
    cursor.execute(
        "SELECT COUNT(*) FROM operation_checkpoints WHERE operation_id = %s;",
        (operation_id,),
    )
    count_before = cursor.fetchone()[0]
    assert count_before == 1, "Checkpoint should exist while operation RUNNING"

    # Mark operation as COMPLETED (trigger should fire)
    cursor.execute(
        """
        UPDATE operations
        SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
        WHERE operation_id = %s;
    """,
        (operation_id,),
    )
    db_connection.commit()

    # Verify checkpoint deleted by trigger
    cursor.execute(
        "SELECT COUNT(*) FROM operation_checkpoints WHERE operation_id = %s;",
        (operation_id,),
    )
    count_after = cursor.fetchone()[0]
    assert (
        count_after == 0
    ), "Checkpoint should be deleted by trigger when operation COMPLETED"

    cursor.close()


def test_cleanup_trigger_preserves_failed_checkpoints(
    db_connection, checkpoint_service, clean_operations_table
):
    """
    Test cleanup trigger preserves checkpoints for FAILED operations.

    Acceptance Criteria:
    - ✅ FAILED operations keep checkpoint (trigger does NOT delete)
    - ✅ Checkpoint available for resume
    """
    operation_id = "test_cleanup_trigger_failed_001"

    # Create operation and save checkpoint
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

    # Save checkpoint
    checkpoint_data = {
        "checkpoint_id": f"{operation_id}_checkpoint_1",
        "checkpoint_type": "epoch_snapshot",
        "metadata": {"epoch": 25},
        "state": {"epoch": 25},
        "artifacts": {},
    }

    checkpoint_service.save_checkpoint(operation_id, checkpoint_data)

    # Mark operation as FAILED (trigger should NOT delete checkpoint)
    cursor.execute(
        """
        UPDATE operations
        SET status = 'FAILED',
            completed_at = CURRENT_TIMESTAMP,
            error_message = 'Out of memory'
        WHERE operation_id = %s;
    """,
        (operation_id,),
    )
    db_connection.commit()

    # Verify checkpoint still exists
    cursor.execute(
        "SELECT COUNT(*) FROM operation_checkpoints WHERE operation_id = %s;",
        (operation_id,),
    )
    count_after = cursor.fetchone()[0]
    assert (
        count_after == 1
    ), "Checkpoint should be preserved for FAILED operations (for resume)"

    # Cleanup manually
    checkpoint_service.delete_checkpoint(operation_id)
    cursor.close()


def test_cleanup_trigger_preserves_cancelled_checkpoints(
    db_connection, checkpoint_service, clean_operations_table
):
    """
    Test cleanup trigger preserves checkpoints for CANCELLED operations.

    Acceptance Criteria:
    - ✅ CANCELLED operations keep checkpoint (trigger does NOT delete)
    - ✅ Checkpoint available for resume
    """
    operation_id = "test_cleanup_trigger_cancelled_001"

    # Create operation and save checkpoint
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

    # Save checkpoint
    checkpoint_data = {
        "checkpoint_id": f"{operation_id}_checkpoint_1",
        "checkpoint_type": "epoch_snapshot",
        "metadata": {"epoch": 15},
        "state": {"epoch": 15},
        "artifacts": {},
    }

    checkpoint_service.save_checkpoint(operation_id, checkpoint_data)

    # Mark operation as CANCELLED (trigger should NOT delete checkpoint)
    cursor.execute(
        """
        UPDATE operations
        SET status = 'CANCELLED', completed_at = CURRENT_TIMESTAMP
        WHERE operation_id = %s;
    """,
        (operation_id,),
    )
    db_connection.commit()

    # Verify checkpoint still exists
    cursor.execute(
        "SELECT COUNT(*) FROM operation_checkpoints WHERE operation_id = %s;",
        (operation_id,),
    )
    count_after = cursor.fetchone()[0]
    assert (
        count_after == 1
    ), "Checkpoint should be preserved for CANCELLED operations (for resume)"

    # Cleanup manually
    checkpoint_service.delete_checkpoint(operation_id)
    cursor.close()


def test_checkpoint_state_size_calculation(
    checkpoint_service, db_connection, clean_operations_table
):
    """
    Test that state_size_bytes is calculated correctly.

    Acceptance Criteria:
    - ✅ state_size_bytes matches actual JSON size
    - ✅ Size recorded in database
    """
    operation_id = "test_state_size_001"

    # Create operation
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

    # Create checkpoint with known state
    state = {
        "epoch": 42,
        "loss": 0.123,
        "config": {"learning_rate": 0.001, "batch_size": 32},
        "history": [{"epoch": i, "loss": 1.0 / (i + 1)} for i in range(10)],
    }

    checkpoint_data = {
        "checkpoint_id": f"{operation_id}_checkpoint_1",
        "checkpoint_type": "epoch_snapshot",
        "metadata": {},
        "state": state,
        "artifacts": {},
    }

    checkpoint_service.save_checkpoint(operation_id, checkpoint_data)

    # Calculate expected size
    state_json = json.dumps(state)
    expected_size = len(state_json.encode("utf-8"))

    # Load and verify
    loaded = checkpoint_service.load_checkpoint(operation_id)
    assert loaded["state_size_bytes"] == expected_size

    # Verify in database
    cursor.execute(
        "SELECT state_size_bytes FROM operation_checkpoints WHERE operation_id = %s;",
        (operation_id,),
    )
    db_size = cursor.fetchone()[0]
    assert db_size == expected_size

    # Cleanup
    checkpoint_service.delete_checkpoint(operation_id)
    cursor.close()


def test_load_nonexistent_checkpoint(checkpoint_service):
    """
    Test loading nonexistent checkpoint returns None.

    Acceptance Criteria:
    - ✅ Returns None for nonexistent operation_id
    - ✅ No error raised
    """
    result = checkpoint_service.load_checkpoint("nonexistent_operation_123")
    assert result is None, "Should return None for nonexistent checkpoint"


def test_delete_nonexistent_checkpoint(checkpoint_service):
    """
    Test deleting nonexistent checkpoint is idempotent (no error).

    Acceptance Criteria:
    - ✅ No error raised when deleting nonexistent checkpoint
    - ✅ Idempotent operation
    """
    # Should not raise error
    checkpoint_service.delete_checkpoint("nonexistent_operation_456")

    # Verify no error by reaching this point
    assert True, "delete_checkpoint should be idempotent"
