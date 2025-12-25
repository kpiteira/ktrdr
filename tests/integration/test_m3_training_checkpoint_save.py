"""Integration tests for M3: Training Checkpoint Save.

This test suite verifies the complete M3 checkpoint save flow:
1. Start training, wait for periodic checkpoint
2. Verify checkpoint in DB with correct state
3. Verify artifacts on filesystem
4. Cancel training, verify cancellation checkpoint
5. Verify checkpoint type updated

Note: This uses mocked DB sessions and real temp directories for fast feedback.
For real Docker-based tests, see tests/e2e/container/
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.checkpoint.checkpoint_policy import CheckpointPolicy
from ktrdr.checkpoint.checkpoint_service import CheckpointData, CheckpointService
from ktrdr.checkpoint.schemas import TrainingCheckpointState

# ============================================================================
# Fixtures
# ============================================================================


def create_mock_session_factory(storage: dict):
    """Create a mock session factory that simulates UPSERT behavior.

    This factory maintains state in the provided storage dict to allow
    verification of database operations.
    """

    @asynccontextmanager
    async def mock_factory():
        session = AsyncMock()

        # Capture UPSERT values
        async def capture_execute(stmt):
            # Extract values from the INSERT statement
            if hasattr(stmt, "compile"):
                # For actual SQLAlchemy statements, we'd need to inspect
                # Instead, we store based on a simple pattern
                pass
            return MagicMock()

        session.execute = capture_execute
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.delete = AsyncMock()

        yield session

    return mock_factory


class MockCheckpointRepository:
    """In-memory checkpoint repository for integration testing.

    Simulates the database operations of CheckpointService.
    """

    def __init__(self):
        self.checkpoints: dict[str, dict] = {}

    async def save(
        self,
        operation_id: str,
        checkpoint_type: str,
        state: dict,
        artifacts_path: Optional[str],
        state_size_bytes: int,
        artifacts_size_bytes: Optional[int],
    ):
        """UPSERT checkpoint record."""
        self.checkpoints[operation_id] = {
            "operation_id": operation_id,
            "checkpoint_type": checkpoint_type,
            "state": state,
            "artifacts_path": artifacts_path,
            "created_at": datetime.now(timezone.utc),
            "state_size_bytes": state_size_bytes,
            "artifacts_size_bytes": artifacts_size_bytes,
        }

    def get(self, operation_id: str) -> Optional[dict]:
        """Get checkpoint record."""
        return self.checkpoints.get(operation_id)

    def delete(self, operation_id: str) -> bool:
        """Delete checkpoint record."""
        if operation_id in self.checkpoints:
            del self.checkpoints[operation_id]
            return True
        return False


class IntegrationCheckpointService(CheckpointService):
    """CheckpointService subclass with in-memory repository for testing.

    This allows us to verify DB state without a real database.
    """

    def __init__(self, artifacts_dir: str):
        # Create a mock session factory
        self._mock_repo = MockCheckpointRepository()
        self._artifacts_dir = Path(artifacts_dir)
        self._session_factory = self._create_mock_factory()

    def _create_mock_factory(self):
        """Create mock session factory that uses our in-memory repo."""

        @asynccontextmanager
        async def mock_factory():
            session = MagicMock()
            session.commit = AsyncMock()
            session.rollback = AsyncMock()
            yield session

        return mock_factory

    async def save_checkpoint(
        self,
        operation_id: str,
        checkpoint_type: str,
        state: dict,
        artifacts: Optional[dict[str, bytes]] = None,
    ) -> None:
        """Save checkpoint with both in-memory repo and filesystem."""
        import json

        artifacts_path: Optional[Path] = None
        artifacts_size_bytes: Optional[int] = None

        # Write artifacts if provided
        if artifacts:
            artifacts_path = await self._write_artifacts(operation_id, artifacts)
            artifacts_size_bytes = sum(len(data) for data in artifacts.values())

        # Calculate state size
        state_json = json.dumps(state)
        state_size_bytes = len(state_json.encode("utf-8"))

        # Save to in-memory repository
        await self._mock_repo.save(
            operation_id=operation_id,
            checkpoint_type=checkpoint_type,
            state=state,
            artifacts_path=str(artifacts_path) if artifacts_path else None,
            state_size_bytes=state_size_bytes,
            artifacts_size_bytes=artifacts_size_bytes,
        )

    async def load_checkpoint(
        self,
        operation_id: str,
        load_artifacts: bool = True,
    ) -> Optional[CheckpointData]:
        """Load checkpoint from in-memory repo and filesystem."""
        record = self._mock_repo.get(operation_id)
        if record is None:
            return None

        checkpoint = CheckpointData(
            operation_id=record["operation_id"],
            checkpoint_type=record["checkpoint_type"],
            created_at=record["created_at"],
            state=record["state"],
            artifacts_path=record["artifacts_path"],
        )

        if load_artifacts and record["artifacts_path"]:
            checkpoint.artifacts = await self._load_artifacts(
                record["artifacts_path"], operation_id
            )

        return checkpoint

    async def delete_checkpoint(self, operation_id: str) -> bool:
        """Delete checkpoint from in-memory repo and filesystem."""
        record = self._mock_repo.get(operation_id)
        if record is None:
            return False

        # Delete artifacts
        if record["artifacts_path"]:
            import shutil

            artifacts_path = Path(record["artifacts_path"])
            if artifacts_path.exists():
                shutil.rmtree(artifacts_path, ignore_errors=True)

        return self._mock_repo.delete(operation_id)


@pytest.fixture
def temp_artifacts_dir(tmp_path):
    """Create a temporary artifacts directory."""
    artifacts_dir = tmp_path / "checkpoints"
    artifacts_dir.mkdir()
    return artifacts_dir


@pytest.fixture
def checkpoint_service(temp_artifacts_dir):
    """Create IntegrationCheckpointService with temp directory."""
    return IntegrationCheckpointService(artifacts_dir=str(temp_artifacts_dir))


@pytest.fixture
def checkpoint_policy():
    """Create CheckpointPolicy with short intervals for testing."""
    return CheckpointPolicy(
        unit_interval=2,  # Checkpoint every 2 epochs
        time_interval_seconds=3600,  # Disable time-based (1 hour)
    )


# ============================================================================
# Test: Periodic Checkpoint
# ============================================================================


class TestM3PeriodicCheckpoint:
    """Integration tests for periodic checkpoint saving."""

    @pytest.mark.asyncio
    async def test_periodic_checkpoint_saves_state_to_db(
        self, checkpoint_service, checkpoint_policy, temp_artifacts_dir
    ):
        """Test that periodic checkpoints save state to database.

        Simulates training loop with periodic checkpoint saves.
        """
        operation_id = "op_training_123"

        # Simulate training epochs
        for epoch in range(5):
            if checkpoint_policy.should_checkpoint(epoch):
                state = TrainingCheckpointState(
                    epoch=epoch,
                    train_loss=1.0 - epoch * 0.1,
                    val_loss=1.1 - epoch * 0.1,
                    learning_rate=0.001,
                    training_history={
                        "train_loss": [1.0 - i * 0.1 for i in range(epoch + 1)],
                        "val_loss": [1.1 - i * 0.1 for i in range(epoch + 1)],
                    },
                    original_request={"symbol": "EURUSD", "timeframe": "1h"},
                )

                # Create sample artifacts
                artifacts = {
                    "model.pt": b"mock_model_weights_" + str(epoch).encode(),
                    "optimizer.pt": b"mock_optimizer_state_" + str(epoch).encode(),
                }

                await checkpoint_service.save_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type="periodic",
                    state=state.to_dict(),
                    artifacts=artifacts,
                )
                checkpoint_policy.record_checkpoint(epoch)

        # Verify checkpoint was saved (should have checkpointed at epochs 2, 4)
        record = checkpoint_service._mock_repo.get(operation_id)
        assert record is not None
        assert record["checkpoint_type"] == "periodic"
        assert record["state"]["epoch"] == 4  # Last checkpoint at epoch 4

    @pytest.mark.asyncio
    async def test_periodic_checkpoint_saves_artifacts_to_filesystem(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that periodic checkpoints save artifacts to filesystem."""
        operation_id = "op_training_456"

        artifacts = {
            "model.pt": b"model_weights_data_for_testing",
            "optimizer.pt": b"optimizer_state_data_for_testing",
        }

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 10, "train_loss": 0.5},
            artifacts=artifacts,
        )

        # Verify artifacts exist on filesystem
        artifact_path = temp_artifacts_dir / operation_id
        assert artifact_path.exists()
        assert (artifact_path / "model.pt").exists()
        assert (artifact_path / "optimizer.pt").exists()

        # Verify content
        assert (
            artifact_path / "model.pt"
        ).read_bytes() == b"model_weights_data_for_testing"

    @pytest.mark.asyncio
    async def test_periodic_checkpoint_overwrites_previous(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that new periodic checkpoints overwrite previous ones (UPSERT)."""
        operation_id = "op_training_789"

        # Save first checkpoint at epoch 5
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 5, "train_loss": 0.8},
            artifacts={"model.pt": b"epoch_5_weights"},
        )

        # Verify first checkpoint
        record = checkpoint_service._mock_repo.get(operation_id)
        assert record["state"]["epoch"] == 5

        # Save second checkpoint at epoch 10 (overwrites)
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 10, "train_loss": 0.4},
            artifacts={"model.pt": b"epoch_10_weights"},
        )

        # Verify second checkpoint replaced first
        record = checkpoint_service._mock_repo.get(operation_id)
        assert record["state"]["epoch"] == 10
        assert record["state"]["train_loss"] == 0.4

        # Verify only one checkpoint directory (not two)
        artifact_path = temp_artifacts_dir / operation_id
        assert (artifact_path / "model.pt").read_bytes() == b"epoch_10_weights"


# ============================================================================
# Test: Cancellation Checkpoint
# ============================================================================


class TestM3CancellationCheckpoint:
    """Integration tests for cancellation checkpoint saving."""

    @pytest.mark.asyncio
    async def test_cancellation_checkpoint_saves_on_cancel(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that cancellation checkpoint is saved when training is cancelled."""
        operation_id = "op_training_cancel_1"

        # Simulate training interrupted at epoch 7
        state = TrainingCheckpointState(
            epoch=7,
            train_loss=0.35,
            val_loss=0.40,
            learning_rate=0.001,
            training_history={
                "train_loss": [1.0, 0.8, 0.6, 0.5, 0.45, 0.4, 0.35],
                "val_loss": [1.1, 0.9, 0.7, 0.6, 0.55, 0.45, 0.40],
            },
        )

        artifacts = {
            "model.pt": b"model_at_cancellation",
            "optimizer.pt": b"optimizer_at_cancellation",
        }

        # Save cancellation checkpoint
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=artifacts,
        )

        # Verify checkpoint type is "cancellation"
        record = checkpoint_service._mock_repo.get(operation_id)
        assert record is not None
        assert record["checkpoint_type"] == "cancellation"
        assert record["state"]["epoch"] == 7

    @pytest.mark.asyncio
    async def test_cancellation_overwrites_periodic_checkpoint(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that cancellation checkpoint overwrites previous periodic checkpoint."""
        operation_id = "op_training_cancel_2"

        # Save periodic checkpoint at epoch 5
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 5, "train_loss": 0.5},
            artifacts={"model.pt": b"periodic_model"},
        )

        record = checkpoint_service._mock_repo.get(operation_id)
        assert record["checkpoint_type"] == "periodic"

        # Save cancellation checkpoint at epoch 8
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state={"epoch": 8, "train_loss": 0.35},
            artifacts={"model.pt": b"cancellation_model"},
        )

        # Verify checkpoint type updated to "cancellation"
        record = checkpoint_service._mock_repo.get(operation_id)
        assert record["checkpoint_type"] == "cancellation"
        assert record["state"]["epoch"] == 8

        # Verify artifacts updated
        artifact_path = temp_artifacts_dir / operation_id
        assert (artifact_path / "model.pt").read_bytes() == b"cancellation_model"


# ============================================================================
# Test: DB State Verification
# ============================================================================


class TestM3DBStateVerification:
    """Integration tests for verifying DB state after checkpoint saves."""

    @pytest.mark.asyncio
    async def test_checkpoint_state_contains_required_fields(self, checkpoint_service):
        """Test that checkpoint state contains all required training fields."""
        operation_id = "op_training_state_1"

        state = TrainingCheckpointState(
            epoch=15,
            train_loss=0.25,
            val_loss=0.28,
            train_accuracy=0.92,
            val_accuracy=0.90,
            learning_rate=0.0005,
            best_val_loss=0.27,
            training_history={
                "train_loss": [0.5, 0.4, 0.3, 0.25],
                "val_loss": [0.55, 0.42, 0.32, 0.28],
            },
            original_request={"symbol": "EURUSD", "epochs": 100},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state=state.to_dict(),
        )

        # Load and verify all fields present
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=False
        )

        assert checkpoint is not None
        assert checkpoint.state["epoch"] == 15
        assert checkpoint.state["train_loss"] == 0.25
        assert checkpoint.state["val_loss"] == 0.28
        assert checkpoint.state["train_accuracy"] == 0.92
        assert checkpoint.state["learning_rate"] == 0.0005
        assert checkpoint.state["best_val_loss"] == 0.27
        assert "train_loss" in checkpoint.state["training_history"]

    @pytest.mark.asyncio
    async def test_checkpoint_state_sizes_calculated(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that state and artifact sizes are calculated correctly."""
        operation_id = "op_training_state_2"

        state = {"epoch": 10, "train_loss": 0.5}
        artifacts = {
            "model.pt": b"a" * 1000,  # 1000 bytes
            "optimizer.pt": b"b" * 500,  # 500 bytes
        }

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state=state,
            artifacts=artifacts,
        )

        record = checkpoint_service._mock_repo.get(operation_id)
        assert record["artifacts_size_bytes"] == 1500
        assert record["state_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_checkpoint_timestamp_recorded(self, checkpoint_service):
        """Test that checkpoint creation timestamp is recorded."""
        operation_id = "op_training_state_3"

        before = datetime.now(timezone.utc)

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 5},
        )

        after = datetime.now(timezone.utc)

        record = checkpoint_service._mock_repo.get(operation_id)
        assert before <= record["created_at"] <= after


