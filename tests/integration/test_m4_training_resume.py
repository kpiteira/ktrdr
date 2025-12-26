"""Integration tests for M4: Training Resume.

This test suite verifies the complete M4 training resume flow:
1. Start training, wait for checkpoint
2. Cancel training
3. Resume training from checkpoint
4. Verify training continues from correct epoch
5. Verify checkpoint deleted after completion
6. Verify final model is valid

Note: Uses mocked DB/checkpoint services for fast feedback.
For real Docker-based tests, see tests/e2e/container/
"""

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

import pytest
import torch
import torch.nn as nn

from ktrdr.checkpoint.checkpoint_policy import CheckpointPolicy
from ktrdr.checkpoint.checkpoint_service import CheckpointData
from ktrdr.checkpoint.schemas import TrainingCheckpointState
from ktrdr.training.checkpoint_restore import TrainingResumeContext

# ============================================================================
# Test Infrastructure: In-Memory Services
# ============================================================================


class MockCheckpointRepository:
    """In-memory checkpoint repository for integration testing."""

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

    def exists(self, operation_id: str) -> bool:
        """Check if checkpoint exists."""
        return operation_id in self.checkpoints


class MockOperationsRepository:
    """In-memory operations repository for integration testing."""

    def __init__(self):
        self.operations: dict[str, dict] = {}

    async def create(
        self,
        operation_id: str,
        operation_type: str,
        status: str = "pending",
    ) -> dict:
        """Create a new operation."""
        self.operations[operation_id] = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "status": status,
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "completed_at": None,
            "progress_percent": 0,
            "error_message": None,
        }
        return self.operations[operation_id]

    async def try_resume(self, operation_id: str) -> bool:
        """Atomically update status to RUNNING if resumable."""
        op = self.operations.get(operation_id)
        if op and op["status"] in ("cancelled", "failed"):
            op["status"] = "running"
            op["started_at"] = datetime.now(timezone.utc)
            op["completed_at"] = None
            op["error_message"] = None
            return True
        return False

    async def update_status(
        self,
        operation_id: str,
        status: str,
        progress_percent: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update operation status."""
        op = self.operations.get(operation_id)
        if op:
            op["status"] = status
            if progress_percent is not None:
                op["progress_percent"] = progress_percent
            if error_message is not None:
                op["error_message"] = error_message
            if status in ("completed", "failed", "cancelled"):
                op["completed_at"] = datetime.now(timezone.utc)

    def get(self, operation_id: str) -> Optional[dict]:
        """Get operation record."""
        return self.operations.get(operation_id)


class IntegrationCheckpointService:
    """Checkpoint service with in-memory repository for testing."""

    def __init__(self, artifacts_dir: Path):
        self._mock_repo = MockCheckpointRepository()
        self._artifacts_dir = artifacts_dir

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
        import shutil

        record = self._mock_repo.get(operation_id)
        if record is None:
            return False

        # Delete artifacts
        if record["artifacts_path"]:
            artifacts_path = Path(record["artifacts_path"])
            if artifacts_path.exists():
                shutil.rmtree(artifacts_path, ignore_errors=True)

        return self._mock_repo.delete(operation_id)

    def checkpoint_exists(self, operation_id: str) -> bool:
        """Check if checkpoint exists."""
        return self._mock_repo.exists(operation_id)

    async def _write_artifacts(
        self, operation_id: str, artifacts: dict[str, bytes]
    ) -> Path:
        """Write artifacts to filesystem."""
        import shutil

        artifact_dir = self._artifacts_dir / operation_id

        # Remove existing artifacts (atomic overwrite via temp dir)
        temp_dir = self._artifacts_dir / f"{operation_id}.tmp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True)

        # Write all artifacts
        for name, data in artifacts.items():
            (temp_dir / name).write_bytes(data)

        # Atomic rename
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        temp_dir.rename(artifact_dir)

        return artifact_dir

    async def _load_artifacts(
        self, artifacts_path: str, operation_id: str
    ) -> dict[str, bytes]:
        """Load artifacts from filesystem."""
        artifact_dir = Path(artifacts_path)
        artifacts = {}
        if artifact_dir.exists():
            for file_path in artifact_dir.iterdir():
                if file_path.is_file():
                    artifacts[file_path.name] = file_path.read_bytes()
        return artifacts


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_artifacts_dir(tmp_path):
    """Create a temporary artifacts directory."""
    artifacts_dir = tmp_path / "checkpoints"
    artifacts_dir.mkdir()
    return artifacts_dir


@pytest.fixture
def checkpoint_service(temp_artifacts_dir):
    """Create IntegrationCheckpointService with temp directory."""
    return IntegrationCheckpointService(artifacts_dir=temp_artifacts_dir)


@pytest.fixture
def operations_repo():
    """Create MockOperationsRepository."""
    return MockOperationsRepository()


@pytest.fixture
def checkpoint_policy():
    """Create CheckpointPolicy with short intervals for testing."""
    return CheckpointPolicy(
        unit_interval=2,  # Checkpoint every 2 epochs
        time_interval_seconds=3600,  # Disable time-based
    )


def create_model_artifacts(
    epoch: int, train_loss: float = 0.5
) -> tuple[dict[str, bytes], nn.Module]:
    """Create model artifacts for a given epoch.

    Returns:
        Tuple of (artifacts dict, model instance)
    """
    model = nn.Linear(10, 3)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # Simulate some training to populate optimizer state
    X = torch.randn(16, 10)
    y = torch.randint(0, 3, (16,))
    criterion = nn.CrossEntropyLoss()

    for _ in range(epoch + 1):
        optimizer.zero_grad()
        outputs = model(X)
        loss = criterion(outputs, y)
        loss.backward()
        optimizer.step()

    # Serialize model and optimizer
    model_buffer = BytesIO()
    torch.save(model.state_dict(), model_buffer)

    optimizer_buffer = BytesIO()
    torch.save(optimizer.state_dict(), optimizer_buffer)

    artifacts = {
        "model.pt": model_buffer.getvalue(),
        "optimizer.pt": optimizer_buffer.getvalue(),
    }

    return artifacts, model


# ============================================================================
# Test: Full Resume Flow
# ============================================================================


class TestM4FullResumeFlow:
    """Integration tests for the complete training resume flow."""

    @pytest.mark.asyncio
    async def test_full_resume_flow_start_cancel_resume_complete(
        self, checkpoint_service, operations_repo, checkpoint_policy, temp_artifacts_dir
    ):
        """
        Test the complete M4 training resume flow:
        1. Start training, periodic checkpoints are saved
        2. Cancel training
        3. Verify checkpoint exists
        4. Resume training
        5. Verify training continues from correct epoch
        6. Complete training
        7. Verify checkpoint deleted
        """
        operation_id = "op_training_full_resume_flow"

        # Step 1: Create operation
        await operations_repo.create(operation_id, "training", status="running")

        # Step 2: Simulate training with periodic checkpoints
        total_epochs = 10
        cancel_at_epoch = 6

        for epoch in range(cancel_at_epoch + 1):
            train_loss = 1.0 - epoch * 0.05
            val_loss = 1.1 - epoch * 0.05

            # Update progress
            progress = int((epoch / total_epochs) * 100)
            await operations_repo.update_status(
                operation_id, "running", progress_percent=progress
            )

            # Check if we should checkpoint
            if checkpoint_policy.should_checkpoint(epoch):
                artifacts, _ = create_model_artifacts(epoch, train_loss)
                state = TrainingCheckpointState(
                    epoch=epoch,
                    train_loss=train_loss,
                    val_loss=val_loss,
                    learning_rate=0.001,
                    training_history={
                        "train_loss": [1.0 - i * 0.05 for i in range(epoch + 1)],
                        "val_loss": [1.1 - i * 0.05 for i in range(epoch + 1)],
                    },
                    original_request={"symbol": "EURUSD", "epochs": total_epochs},
                )

                await checkpoint_service.save_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type="periodic",
                    state=state.to_dict(),
                    artifacts=artifacts,
                )
                checkpoint_policy.record_checkpoint(epoch)

        # Step 3: Cancel training (simulate user cancellation at epoch 6)
        cancel_state = TrainingCheckpointState(
            epoch=cancel_at_epoch,
            train_loss=1.0 - cancel_at_epoch * 0.05,
            val_loss=1.1 - cancel_at_epoch * 0.05,
            learning_rate=0.001,
            training_history={
                "train_loss": [1.0 - i * 0.05 for i in range(cancel_at_epoch + 1)],
            },
        )
        cancel_artifacts, _ = create_model_artifacts(cancel_at_epoch)

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=cancel_state.to_dict(),
            artifacts=cancel_artifacts,
        )
        await operations_repo.update_status(operation_id, "cancelled")

        # Step 4: Verify checkpoint exists
        assert checkpoint_service.checkpoint_exists(operation_id)
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None
        assert checkpoint.state["epoch"] == cancel_at_epoch
        assert checkpoint.checkpoint_type == "cancellation"

        # Step 5: Resume training
        resume_success = await operations_repo.try_resume(operation_id)
        assert resume_success is True

        op = operations_repo.get(operation_id)
        assert op["status"] == "running"

        # Load checkpoint for resume context
        resume_checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )
        assert resume_checkpoint is not None
        assert resume_checkpoint.artifacts is not None

        # Create resume context (per design D7: start from checkpoint_epoch + 1)
        resume_context = TrainingResumeContext(
            start_epoch=resume_checkpoint.state["epoch"] + 1,
            model_weights=resume_checkpoint.artifacts["model.pt"],
            optimizer_state=resume_checkpoint.artifacts["optimizer.pt"],
            training_history=resume_checkpoint.state.get("training_history", {}),
            best_val_loss=resume_checkpoint.state.get("best_val_loss", float("inf")),
        )

        # Verify start epoch is correct (checkpoint was at 6, resume from 7)
        assert resume_context.start_epoch == cancel_at_epoch + 1

        # Step 6: Simulate resumed training from epoch 7 to 9 (epochs 7, 8, 9)
        for epoch in range(resume_context.start_epoch, total_epochs):
            progress = int((epoch / total_epochs) * 100)
            await operations_repo.update_status(
                operation_id, "running", progress_percent=progress
            )

        # Step 7: Complete training
        await operations_repo.update_status(
            operation_id, "completed", progress_percent=100
        )

        # Step 8: Delete checkpoint after completion
        deleted = await checkpoint_service.delete_checkpoint(operation_id)
        assert deleted is True

        # Verify checkpoint is gone
        assert not checkpoint_service.checkpoint_exists(operation_id)

        # Verify operation is completed
        final_op = operations_repo.get(operation_id)
        assert final_op["status"] == "completed"
        assert final_op["progress_percent"] == 100


# ============================================================================
# Test: Resume From Correct Epoch
# ============================================================================


class TestM4ResumeFromCorrectEpoch:
    """Tests for verifying training resumes from the correct epoch."""

    @pytest.mark.asyncio
    async def test_resume_starts_from_checkpoint_epoch_plus_one(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Per design D7: Resume starts from checkpoint_epoch + 1."""
        operation_id = "op_resume_epoch_test"

        # Save checkpoint at epoch 25
        checkpoint_epoch = 25
        artifacts, _ = create_model_artifacts(checkpoint_epoch)
        state = TrainingCheckpointState(
            epoch=checkpoint_epoch,
            train_loss=0.5,
            val_loss=0.55,
            learning_rate=0.001,
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=artifacts,
        )

        # Load checkpoint and create resume context
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )

        resume_context = TrainingResumeContext(
            start_epoch=checkpoint.state["epoch"] + 1,
            model_weights=checkpoint.artifacts["model.pt"],
            optimizer_state=checkpoint.artifacts["optimizer.pt"],
        )

        # Verify start epoch is checkpoint_epoch + 1
        assert resume_context.start_epoch == checkpoint_epoch + 1
        assert resume_context.start_epoch == 26

    @pytest.mark.asyncio
    async def test_resume_from_epoch_zero_checkpoint(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test resume from a checkpoint at epoch 0."""
        operation_id = "op_resume_epoch_zero"

        artifacts, _ = create_model_artifacts(0)
        state = TrainingCheckpointState(
            epoch=0,
            train_loss=1.0,
            val_loss=1.1,
            learning_rate=0.001,
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=state.to_dict(),
            artifacts=artifacts,
        )

        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )

        resume_context = TrainingResumeContext(
            start_epoch=checkpoint.state["epoch"] + 1,
            model_weights=checkpoint.artifacts["model.pt"],
            optimizer_state=checkpoint.artifacts["optimizer.pt"],
        )

        # Resume from epoch 1
        assert resume_context.start_epoch == 1

    @pytest.mark.asyncio
    async def test_training_history_preserved_on_resume(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that training history from prior epochs is preserved."""
        operation_id = "op_resume_history"

        # Checkpoint at epoch 10 with full training history
        checkpoint_epoch = 10
        training_history = {
            "train_loss": [1.0 - i * 0.05 for i in range(checkpoint_epoch + 1)],
            "val_loss": [1.1 - i * 0.05 for i in range(checkpoint_epoch + 1)],
        }

        artifacts, _ = create_model_artifacts(checkpoint_epoch)
        state = TrainingCheckpointState(
            epoch=checkpoint_epoch,
            train_loss=training_history["train_loss"][-1],
            val_loss=training_history["val_loss"][-1],
            learning_rate=0.001,
            training_history=training_history,
            best_val_loss=min(training_history["val_loss"]),
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=artifacts,
        )

        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )

        resume_context = TrainingResumeContext(
            start_epoch=checkpoint.state["epoch"] + 1,
            model_weights=checkpoint.artifacts["model.pt"],
            optimizer_state=checkpoint.artifacts["optimizer.pt"],
            training_history=checkpoint.state.get("training_history", {}),
            best_val_loss=checkpoint.state.get("best_val_loss", float("inf")),
        )

        # Verify training history is preserved
        assert len(resume_context.training_history["train_loss"]) == 11
        assert len(resume_context.training_history["val_loss"]) == 11
        assert resume_context.best_val_loss == min(training_history["val_loss"])


