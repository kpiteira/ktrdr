"""Integration tests for M6: Graceful Shutdown.

This test suite verifies the complete M6 graceful shutdown flow:
1. Start operation
2. Simulate SIGTERM (via shutdown event)
3. Verify checkpoint saved with type="shutdown"
4. Verify status updated to CANCELLED
5. Verify operation can be resumed

Note: Uses mocked services for fast feedback. Actual Docker stop
behavior is tested in e2e/container tests. The key is that we
test the same code paths that would execute during real SIGTERM.
"""

import asyncio
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
import torch
import torch.nn as nn

from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.checkpoint.schemas import TrainingCheckpointState
from ktrdr.training.checkpoint_restore import TrainingResumeContext
from ktrdr.workers.base import GracefulShutdownError, WorkerAPIBase

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
        artifacts_path: str | None,
        state_size_bytes: int,
        artifacts_size_bytes: int | None,
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

    def get(self, operation_id: str) -> dict | None:
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
        if op and op["status"].lower() in ("cancelled", "failed"):
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
        progress_percent: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update operation status."""
        op = self.operations.get(operation_id)
        if op:
            op["status"] = status
            if progress_percent is not None:
                op["progress_percent"] = progress_percent
            if error_message is not None:
                op["error_message"] = error_message
            if status.lower() in ("completed", "failed", "cancelled"):
                op["completed_at"] = datetime.now(timezone.utc)

    def get(self, operation_id: str) -> dict | None:
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
        artifacts: dict[str, bytes] | None = None,
    ) -> None:
        """Save checkpoint with both in-memory repo and filesystem."""
        import json
        import shutil

        artifacts_path: Path | None = None
        artifacts_size_bytes: int | None = None

        # Write artifacts if provided
        if artifacts:
            artifact_dir = self._artifacts_dir / operation_id
            temp_dir = self._artifacts_dir / f"{operation_id}.tmp"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True)

            for name, data in artifacts.items():
                (temp_dir / name).write_bytes(data)

            if artifact_dir.exists():
                shutil.rmtree(artifact_dir)
            temp_dir.rename(artifact_dir)

            artifacts_path = artifact_dir
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
    ) -> dict | None:
        """Load checkpoint from in-memory repo and filesystem."""
        record = self._mock_repo.get(operation_id)
        if record is None:
            return None

        result = {
            "operation_id": record["operation_id"],
            "checkpoint_type": record["checkpoint_type"],
            "created_at": record["created_at"],
            "state": record["state"],
            "artifacts_path": record["artifacts_path"],
            "artifacts": None,
        }

        if load_artifacts and record["artifacts_path"]:
            artifacts = {}
            artifact_dir = Path(record["artifacts_path"])
            if artifact_dir.exists():
                for file_path in artifact_dir.iterdir():
                    if file_path.is_file():
                        artifacts[file_path.name] = file_path.read_bytes()
            result["artifacts"] = artifacts

        return result

    def checkpoint_exists(self, operation_id: str) -> bool:
        """Check if checkpoint exists."""
        return self._mock_repo.exists(operation_id)

    async def delete_checkpoint(self, operation_id: str) -> bool:
        """Delete checkpoint from in-memory repo and filesystem."""
        import shutil

        record = self._mock_repo.get(operation_id)
        if record is None:
            return False

        if record["artifacts_path"]:
            artifacts_path = Path(record["artifacts_path"])
            if artifacts_path.exists():
                shutil.rmtree(artifacts_path, ignore_errors=True)

        return self._mock_repo.delete(operation_id)


# ============================================================================
# Test Infrastructure: Worker with Checkpoint Support
# ============================================================================


class GracefulShutdownTestWorker(WorkerAPIBase):
    """Worker that integrates with mock checkpoint/operations services."""

    def __init__(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: MockOperationsRepository,
    ):
        super().__init__(
            worker_type=WorkerType.TRAINING,
            operation_type=OperationType.TRAINING,
            worker_port=5002,
            backend_url="http://backend:8000",
        )
        self._checkpoint_service = checkpoint_service
        self._operations_repo = operations_repo
        self._current_state: dict = {}

    def set_current_state(self, state: dict) -> None:
        """Set the current training state for checkpoint saving."""
        self._current_state = state

    def set_current_artifacts(self, artifacts: dict[str, bytes]) -> None:
        """Set current artifacts for checkpoint saving."""
        self._current_artifacts = artifacts

    async def _save_checkpoint(self, operation_id: str, checkpoint_type: str) -> None:
        """Save checkpoint using the mock checkpoint service."""
        artifacts = getattr(self, "_current_artifacts", None)
        await self._checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type=checkpoint_type,
            state=self._current_state,
            artifacts=artifacts,
        )

    async def _update_operation_status(
        self,
        operation_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update operation status in mock repository."""
        await self._operations_repo.update_status(
            operation_id=operation_id,
            status=status,
            error_message=error_message,
        )


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_artifacts_dir(tmp_path: Path) -> Path:
    """Create a temporary artifacts directory."""
    artifacts_dir = tmp_path / "checkpoints"
    artifacts_dir.mkdir()
    return artifacts_dir


