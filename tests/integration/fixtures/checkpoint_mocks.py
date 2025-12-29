"""Shared mock infrastructure for checkpoint integration tests.

This module provides reusable mock services for testing checkpoint and resume
functionality across different operation types (training, backtesting).
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ktrdr.checkpoint.checkpoint_service import CheckpointData


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
        """Atomically update status to RESUMING if resumable.

        Note: Sets status to 'resuming' which matches real backend behavior.
        The worker then transitions resuming → running via start_operation().
        """
        op = self.operations.get(operation_id)
        if op and op["status"] in ("cancelled", "failed"):
            op["status"] = "resuming"
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
    """Checkpoint service with in-memory repository for testing.

    Supports both artifact-based checkpoints (e.g., training with model.pt)
    and artifact-free checkpoints (e.g., backtesting with state in DB).

    Args:
        artifacts_dir: Optional directory for storing artifacts.
                      If None, artifact handling is disabled.
    """

    def __init__(self, artifacts_dir: Optional[Path] = None):
        self._mock_repo = MockCheckpointRepository()
        self._artifacts_dir = artifacts_dir

    async def save_checkpoint(
        self,
        operation_id: str,
        checkpoint_type: str,
        state: dict,
        artifacts: Optional[dict[str, bytes]] = None,
    ) -> None:
        """Save checkpoint with both in-memory repo and filesystem (if artifacts).

        Args:
            operation_id: Operation ID
            checkpoint_type: Type of checkpoint (periodic, cancellation, failure)
            state: Checkpoint state dict
            artifacts: Optional dict of artifact name → bytes
        """
        import json

        artifacts_path: Optional[Path] = None
        artifacts_size_bytes: Optional[int] = None

        # Write artifacts if provided and artifacts_dir is configured
        if artifacts and self._artifacts_dir is not None:
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
        """Load checkpoint from in-memory repo and filesystem.

        Args:
            operation_id: Operation ID
            load_artifacts: Whether to load artifacts from filesystem

        Returns:
            CheckpointData or None if not found
        """
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

        # Load artifacts if requested and path exists
        if load_artifacts and record["artifacts_path"]:
            checkpoint.artifacts = await self._load_artifacts(
                record["artifacts_path"], operation_id
            )

        return checkpoint

    async def delete_checkpoint(self, operation_id: str) -> bool:
        """Delete checkpoint from in-memory repo and filesystem.

        Args:
            operation_id: Operation ID

        Returns:
            True if deleted, False if not found
        """
        record = self._mock_repo.get(operation_id)
        if record is None:
            return False

        # Delete artifacts from filesystem
        if record["artifacts_path"]:
            artifacts_path = Path(record["artifacts_path"])
            if artifacts_path.exists():
                shutil.rmtree(artifacts_path, ignore_errors=True)

        return self._mock_repo.delete(operation_id)

    def checkpoint_exists(self, operation_id: str) -> bool:
        """Check if checkpoint exists.

        Args:
            operation_id: Operation ID

        Returns:
            True if checkpoint exists, False otherwise
        """
        return self._mock_repo.exists(operation_id)

    async def _write_artifacts(
        self, operation_id: str, artifacts: dict[str, bytes]
    ) -> Path:
        """Write artifacts to filesystem.

        Uses atomic write via temp directory + rename.

        Args:
            operation_id: Operation ID
            artifacts: Dict of artifact name → bytes

        Returns:
            Path to artifact directory
        """
        if self._artifacts_dir is None:
            raise ValueError("artifacts_dir not configured")

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
        """Load artifacts from filesystem.

        Args:
            artifacts_path: Path to artifact directory
            operation_id: Operation ID (unused, kept for signature compatibility)

        Returns:
            Dict of artifact name → bytes
        """
        artifact_dir = Path(artifacts_path)
        artifacts = {}
        if artifact_dir.exists():
            for file_path in artifact_dir.iterdir():
                if file_path.is_file():
                    artifacts[file_path.name] = file_path.read_bytes()
        return artifacts