# ============================================================================
# Test: Checkpoint Cleanup After Completion
# ============================================================================


class TestM4CheckpointCleanup:
    """Tests for checkpoint deletion after successful completion."""

    @pytest.mark.asyncio
    async def test_checkpoint_deleted_after_successful_completion(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that checkpoint is deleted after training completes successfully."""
        operation_id = "op_cleanup_success"

        # Save a checkpoint
        artifacts, _ = create_model_artifacts(5)
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state={"epoch": 5, "train_loss": 0.5},
            artifacts=artifacts,
        )

        # Verify checkpoint exists
        assert checkpoint_service.checkpoint_exists(operation_id)

        # Simulate successful completion - delete checkpoint
        deleted = await checkpoint_service.delete_checkpoint(operation_id)

        # Verify deletion
        assert deleted is True
        assert not checkpoint_service.checkpoint_exists(operation_id)

        # Verify artifacts are deleted from filesystem
        artifact_path = temp_artifacts_dir / operation_id
        assert not artifact_path.exists()

    @pytest.mark.asyncio
    async def test_checkpoint_preserved_on_resume_failure(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Per design D6: Checkpoint preserved if resume fails."""
        operation_id = "op_resume_failure"

        # Save checkpoint
        artifacts, _ = create_model_artifacts(10)
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state={"epoch": 10, "train_loss": 0.4},
            artifacts=artifacts,
        )

        # Simulate resume attempt that fails (don't delete checkpoint)
        # Just verify checkpoint is still there

        assert checkpoint_service.checkpoint_exists(operation_id)

        # Load and verify still valid
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )
        assert checkpoint is not None
        assert checkpoint.state["epoch"] == 10

    @pytest.mark.asyncio
    async def test_delete_nonexistent_checkpoint_returns_false(
        self, checkpoint_service
    ):
        """Test that deleting a non-existent checkpoint returns False."""
        result = await checkpoint_service.delete_checkpoint("nonexistent_op")
        assert result is False