@pytest.fixture
def checkpoint_service(temp_artifacts_dir: Path) -> IntegrationCheckpointService:
    """Create IntegrationCheckpointService with temp directory."""
    return IntegrationCheckpointService(artifacts_dir=temp_artifacts_dir)


@pytest.fixture
def operations_repo() -> MockOperationsRepository:
    """Create MockOperationsRepository."""
    return MockOperationsRepository()


@pytest.fixture
def worker(
    checkpoint_service: IntegrationCheckpointService,
    operations_repo: MockOperationsRepository,
) -> GracefulShutdownTestWorker:
    """Create GracefulShutdownTestWorker with mock services."""
    return GracefulShutdownTestWorker(
        checkpoint_service=checkpoint_service,
        operations_repo=operations_repo,
    )


def create_model_artifacts(epoch: int) -> dict[str, bytes]:
    """Create model artifacts for a given epoch."""
    model = nn.Linear(10, 3)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # Simulate training
    X = torch.randn(16, 10)
    y = torch.randint(0, 3, (16,))
    criterion = nn.CrossEntropyLoss()

    for _ in range(epoch + 1):
        optimizer.zero_grad()
        outputs = model(X)
        loss = criterion(outputs, y)
        loss.backward()
        optimizer.step()

    # Serialize
    model_buffer = BytesIO()
    torch.save(model.state_dict(), model_buffer)

    optimizer_buffer = BytesIO()
    torch.save(optimizer.state_dict(), optimizer_buffer)

    return {
        "model.pt": model_buffer.getvalue(),
        "optimizer.pt": optimizer_buffer.getvalue(),
    }


# ============================================================================
# Test: Shutdown Saves Checkpoint
# ============================================================================


