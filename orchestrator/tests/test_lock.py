"""Tests for milestone lock manager."""

import os
from pathlib import Path

import pytest

from orchestrator.lock import MilestoneLock


class TestMilestoneLockAcquire:
    """Tests for MilestoneLock.acquire()."""

    def test_acquire_creates_lock_file(self, tmp_path: Path) -> None:
        """Acquiring lock creates a lock file."""
        lock = MilestoneLock(tmp_path, "test_milestone")

        result = lock.acquire()

        assert result is True
        assert (tmp_path / "test_milestone.lock").exists()

    def test_acquire_writes_current_pid(self, tmp_path: Path) -> None:
        """Lock file contains current process PID."""
        lock = MilestoneLock(tmp_path, "test_milestone")
        lock.acquire()

        lock_content = (tmp_path / "test_milestone.lock").read_text().strip()

        assert lock_content == str(os.getpid())

    def test_acquire_fails_when_lock_held_by_running_process(
        self, tmp_path: Path
    ) -> None:
        """Cannot acquire lock when held by another running process."""
        lock_file = tmp_path / "test_milestone.lock"
        # Write current PID (simulates another instance of this process)
        lock_file.write_text(str(os.getpid()))

        lock = MilestoneLock(tmp_path, "test_milestone")
        result = lock.acquire()

        assert result is False

    def test_acquire_succeeds_when_lock_held_by_dead_process(
        self, tmp_path: Path
    ) -> None:
        """Can acquire lock when held by a dead process (stale lock)."""
        lock_file = tmp_path / "test_milestone.lock"
        # Write a PID that definitely doesn't exist
        # PID 99999999 is way beyond typical PID range
        lock_file.write_text("99999999")

        lock = MilestoneLock(tmp_path, "test_milestone")
        result = lock.acquire()

        assert result is True
        # Lock should now contain current PID
        assert lock_file.read_text().strip() == str(os.getpid())

    def test_acquire_succeeds_when_lock_file_has_invalid_content(
        self, tmp_path: Path
    ) -> None:
        """Can acquire lock when lock file contains invalid content."""
        lock_file = tmp_path / "test_milestone.lock"
        lock_file.write_text("not_a_pid")

        lock = MilestoneLock(tmp_path, "test_milestone")
        result = lock.acquire()

        assert result is True


class TestMilestoneLockRelease:
    """Tests for MilestoneLock.release()."""

    def test_release_removes_lock_file(self, tmp_path: Path) -> None:
        """Releasing lock removes the lock file."""
        lock = MilestoneLock(tmp_path, "test_milestone")
        lock.acquire()

        lock.release()

        assert not (tmp_path / "test_milestone.lock").exists()

    def test_release_idempotent(self, tmp_path: Path) -> None:
        """Releasing a non-existent lock doesn't raise."""
        lock = MilestoneLock(tmp_path, "test_milestone")

        # Should not raise even though no lock exists
        lock.release()


class TestMilestoneLockContextManager:
    """Tests for MilestoneLock context manager."""

    def test_context_manager_acquires_and_releases(self, tmp_path: Path) -> None:
        """Context manager acquires on enter and releases on exit."""
        lock = MilestoneLock(tmp_path, "test_milestone")
        lock_file = tmp_path / "test_milestone.lock"

        with lock:
            assert lock_file.exists()
            assert lock_file.read_text().strip() == str(os.getpid())

        assert not lock_file.exists()

    def test_context_manager_raises_when_lock_held(self, tmp_path: Path) -> None:
        """Context manager raises RuntimeError when lock already held."""
        lock_file = tmp_path / "test_milestone.lock"
        # Simulate lock held by current process
        lock_file.write_text(str(os.getpid()))

        lock = MilestoneLock(tmp_path, "test_milestone")

        with pytest.raises(RuntimeError, match="already running"):
            with lock:
                pass

    def test_context_manager_releases_on_exception(self, tmp_path: Path) -> None:
        """Lock is released even if exception occurs inside context."""
        lock = MilestoneLock(tmp_path, "test_milestone")
        lock_file = tmp_path / "test_milestone.lock"

        try:
            with lock:
                assert lock_file.exists()
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert not lock_file.exists()


class TestMilestoneLockGetHolderPid:
    """Tests for MilestoneLock.get_holder_pid()."""

    def test_get_holder_pid_returns_pid(self, tmp_path: Path) -> None:
        """get_holder_pid returns PID when lock is held."""
        lock_file = tmp_path / "test_milestone.lock"
        lock_file.write_text("12345")

        lock = MilestoneLock(tmp_path, "test_milestone")

        assert lock.get_holder_pid() == 12345

    def test_get_holder_pid_returns_none_when_no_lock(self, tmp_path: Path) -> None:
        """get_holder_pid returns None when no lock exists."""
        lock = MilestoneLock(tmp_path, "test_milestone")

        assert lock.get_holder_pid() is None

    def test_get_holder_pid_returns_none_for_invalid_content(
        self, tmp_path: Path
    ) -> None:
        """get_holder_pid returns None when lock file has invalid content."""
        lock_file = tmp_path / "test_milestone.lock"
        lock_file.write_text("not_a_pid")

        lock = MilestoneLock(tmp_path, "test_milestone")

        assert lock.get_holder_pid() is None