# ============================================================================
# Test: Model Validity After Resume
# ============================================================================


class TestM4ModelValidityAfterResume:
    """Tests for verifying model validity after resume."""

    @pytest.mark.asyncio
    async def test_model_weights_loadable_after_resume(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that model weights from checkpoint can be loaded into a model."""
        operation_id = "op_model_validity"

        # Create a known model state
        original_model = nn.Linear(10, 3)
        with torch.no_grad():
            original_model.weight.fill_(0.5)
            original_model.bias.fill_(0.1)

        # Serialize
        model_buffer = BytesIO()
        torch.save(original_model.state_dict(), model_buffer)

        optimizer = torch.optim.Adam(original_model.parameters())
        optimizer_buffer = BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        artifacts = {
            "model.pt": model_buffer.getvalue(),
            "optimizer.pt": optimizer_buffer.getvalue(),
        }

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state={"epoch": 5, "train_loss": 0.5},
            artifacts=artifacts,
        )

        # Load checkpoint
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )

        # Create a new model and load weights
        new_model = nn.Linear(10, 3)
        state_dict = torch.load(BytesIO(checkpoint.artifacts["model.pt"]))
        new_model.load_state_dict(state_dict)

        # Verify weights match
        assert torch.allclose(new_model.weight, original_model.weight)
        assert torch.allclose(new_model.bias, original_model.bias)

    @pytest.mark.asyncio
    async def test_optimizer_state_loadable_after_resume(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that optimizer state from checkpoint can be loaded."""
        operation_id = "op_optimizer_validity"

        # Create model and optimizer with state
        model = nn.Linear(10, 3)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

        # Train a bit to populate optimizer state
        X = torch.randn(16, 10)
        y = torch.randint(0, 3, (16,))
        criterion = nn.CrossEntropyLoss()

        for _ in range(5):
            optimizer.zero_grad()
            loss = criterion(model(X), y)
            loss.backward()
            optimizer.step()

        # Capture optimizer state
        model_buffer = BytesIO()
        torch.save(model.state_dict(), model_buffer)

        optimizer_buffer = BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        artifacts = {
            "model.pt": model_buffer.getvalue(),
            "optimizer.pt": optimizer_buffer.getvalue(),
        }

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state={"epoch": 5},
            artifacts=artifacts,
        )

        # Load checkpoint
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )

        # Create new model and optimizer, load state
        new_model = nn.Linear(10, 3)
        new_model.load_state_dict(torch.load(BytesIO(checkpoint.artifacts["model.pt"])))

        new_optimizer = torch.optim.Adam(new_model.parameters(), lr=0.001)
        new_optimizer.load_state_dict(
            torch.load(BytesIO(checkpoint.artifacts["optimizer.pt"]))
        )

        # Verify optimizer has populated state (momentum buffers, etc.)
        assert len(new_optimizer.state) > 0

    @pytest.mark.asyncio
    async def test_resumed_model_produces_valid_predictions(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that a model restored from checkpoint produces valid predictions."""
        operation_id = "op_model_predictions"

        # Create and train a model
        original_model = nn.Linear(10, 3)
        optimizer = torch.optim.Adam(original_model.parameters())
        criterion = nn.CrossEntropyLoss()

        X = torch.randn(32, 10)
        y = torch.randint(0, 3, (32,))

        for _ in range(5):
            optimizer.zero_grad()
            loss = criterion(original_model(X), y)
            loss.backward()
            optimizer.step()

        # Get original predictions
        original_model.eval()
        with torch.no_grad():
            original_predictions = original_model(X)

        # Save checkpoint
        model_buffer = BytesIO()
        torch.save(original_model.state_dict(), model_buffer)

        optimizer_buffer = BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state={"epoch": 5},
            artifacts={
                "model.pt": model_buffer.getvalue(),
                "optimizer.pt": optimizer_buffer.getvalue(),
            },
        )

        # Load and restore
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )

        restored_model = nn.Linear(10, 3)
        restored_model.load_state_dict(
            torch.load(BytesIO(checkpoint.artifacts["model.pt"]))
        )

        # Verify predictions match
        restored_model.eval()
        with torch.no_grad():
            restored_predictions = restored_model(X)

        assert torch.allclose(original_predictions, restored_predictions)


# ============================================================================
# Test: Edge Cases
# ============================================================================


class TestM4EdgeCases:
    """Tests for edge cases in the resume flow."""

    @pytest.mark.asyncio
    async def test_resume_already_running_operation_fails(self, operations_repo):
        """Test that resuming an already running operation fails."""
        operation_id = "op_already_running"

        await operations_repo.create(operation_id, "training", status="running")

        # Try to resume - should fail
        result = await operations_repo.try_resume(operation_id)
        assert result is False

        # Status should still be running
        op = operations_repo.get(operation_id)
        assert op["status"] == "running"

    @pytest.mark.asyncio
    async def test_resume_completed_operation_fails(self, operations_repo):
        """Test that resuming a completed operation fails."""
        operation_id = "op_completed"

        await operations_repo.create(operation_id, "training", status="completed")

        result = await operations_repo.try_resume(operation_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_cancelled_operation_succeeds(self, operations_repo):
        """Test that resuming a cancelled operation succeeds."""
        operation_id = "op_cancelled"

        await operations_repo.create(operation_id, "training", status="cancelled")

        result = await operations_repo.try_resume(operation_id)
        assert result is True

        op = operations_repo.get(operation_id)
        assert op["status"] == "running"

    @pytest.mark.asyncio
    async def test_resume_failed_operation_succeeds(self, operations_repo):
        """Test that resuming a failed operation succeeds."""
        operation_id = "op_failed"

        await operations_repo.create(operation_id, "training", status="failed")

        result = await operations_repo.try_resume(operation_id)
        assert result is True

        op = operations_repo.get(operation_id)
        assert op["status"] == "running"

    @pytest.mark.asyncio
    async def test_resume_without_checkpoint_is_detectable(
        self, checkpoint_service, operations_repo
    ):
        """Test that attempting to resume without a checkpoint is detectable."""
        operation_id = "op_no_checkpoint"

        await operations_repo.create(operation_id, "training", status="cancelled")

        # Resume succeeds at operation level
        result = await operations_repo.try_resume(operation_id)
        assert result is True

        # But checkpoint doesn't exist
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is None

        # Caller should detect this and fail appropriately
        assert not checkpoint_service.checkpoint_exists(operation_id)


# ============================================================================
# Test: TrainingResumeContext Integration
# ============================================================================


class TestM4ResumeContextIntegration:
    """Tests for TrainingResumeContext creation and validation."""

    @pytest.mark.asyncio
    async def test_resume_context_created_from_checkpoint(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test that TrainingResumeContext is correctly created from checkpoint."""
        operation_id = "op_resume_context"

        # Save checkpoint with all fields
        artifacts, _ = create_model_artifacts(15)
        training_history = {
            "train_loss": [1.0 - i * 0.03 for i in range(16)],
            "val_loss": [1.1 - i * 0.03 for i in range(16)],
        }

        state = TrainingCheckpointState(
            epoch=15,
            train_loss=training_history["train_loss"][-1],
            val_loss=training_history["val_loss"][-1],
            learning_rate=0.0005,
            training_history=training_history,
            best_val_loss=min(training_history["val_loss"]),
            original_request={"symbol": "EURUSD", "epochs": 50},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=artifacts,
        )

        # Load and create resume context
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )

        resume_context = TrainingResumeContext(
            start_epoch=checkpoint.state["epoch"] + 1,
            model_weights=checkpoint.artifacts["model.pt"],
            optimizer_state=checkpoint.artifacts["optimizer.pt"],
            training_history=checkpoint.state.get("training_history", {}),
            best_val_loss=checkpoint.state.get("best_val_loss", float("inf")),
            original_request=checkpoint.state.get("original_request", {}),
        )

        # Verify all fields
        assert resume_context.start_epoch == 16
        assert resume_context.model_weights is not None
        assert resume_context.optimizer_state is not None
        assert len(resume_context.training_history["train_loss"]) == 16
        assert resume_context.best_val_loss == min(training_history["val_loss"])
        assert resume_context.original_request["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_resume_context_with_scheduler_state(
        self, checkpoint_service, temp_artifacts_dir
    ):
        """Test resume context with optional scheduler state."""
        operation_id = "op_resume_scheduler"

        # Create model, optimizer, and scheduler
        model = nn.Linear(10, 3)
        optimizer = torch.optim.Adam(model.parameters())
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

        # Step scheduler
        for _ in range(10):
            scheduler.step()

        # Serialize all
        model_buffer = BytesIO()
        torch.save(model.state_dict(), model_buffer)

        optimizer_buffer = BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        scheduler_buffer = BytesIO()
        torch.save(scheduler.state_dict(), scheduler_buffer)

        artifacts = {
            "model.pt": model_buffer.getvalue(),
            "optimizer.pt": optimizer_buffer.getvalue(),
            "scheduler.pt": scheduler_buffer.getvalue(),
        }

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state={"epoch": 10},
            artifacts=artifacts,
        )

        # Load and create resume context
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )

        resume_context = TrainingResumeContext(
            start_epoch=checkpoint.state["epoch"] + 1,
            model_weights=checkpoint.artifacts["model.pt"],
            optimizer_state=checkpoint.artifacts["optimizer.pt"],
            scheduler_state=checkpoint.artifacts.get("scheduler.pt"),
        )

        # Verify scheduler state is present
        assert resume_context.scheduler_state is not None

        # Verify it can be loaded
        new_scheduler = torch.optim.lr_scheduler.StepLR(
            torch.optim.Adam(nn.Linear(10, 3).parameters()),
            step_size=5,
            gamma=0.1,
        )
        new_scheduler.load_state_dict(
            torch.load(BytesIO(resume_context.scheduler_state))
        )
        assert new_scheduler.last_epoch == 10