# ============================================================================
# Test: Filesystem Artifacts Verification
# ============================================================================


class TestM3FilesystemArtifactsVerification:
    """Integration tests for verifying filesystem artifacts."""

    @pytest.mark.asyncio
    async def test_artifacts_written_atomically(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that artifacts are written atomically (no partial writes)."""
        operation_id = "op_training_atomic_1"

        artifacts = {
            "model.pt": b"model_weights",
            "optimizer.pt": b"optimizer_state",
            "scheduler.pt": b"scheduler_state",
        }

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 10},
            artifacts=artifacts,
        )

        # Verify all files present
        artifact_path = temp_artifacts_dir / operation_id
        assert (artifact_path / "model.pt").exists()
        assert (artifact_path / "optimizer.pt").exists()
        assert (artifact_path / "scheduler.pt").exists()

        # Verify no temp directory left behind
        temp_path = temp_artifacts_dir / f"{operation_id}.tmp"
        assert not temp_path.exists()

    @pytest.mark.asyncio
    async def test_artifacts_can_be_loaded(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that saved artifacts can be loaded correctly."""
        operation_id = "op_training_load_1"

        original_artifacts = {
            "model.pt": b"original_model_weights_12345",
            "optimizer.pt": b"original_optimizer_state_67890",
        }

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 10},
            artifacts=original_artifacts,
        )

        # Load and verify artifacts match
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )

        assert checkpoint is not None
        assert checkpoint.artifacts is not None
        assert checkpoint.artifacts["model.pt"] == b"original_model_weights_12345"
        assert checkpoint.artifacts["optimizer.pt"] == b"original_optimizer_state_67890"

    @pytest.mark.asyncio
    async def test_artifacts_deleted_with_checkpoint(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that artifacts are deleted when checkpoint is deleted."""
        operation_id = "op_training_delete_1"

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 10},
            artifacts={"model.pt": b"to_be_deleted"},
        )

        artifact_path = temp_artifacts_dir / operation_id
        assert artifact_path.exists()

        # Delete checkpoint
        result = await checkpoint_service.delete_checkpoint(operation_id)
        assert result is True

        # Verify artifacts deleted
        assert not artifact_path.exists()

    @pytest.mark.asyncio
    async def test_artifacts_overwritten_on_upsert(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that old artifacts are replaced on checkpoint update."""
        operation_id = "op_training_upsert_1"

        # Save initial checkpoint with extra file
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 5},
            artifacts={
                "model.pt": b"old_model",
                "old_file.pt": b"should_be_removed",
            },
        )

        artifact_path = temp_artifacts_dir / operation_id
        assert (artifact_path / "old_file.pt").exists()

        # Update checkpoint with new artifacts (no old_file.pt)
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 10},
            artifacts={"model.pt": b"new_model"},
        )

        # Verify old artifacts removed, new artifacts present
        assert (artifact_path / "model.pt").read_bytes() == b"new_model"
        assert not (artifact_path / "old_file.pt").exists()


