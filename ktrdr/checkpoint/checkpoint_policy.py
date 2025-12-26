"""Checkpoint policy for determining when to create checkpoints.

The policy uses two independent triggers:
1. Unit-based: Checkpoint after every N units (e.g., epochs)
2. Time-based: Checkpoint after M seconds have elapsed

Either trigger is sufficient to trigger a checkpoint.
"""

import time
from typing import Optional


class CheckpointPolicy:
    """Policy that determines when checkpoints should be created.

    Tracks last checkpoint time and unit to make trigger decisions.
    Either the unit interval OR the time interval being exceeded
    will trigger a checkpoint.
    """

    def __init__(
        self,
        unit_interval: int = 10,
        time_interval_seconds: int = 300,
    ) -> None:
        """Initialize checkpoint policy.

        Args:
            unit_interval: Create checkpoint every N units (e.g., epochs).
                Defaults to 10.
            time_interval_seconds: Create checkpoint after N seconds.
                Defaults to 300 (5 minutes).
        """
        self._unit_interval = unit_interval
        self._time_interval = time_interval_seconds
        self._last_checkpoint_time: Optional[float] = None
        self._last_checkpoint_unit: int = 0

    @property
    def unit_interval(self) -> int:
        """Return the unit interval setting."""
        return self._unit_interval

    @property
    def time_interval_seconds(self) -> int:
        """Return the time interval setting in seconds."""
        return self._time_interval

    def should_checkpoint(self, current_unit: int, force: bool = False) -> bool:
        """Determine if a checkpoint should be created.

        Args:
            current_unit: Current unit number (e.g., epoch number).
            force: If True, always return True regardless of intervals.

        Returns:
            True if a checkpoint should be created, False otherwise.
        """
        if force:
            return True

        # Time-based trigger (only if we've recorded a checkpoint before)
        if self._last_checkpoint_time is not None:
            now = time.time()
            if now - self._last_checkpoint_time >= self._time_interval:
                return True

        # Unit-based trigger
        if current_unit - self._last_checkpoint_unit >= self._unit_interval:
            return True

        return False

    def record_checkpoint(self, current_unit: int) -> None:
        """Record that a checkpoint was created.

        Should be called after successfully saving a checkpoint.

        Args:
            current_unit: Unit number at which checkpoint was created.
        """
        self._last_checkpoint_time = time.time()
        self._last_checkpoint_unit = current_unit
