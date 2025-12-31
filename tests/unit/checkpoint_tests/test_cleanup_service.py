"""Unit tests for CheckpointCleanupService.

Tests the automatic checkpoint cleanup service that:
1. Deletes checkpoints older than max_age_days
2. Cleans orphan artifact directories
3. Runs on configurable interval
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

from ktrdr.checkpoint.checkpoint_service import CheckpointSummary

# ============================================================================
# Mock CheckpointService for testing
# ============================================================================


class MockCheckpointService:
    """Mock checkpoint service for testing cleanup operations."""

    def __init__(self):
        self.checkpoints: dict[str, dict] = {}
        self.artifacts_dir = Path("/tmp/test_artifacts")
        self.cleanup_old_called = False
        self.cleanup_orphans_called = False
        self.last_max_age_days: Optional[int] = None

    async def list_checkpoints(
        self, older_than_days: Optional[int] = None
    ) -> list[CheckpointSummary]:
        """List checkpoints, optionally filtered by age."""
        result = []
        cutoff = None
        if older_than_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        for op_id, cp in self.checkpoints.items():
            if cutoff is None or cp["created_at"] < cutoff:
                result.append(
                    CheckpointSummary(
                        operation_id=op_id,
                        checkpoint_type=cp["type"],
                        created_at=cp["created_at"],
                        state_summary={},
                        artifacts_size_bytes=cp.get("artifacts_size"),
                    )
                )
        return result

    async def delete_checkpoint(self, operation_id: str) -> bool:
        """Delete a checkpoint."""
        if operation_id in self.checkpoints:
            del self.checkpoints[operation_id]
            return True
        return False

    async def cleanup_old_checkpoints(self, max_age_days: int = 30) -> int:
        """Delete checkpoints older than max_age_days."""
        self.cleanup_old_called = True
        self.last_max_age_days = max_age_days

        old_checkpoints = await self.list_checkpoints(older_than_days=max_age_days)
        deleted = 0
        for cp in old_checkpoints:
            if await self.delete_checkpoint(cp.operation_id):
                deleted += 1
        return deleted

    async def cleanup_orphan_artifacts(self) -> int:
        """Clean orphan artifact directories."""
        self.cleanup_orphans_called = True
        # In mock, we just return 0 - real implementation scans filesystem
        return 0

    def add_checkpoint(
        self,
        operation_id: str,
        age_days: int = 0,
        checkpoint_type: str = "periodic",
        artifacts_size: Optional[int] = None,
    ):
        """Helper to add a checkpoint for testing."""
        created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
        self.checkpoints[operation_id] = {
            "type": checkpoint_type,
            "created_at": created_at,
            "artifacts_size": artifacts_size,
        }


# ============================================================================
# Tests for cleanup methods on CheckpointService
# ============================================================================


class TestCheckpointServiceCleanupMethods:
    """Tests for cleanup_old_checkpoints and cleanup_orphan_artifacts."""

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints_deletes_old(self):
        """Old checkpoints should be deleted."""
        service = MockCheckpointService()

        # Add checkpoints of various ages
        service.add_checkpoint("op_recent", age_days=5)
        service.add_checkpoint("op_old_31", age_days=31)
        service.add_checkpoint("op_old_60", age_days=60)

        # Cleanup checkpoints older than 30 days
        deleted = await service.cleanup_old_checkpoints(max_age_days=30)

        assert deleted == 2
        assert "op_recent" in service.checkpoints
        assert "op_old_31" not in service.checkpoints
        assert "op_old_60" not in service.checkpoints

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints_respects_age_parameter(self):
        """max_age_days parameter should be respected."""
        service = MockCheckpointService()

        service.add_checkpoint("op_10_days", age_days=10)
        service.add_checkpoint("op_20_days", age_days=20)

        # Cleanup with 15 days threshold
        deleted = await service.cleanup_old_checkpoints(max_age_days=15)

        assert deleted == 1
        assert "op_10_days" in service.checkpoints
        assert "op_20_days" not in service.checkpoints

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints_returns_zero_when_none_old(self):
        """Should return 0 when no old checkpoints exist."""
        service = MockCheckpointService()

        service.add_checkpoint("op_recent_1", age_days=1)
        service.add_checkpoint("op_recent_2", age_days=5)

        deleted = await service.cleanup_old_checkpoints(max_age_days=30)

        assert deleted == 0
        assert len(service.checkpoints) == 2

    @pytest.mark.asyncio
    async def test_cleanup_orphan_artifacts_called(self):
        """cleanup_orphan_artifacts should be callable."""
        service = MockCheckpointService()

        orphans = await service.cleanup_orphan_artifacts()

        assert service.cleanup_orphans_called
        assert orphans == 0  # Mock returns 0


# ============================================================================
# Tests for CheckpointCleanupService
# ============================================================================


class TestCheckpointCleanupService:
    """Tests for the background cleanup service."""

    @pytest.mark.asyncio
    async def test_cleanup_service_initialization(self):
        """Service should initialize with configurable parameters."""
        from ktrdr.checkpoint.cleanup_service import CheckpointCleanupService

        mock_service = MockCheckpointService()

        cleanup_service = CheckpointCleanupService(
            checkpoint_service=mock_service,
            max_age_days=45,
            cleanup_interval_hours=12,
        )

        assert cleanup_service._max_age_days == 45
        assert cleanup_service._cleanup_interval == 12 * 3600

    @pytest.mark.asyncio
    async def test_cleanup_service_default_values(self):
        """Service should have sensible defaults."""
        from ktrdr.checkpoint.cleanup_service import CheckpointCleanupService

        mock_service = MockCheckpointService()

        cleanup_service = CheckpointCleanupService(
            checkpoint_service=mock_service,
        )

        assert cleanup_service._max_age_days == 30
        assert cleanup_service._cleanup_interval == 24 * 3600

    @pytest.mark.asyncio
    async def test_run_cleanup_calls_both_methods(self):
        """run_cleanup should call both cleanup methods."""
        from ktrdr.checkpoint.cleanup_service import CheckpointCleanupService

        mock_service = MockCheckpointService()
        mock_service.add_checkpoint("op_old", age_days=35)

        cleanup_service = CheckpointCleanupService(
            checkpoint_service=mock_service,
            max_age_days=30,
        )

        result = await cleanup_service.run_cleanup()

        assert mock_service.cleanup_old_called
        assert mock_service.cleanup_orphans_called
        assert result["checkpoints_deleted"] == 1
        assert result["orphans_cleaned"] == 0

    @pytest.mark.asyncio
    async def test_run_cleanup_passes_max_age(self):
        """run_cleanup should pass configured max_age_days."""
        from ktrdr.checkpoint.cleanup_service import CheckpointCleanupService

        mock_service = MockCheckpointService()

        cleanup_service = CheckpointCleanupService(
            checkpoint_service=mock_service,
            max_age_days=45,
        )

        await cleanup_service.run_cleanup()

        assert mock_service.last_max_age_days == 45

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        """start() should create a background task."""
        from ktrdr.checkpoint.cleanup_service import CheckpointCleanupService

        mock_service = MockCheckpointService()

        cleanup_service = CheckpointCleanupService(
            checkpoint_service=mock_service,
            cleanup_interval_hours=24,
        )

        await cleanup_service.start()

        assert cleanup_service._task is not None
        assert not cleanup_service._task.done()

        # Cleanup
        await cleanup_service.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """stop() should cancel the background task."""
        from ktrdr.checkpoint.cleanup_service import CheckpointCleanupService

        mock_service = MockCheckpointService()

        cleanup_service = CheckpointCleanupService(
            checkpoint_service=mock_service,
        )

        await cleanup_service.start()
        task = cleanup_service._task

        await cleanup_service.stop()

        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_stop_handles_no_task(self):
        """stop() should handle case where task was never started."""
        from ktrdr.checkpoint.cleanup_service import CheckpointCleanupService

        mock_service = MockCheckpointService()

        cleanup_service = CheckpointCleanupService(
            checkpoint_service=mock_service,
        )

        # Should not raise
        await cleanup_service.stop()

    @pytest.mark.asyncio
    async def test_cleanup_loop_runs_after_interval(self):
        """Cleanup loop should run after the configured interval."""
        from ktrdr.checkpoint.cleanup_service import CheckpointCleanupService

        mock_service = MockCheckpointService()
        mock_service.add_checkpoint("op_old", age_days=35)

        # Use very short interval for testing
        cleanup_service = CheckpointCleanupService(
            checkpoint_service=mock_service,
            max_age_days=30,
            cleanup_interval_hours=0,  # Will be overridden
        )
        # Override for testing (in seconds, not hours)
        cleanup_service._cleanup_interval = 0.1  # 100ms

        await cleanup_service.start()

        # Wait for cleanup to run
        await asyncio.sleep(0.2)

        await cleanup_service.stop()

        # Cleanup should have been called
        assert mock_service.cleanup_old_called


class TestCheckpointCleanupServiceLogging:
    """Tests for cleanup service logging."""

    @pytest.mark.asyncio
    async def test_run_cleanup_logs_results(self):
        """run_cleanup should log cleanup results."""
        from ktrdr.checkpoint.cleanup_service import CheckpointCleanupService

        mock_service = MockCheckpointService()
        mock_service.add_checkpoint("op_old", age_days=35)

        cleanup_service = CheckpointCleanupService(
            checkpoint_service=mock_service,
            max_age_days=30,
        )

        with patch("ktrdr.checkpoint.cleanup_service.logger") as mock_logger:
            await cleanup_service.run_cleanup()

            # Should log start and results
            assert mock_logger.info.call_count >= 2