# ============================================================================
# Test: Full M3 Flow Integration
# ============================================================================


class TestM3FullFlow:
    """Full M3 scenario test combining all components."""

    @pytest.mark.asyncio
    async def test_full_training_checkpoint_flow(
        self, checkpoint_service, checkpoint_policy, temp_artifacts_dir
    ):
        """
        Test the complete M3 training checkpoint flow:
        1. Training starts, periodic checkpoints are saved
        2. Verify checkpoint state in DB
        3. Verify artifacts on filesystem
        4. Training is cancelled
        5. Cancellation checkpoint is saved
        6. Verify checkpoint type is updated
        """
        operation_id = "op_training_full_flow"

        # Step 1: Simulate training with periodic checkpoints
        checkpoints_saved = 0
        for epoch in range(10):
            # Simulate training epoch
            train_loss = 1.0 - epoch * 0.05
            val_loss = 1.1 - epoch * 0.05

            # Check if we should checkpoint
            if checkpoint_policy.should_checkpoint(epoch):
                state = TrainingCheckpointState(
                    epoch=epoch,
                    train_loss=train_loss,
                    val_loss=val_loss,
                    learning_rate=0.001,
                    training_history={
                        "train_loss": [1.0 - i * 0.05 for i in range(epoch + 1)],
                    },
                )

                await checkpoint_service.save_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type="periodic",
                    state=state.to_dict(),
                    artifacts={
                        "model.pt": f"model_epoch_{epoch}".encode(),
                        "optimizer.pt": f"optimizer_epoch_{epoch}".encode(),
                    },
                )
                checkpoint_policy.record_checkpoint(epoch)
                checkpoints_saved += 1

        # Verify periodic checkpoints were saved
        assert checkpoints_saved >= 1

        # Step 2: Verify checkpoint state in DB
        record = checkpoint_service._mock_repo.get(operation_id)
        assert record is not None
        assert record["checkpoint_type"] == "periodic"
        # Verify epoch was recorded (should be from one of the checkpoint epochs)
        assert record["state"]["epoch"] >= 0

        # Step 3: Verify artifacts on filesystem
        artifact_path = temp_artifacts_dir / operation_id
        assert artifact_path.exists()
        assert (artifact_path / "model.pt").exists()

        # Step 4 & 5: Training cancelled, save cancellation checkpoint
        cancellation_epoch = 8  # Cancelled during epoch 8
        cancellation_state = TrainingCheckpointState(
            epoch=cancellation_epoch,
            train_loss=0.60,
            val_loss=0.65,
            learning_rate=0.001,
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=cancellation_state.to_dict(),
            artifacts={
                "model.pt": b"model_at_cancellation",
                "optimizer.pt": b"optimizer_at_cancellation",
            },
        )

        # Step 6: Verify checkpoint type is updated
        record = checkpoint_service._mock_repo.get(operation_id)
        assert record["checkpoint_type"] == "cancellation"
        assert record["state"]["epoch"] == cancellation_epoch

        # Verify artifacts updated
        assert (artifact_path / "model.pt").read_bytes() == b"model_at_cancellation"

    @pytest.mark.asyncio
    async def test_failure_checkpoint_flow(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that failure checkpoints are saved correctly on exception."""
        operation_id = "op_training_failure"

        # Simulate training that fails at epoch 3
        failure_state = TrainingCheckpointState(
            epoch=3,
            train_loss=0.8,
            val_loss=0.85,
            learning_rate=0.001,
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=failure_state.to_dict(),
            artifacts={"model.pt": b"model_at_failure"},
        )

        # Verify failure checkpoint saved
        record = checkpoint_service._mock_repo.get(operation_id)
        assert record["checkpoint_type"] == "failure"
        assert record["state"]["epoch"] == 3

    @pytest.mark.asyncio
    async def test_successful_completion_deletes_checkpoint(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that successful training completion deletes the checkpoint."""
        operation_id = "op_training_success"

        # Save a periodic checkpoint during training
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 50, "train_loss": 0.1},
            artifacts={"model.pt": b"good_model"},
        )

        # Verify checkpoint exists
        assert checkpoint_service._mock_repo.get(operation_id) is not None
        artifact_path = temp_artifacts_dir / operation_id
        assert artifact_path.exists()

        # Training completes successfully, delete checkpoint
        result = await checkpoint_service.delete_checkpoint(operation_id)
        assert result is True

        # Verify checkpoint deleted
        assert checkpoint_service._mock_repo.get(operation_id) is None
        assert not artifact_path.exists()