class TestM6ShutdownSavesCheckpoint:
    """Tests for checkpoint saving on graceful shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_during_operation_saves_checkpoint(
        self,
        worker: GracefulShutdownTestWorker,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: MockOperationsRepository,
    ):
        """
        Test that when shutdown occurs during operation:
        - Checkpoint is saved with type="shutdown"
        - State is preserved for later resume
        """
        operation_id = "op_shutdown_checkpoint_test"
        await operations_repo.create(operation_id, "training", status="running")

        # Set up current training state
        training_state = TrainingCheckpointState(
            epoch=15,
            train_loss=0.35,
            val_loss=0.40,
            learning_rate=0.001,
            training_history={
                "train_loss": [1.0 - i * 0.04 for i in range(16)],
                "val_loss": [1.1 - i * 0.04 for i in range(16)],
            },
        )
        worker.set_current_state(training_state.to_dict())
        worker.set_current_artifacts(create_model_artifacts(15))

        operation_started = asyncio.Event()

        async def long_operation() -> str:
            operation_started.set()
            await asyncio.sleep(10)  # Long operation
            return "completed"

        async def trigger_shutdown() -> None:
            await operation_started.wait()
            await asyncio.sleep(0.01)  # Small delay
            worker._shutdown_event.set()

        # Run operation and shutdown trigger concurrently
        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown(operation_id, long_operation())

        await shutdown_task

        # Verify checkpoint was saved
        assert checkpoint_service.checkpoint_exists(operation_id)

        # Verify checkpoint type is "shutdown"
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None
        assert checkpoint["checkpoint_type"] == "shutdown"

        # Verify state was preserved
        assert checkpoint["state"]["epoch"] == 15
        assert checkpoint["state"]["train_loss"] == 0.35

    @pytest.mark.asyncio
    async def test_shutdown_checkpoint_includes_artifacts(
        self,
        worker: GracefulShutdownTestWorker,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: MockOperationsRepository,
    ):
        """Test that shutdown checkpoint includes model artifacts."""
        operation_id = "op_shutdown_artifacts_test"
        await operations_repo.create(operation_id, "training", status="running")

        # Set up state with artifacts
        worker.set_current_state({"epoch": 10, "train_loss": 0.5})
        artifacts = create_model_artifacts(10)
        worker.set_current_artifacts(artifacts)

        operation_started = asyncio.Event()

        async def operation() -> str:
            operation_started.set()
            await asyncio.sleep(10)
            return "done"

        async def trigger_shutdown() -> None:
            await operation_started.wait()
            await asyncio.sleep(0.01)
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown(operation_id, operation())

        await shutdown_task

        # Load checkpoint with artifacts
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )
        assert checkpoint is not None
        assert checkpoint["artifacts"] is not None
        assert "model.pt" in checkpoint["artifacts"]
        assert "optimizer.pt" in checkpoint["artifacts"]


# ============================================================================
# Test: Shutdown Updates Status to CANCELLED
# ============================================================================


class TestM6ShutdownUpdatesStatus:
    """Tests for status update on graceful shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_sets_status_to_cancelled(
        self,
        worker: GracefulShutdownTestWorker,
        operations_repo: MockOperationsRepository,
    ):
        """
        Test that when shutdown occurs:
        - Operation status is updated to CANCELLED
        - Error message indicates shutdown
        """
        operation_id = "op_shutdown_status_test"
        await operations_repo.create(operation_id, "training", status="running")

        worker.set_current_state({"epoch": 5})

        operation_started = asyncio.Event()

        async def operation() -> str:
            operation_started.set()
            await asyncio.sleep(10)
            return "done"

        async def trigger_shutdown() -> None:
            await operation_started.wait()
            await asyncio.sleep(0.01)
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown(operation_id, operation())

        await shutdown_task

        # Verify status was updated to CANCELLED
        op = operations_repo.get(operation_id)
        assert op is not None
        assert op["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_shutdown_error_message_mentions_shutdown(
        self,
        worker: GracefulShutdownTestWorker,
        operations_repo: MockOperationsRepository,
    ):
        """Test that error message indicates graceful shutdown."""
        operation_id = "op_shutdown_message_test"
        await operations_repo.create(operation_id, "training", status="running")

        worker.set_current_state({"epoch": 3})

        operation_started = asyncio.Event()

        async def operation() -> str:
            operation_started.set()
            await asyncio.sleep(10)
            return "done"

        async def trigger_shutdown() -> None:
            await operation_started.wait()
            await asyncio.sleep(0.01)
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown(operation_id, operation())

        await shutdown_task

        op = operations_repo.get(operation_id)
        assert op is not None
        assert op["error_message"] is not None
        assert "shutdown" in op["error_message"].lower()


# ============================================================================
# Test: Operation Can Resume After Shutdown
# ============================================================================


