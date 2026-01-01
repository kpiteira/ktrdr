"""Automatic checkpoint cleanup service.

Background service that periodically cleans up:
- Old checkpoints (older than max_age_days)
- Orphan artifact directories (no matching DB record)

Runs on a configurable interval (default: daily).
"""

import asyncio
import logging
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class CheckpointServiceProtocol(Protocol):
    """Protocol for checkpoint service dependency."""

    async def cleanup_old_checkpoints(self, max_age_days: int = 30) -> int:
        """Delete checkpoints older than max_age_days."""
        ...

    async def cleanup_orphan_artifacts(self) -> int:
        """Clean orphan artifact directories."""
        ...


class CheckpointCleanupService:
    """Background service for automatic checkpoint cleanup.

    Runs a periodic cleanup loop that:
    1. Deletes checkpoints older than max_age_days
    2. Cleans orphan artifact directories

    Follows the same lifecycle pattern as OrphanOperationDetector:
    - start(): Create background task
    - stop(): Cancel background task
    """

    def __init__(
        self,
        checkpoint_service: CheckpointServiceProtocol,
        max_age_days: int = 30,
        cleanup_interval_hours: int = 24,
    ):
        """Initialize the cleanup service.

        Args:
            checkpoint_service: The checkpoint service for cleanup operations.
            max_age_days: Maximum age in days for checkpoints to keep. Default 30.
            cleanup_interval_hours: Hours between cleanup runs. Default 24 (daily).
        """
        self._checkpoint_service = checkpoint_service
        self._max_age_days = max_age_days
        self._cleanup_interval = cleanup_interval_hours * 3600  # Convert to seconds
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background cleanup loop.

        Creates an asyncio task that runs cleanup at the configured interval.
        """
        if self._task is not None:
            logger.warning("Cleanup service already started")
            return

        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            f"Checkpoint cleanup service started "
            f"(interval={self._cleanup_interval}s, max_age={self._max_age_days}d)"
        )

    async def stop(self) -> None:
        """Stop the background cleanup loop.

        Cancels the cleanup task if running.
        """
        if self._task is None:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            logger.debug("Checkpoint cleanup task cancelled during service stop")
        finally:
            self._task = None
            logger.info("Checkpoint cleanup service stopped")

    async def run_cleanup(self) -> dict[str, Any]:
        """Run a single cleanup cycle.

        Can be called manually or by the background loop.

        Returns:
            Dict with cleanup results:
            - checkpoints_deleted: Number of old checkpoints deleted
            - orphans_cleaned: Number of orphan directories cleaned
        """
        logger.info("Starting checkpoint cleanup...")

        # Delete old checkpoints
        checkpoints_deleted = await self._checkpoint_service.cleanup_old_checkpoints(
            max_age_days=self._max_age_days
        )
        logger.info(f"Deleted {checkpoints_deleted} old checkpoints")

        # Clean orphan artifacts
        orphans_cleaned = await self._checkpoint_service.cleanup_orphan_artifacts()
        logger.info(f"Cleaned {orphans_cleaned} orphan artifact directories")

        return {
            "checkpoints_deleted": checkpoints_deleted,
            "orphans_cleaned": orphans_cleaned,
        }

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop.

        Waits for the configured interval, then runs cleanup.
        Repeats indefinitely until cancelled.
        """
        while True:
            try:
                # Wait for interval before first run
                # This allows the system to stabilize after startup
                await asyncio.sleep(self._cleanup_interval)

                # Run cleanup
                await self.run_cleanup()

            except asyncio.CancelledError:
                logger.debug("Cleanup loop cancelled")
                raise
            except Exception as e:
                # Log error but don't crash the loop
                logger.error(f"Error during checkpoint cleanup: {e}")
                # Wait before retrying to avoid tight error loop
                await asyncio.sleep(60)
