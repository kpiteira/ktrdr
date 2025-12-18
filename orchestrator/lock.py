"""Lock manager for milestone execution.

Provides PID-based locking to prevent concurrent orchestrator runs
on the same milestone.
"""

import os
from pathlib import Path
from types import TracebackType


class MilestoneLock:
    """PID-based lock for milestone execution.

    Prevents multiple orchestrator instances from running the same
    milestone concurrently. Lock is stored as a file containing the
    holder's PID.

    Usage:
        lock = MilestoneLock(state_dir, "M4")
        with lock:
            # Run milestone - lock is held
            ...
        # Lock is released

    Attributes:
        lock_path: Path to the lock file
    """

    def __init__(self, state_dir: Path, milestone_id: str) -> None:
        """Initialize lock manager.

        Args:
            state_dir: Directory for lock files
            milestone_id: Milestone identifier for lock file name
        """
        self.lock_path = state_dir / f"{milestone_id}.lock"

    def acquire(self) -> bool:
        """Try to acquire the lock.

        Checks if an existing lock is held by a running process.
        Stale locks (from dead processes) are automatically cleaned up.

        Returns:
            True if lock acquired, False if held by another running process
        """
        if self.lock_path.exists():
            holder_pid = self.get_holder_pid()
            if holder_pid is not None and self._is_process_running(holder_pid):
                return False
            # Stale lock or invalid content - can acquire

        # Acquire lock
        self.lock_path.write_text(str(os.getpid()))
        return True

    def release(self) -> None:
        """Release the lock.

        Safe to call even if lock doesn't exist.
        """
        if self.lock_path.exists():
            self.lock_path.unlink()

    def get_holder_pid(self) -> int | None:
        """Get PID of lock holder.

        Returns:
            PID as int if lock exists and contains valid PID, None otherwise
        """
        if not self.lock_path.exists():
            return None

        try:
            content = self.lock_path.read_text().strip()
            return int(content)
        except ValueError:
            return None

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running.

        Args:
            pid: Process ID to check

        Returns:
            True if process exists, False otherwise
        """
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we don't have permission to signal it
            return True

    def __enter__(self) -> "MilestoneLock":
        """Acquire lock on context entry.

        Raises:
            RuntimeError: If lock is already held by a running process
        """
        if not self.acquire():
            holder_pid = self.get_holder_pid()
            raise RuntimeError(f"Milestone already running (PID: {holder_pid})")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Release lock on context exit."""
        self.release()