class TestM6ResumeAfterShutdown:
    """Tests for resuming operations after graceful shutdown."""

    @pytest.mark.asyncio
    async def test_can_resume_after_shutdown(
        self,
        worker: GracefulShutdownTestWorker,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: MockOperationsRepository,
    ):
        """
        Test the complete shutdown and resume flow:
        1. Start operation
        2. Trigger shutdown
        3. Verify checkpoint saved
        4. Verify status=CANCELLED
        5. Verify try_resume succeeds
        6. Verify checkpoint can be loaded for resume
        """
        operation_id = "op_full_resume_flow"
        await operations_repo.create(operation_id, "training", status="running")

        # Set up training state at epoch 20
        shutdown_epoch = 20
        training_state = TrainingCheckpointState(
            epoch=shutdown_epoch,
            train_loss=0.25,
            val_loss=0.30,
            learning_rate=0.0005,
            training_history={
                "train_loss": [1.0 - i * 0.035 for i in range(shutdown_epoch + 1)],
                "val_loss": [1.1 - i * 0.038 for i in range(shutdown_epoch + 1)],
            },
            original_request={"symbol": "EURUSD", "epochs": 100},
        )
        worker.set_current_state(training_state.to_dict())
        worker.set_current_artifacts(create_model_artifacts(shutdown_epoch))

        operation_started = asyncio.Event()

        async def operation() -> str:
            operation_started.set()
            await asyncio.sleep(10)
            return "done"

        async def trigger_shutdown() -> None:
            await operation_started.wait()
            await asyncio.sleep(0.01)
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown(operation_id, operation())

        await shutdown_task

        # Step 3: Verify checkpoint exists with type="shutdown"
        assert checkpoint_service.checkpoint_exists(operation_id)
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )
        assert checkpoint is not None
        assert checkpoint["checkpoint_type"] == "shutdown"

        # Step 4: Verify status=CANCELLED
        op = operations_repo.get(operation_id)
        assert op is not None
        assert op["status"] == "CANCELLED"

        # Step 5: Verify try_resume succeeds
        resume_success = await operations_repo.try_resume(operation_id)
        assert resume_success is True

        resumed_op = operations_repo.get(operation_id)
        assert resumed_op is not None
        assert resumed_op["status"] == "running"

        # Step 6: Verify checkpoint can be loaded for resume
        assert checkpoint["artifacts"] is not None

        resume_context = TrainingResumeContext(
            start_epoch=checkpoint["state"]["epoch"] + 1,
            model_weights=checkpoint["artifacts"]["model.pt"],
            optimizer_state=checkpoint["artifacts"]["optimizer.pt"],
            training_history=checkpoint["state"].get("training_history", {}),
            original_request=checkpoint["state"].get("original_request", {}),
        )

        # Resume should start from epoch 21
        assert resume_context.start_epoch == shutdown_epoch + 1
        assert len(resume_context.training_history["train_loss"]) == shutdown_epoch + 1

    @pytest.mark.asyncio
    async def test_model_weights_valid_after_shutdown_resume(
        self,
        worker: GracefulShutdownTestWorker,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: MockOperationsRepository,
    ):
        """Test that model weights from shutdown checkpoint are loadable."""
        operation_id = "op_model_validity_test"
        await operations_repo.create(operation_id, "training", status="running")

        # Create known model state
        original_model = nn.Linear(10, 3)
        with torch.no_grad():
            original_model.weight.fill_(0.42)
            original_model.bias.fill_(0.13)

        model_buffer = BytesIO()
        torch.save(original_model.state_dict(), model_buffer)

        optimizer = torch.optim.Adam(original_model.parameters())
        optimizer_buffer = BytesIO()
        torch.save(optimizer.state_dict(), optimizer_buffer)

        worker.set_current_state({"epoch": 5})
        worker.set_current_artifacts(
            {
                "model.pt": model_buffer.getvalue(),
                "optimizer.pt": optimizer_buffer.getvalue(),
            }
        )

        operation_started = asyncio.Event()

        async def operation() -> str:
            operation_started.set()
            await asyncio.sleep(10)
            return "done"

        async def trigger_shutdown() -> None:
            await operation_started.wait()
            await asyncio.sleep(0.01)
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown(operation_id, operation())

        await shutdown_task

        # Load checkpoint and restore model
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=True
        )
        assert checkpoint is not None
        assert checkpoint["artifacts"] is not None

        restored_model = nn.Linear(10, 3)
        state_dict = torch.load(BytesIO(checkpoint["artifacts"]["model.pt"]))
        restored_model.load_state_dict(state_dict)

        # Verify weights match
        assert torch.allclose(restored_model.weight, original_model.weight)
        assert torch.allclose(restored_model.bias, original_model.bias)