# ============================================================================
# Test: Checkpoint Policy Integration
# ============================================================================


class TestM3CheckpointPolicyIntegration:
    """Integration tests for CheckpointPolicy with CheckpointService."""

    @pytest.mark.asyncio
    async def test_policy_triggers_at_unit_interval(self):
        """Test that policy triggers checkpoints at the correct unit intervals."""
        policy = CheckpointPolicy(unit_interval=5, time_interval_seconds=3600)

        triggered_epochs = []
        for epoch in range(20):
            if policy.should_checkpoint(epoch):
                triggered_epochs.append(epoch)
                policy.record_checkpoint(epoch)

        # Should trigger at epochs 5, 10, 15 (not 0, 20)
        assert triggered_epochs == [5, 10, 15]

    @pytest.mark.asyncio
    async def test_force_flag_always_triggers(self):
        """Test that force=True always triggers checkpoint."""
        policy = CheckpointPolicy(unit_interval=100, time_interval_seconds=3600)

        # Even at epoch 0 with high interval, force should trigger
        assert policy.should_checkpoint(0, force=True)
        assert policy.should_checkpoint(1, force=True)
        assert policy.should_checkpoint(50, force=True)

    @pytest.mark.asyncio
    async def test_policy_state_persists_across_checks(self):
        """Test that policy correctly tracks last checkpoint state."""
        policy = CheckpointPolicy(unit_interval=3, time_interval_seconds=3600)

        # Trigger at epoch 3
        assert policy.should_checkpoint(3)
        policy.record_checkpoint(3)

        # Should not trigger at 4, 5
        assert not policy.should_checkpoint(4)
        assert not policy.should_checkpoint(5)

        # Should trigger at 6 (3 epochs since last)
        assert policy.should_checkpoint(6)