# ============================================================================
# Test: Edge Cases
# ============================================================================


class TestM6EdgeCases:
    """Tests for edge cases in graceful shutdown."""

    @pytest.mark.asyncio
    async def test_stale_shutdown_event_is_cleared(
        self,
        worker: GracefulShutdownTestWorker,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: MockOperationsRepository,
    ):
        """Test that stale shutdown events are cleared before new operations.

        This tests the scenario where a shutdown event was set from a previous
        operation (e.g., after backend restart) but the worker survived. The
        stale event should be cleared so new operations can run normally.
        """
        operation_id = "op_stale_event_cleared"
        await operations_repo.create(operation_id, "training", status="running")

        worker.set_current_state({"epoch": 0, "train_loss": 1.0})

        # Set a "stale" shutdown event (simulating leftover from previous op)
        worker._shutdown_event.set()

        async def quick_operation() -> str:
            return "completed"

        # Operation should complete normally - stale event is cleared
        result = await worker.run_with_graceful_shutdown(
            operation_id, quick_operation()
        )

        assert result == "completed"

        # No shutdown checkpoint should be saved (operation completed normally)
        assert not checkpoint_service.checkpoint_exists(operation_id)

    @pytest.mark.asyncio
    async def test_multiple_shutdown_signals(
        self,
        worker: GracefulShutdownTestWorker,
        operations_repo: MockOperationsRepository,
    ):
        """Test that multiple shutdown signals during operation don't cause issues."""
        operation_id = "op_multiple_signals"
        await operations_repo.create(operation_id, "training", status="running")

        worker.set_current_state({"epoch": 5})

        operation_started = asyncio.Event()

        async def operation() -> str:
            operation_started.set()
            await asyncio.sleep(10)
            return "done"

        async def trigger_multiple_shutdowns() -> None:
            await operation_started.wait()
            await asyncio.sleep(0.01)
            # Set shutdown multiple times (should be idempotent)
            worker._shutdown_event.set()
            worker._shutdown_event.set()
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_multiple_shutdowns())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown(operation_id, operation())

        await shutdown_task

        # Should complete without errors
        op = operations_repo.get(operation_id)
        assert op is not None
        assert op["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_operation_completes_without_shutdown(
        self,
        worker: GracefulShutdownTestWorker,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: MockOperationsRepository,
    ):
        """Test that normal completion works when no shutdown signal."""
        operation_id = "op_normal_completion"
        await operations_repo.create(operation_id, "training", status="running")

        worker.set_current_state({"epoch": 50})

        async def quick_operation() -> str:
            return "completed"

        result = await worker.run_with_graceful_shutdown(
            operation_id, quick_operation()
        )

        assert result == "completed"

        # No shutdown checkpoint should be saved
        assert not checkpoint_service.checkpoint_exists(operation_id)

    @pytest.mark.asyncio
    async def test_checkpoint_preserved_on_resume_failure(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: MockOperationsRepository,
    ):
        """Test checkpoint is preserved if resume fails (e.g., worker crashes again)."""
        operation_id = "op_resume_failure"

        # Create a shutdown checkpoint
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="shutdown",
            state={"epoch": 30, "train_loss": 0.2},
            artifacts=create_model_artifacts(30),
        )
        await operations_repo.create(operation_id, "training", status="cancelled")

        # Simulate resume attempt
        resume_success = await operations_repo.try_resume(operation_id)
        assert resume_success is True

        # Checkpoint should still exist (not deleted until completion)
        assert checkpoint_service.checkpoint_exists(operation_id)

        # Simulate failure during resumed training - status goes back to failed
        await operations_repo.update_status(
            operation_id, "failed", error_message="OOM during resume"
        )

        # Checkpoint should still exist for another resume attempt
        assert checkpoint_service.checkpoint_exists(operation_id)
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None
        assert checkpoint["state"]["epoch"] == 30
