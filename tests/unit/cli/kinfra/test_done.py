"""Tests for kinfra done command.

Tests the done command which completes a worktree, releases its sandbox slot,
and removes the worktree with dirty state protection.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestDoneCommandExists:
    """Tests that done command is properly registered."""

    def test_done_command_in_help(self, runner) -> None:
        """kinfra --help should list done command."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "done" in result.output.lower()

    def test_done_help_shows_usage(self, runner) -> None:
        """kinfra done --help should show name argument and force flag."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["done", "--help"])
        assert result.exit_code == 0
        assert "name" in result.output.lower()
        assert "force" in result.output.lower()


class TestFindWorktree:
    """Tests for finding worktree by name."""

    def test_find_worktree_exact_impl(self, tmp_path: Path) -> None:
        """Should find impl worktree by exact name."""
        from ktrdr.cli.kinfra.done import _find_worktree

        # Create worktree directory structure
        worktree = tmp_path / "ktrdr-impl-feature-M1"
        worktree.mkdir()

        result = _find_worktree("feature-M1", parent_path=tmp_path)
        assert result == worktree

    def test_find_worktree_exact_spec(self, tmp_path: Path) -> None:
        """Should find spec worktree by exact name."""
        from ktrdr.cli.kinfra.done import _find_worktree

        worktree = tmp_path / "ktrdr-spec-mydesign"
        worktree.mkdir()

        result = _find_worktree("mydesign", parent_path=tmp_path)
        assert result == worktree

    def test_find_worktree_partial_match(self, tmp_path: Path) -> None:
        """Should find worktree by partial name match."""
        from ktrdr.cli.kinfra.done import _find_worktree

        worktree = tmp_path / "ktrdr-impl-genome-M1"
        worktree.mkdir()

        result = _find_worktree("genome", parent_path=tmp_path)
        assert result == worktree

    def test_find_worktree_not_found(self, tmp_path: Path) -> None:
        """Should raise error when no worktree matches."""
        import typer

        from ktrdr.cli.kinfra.done import _find_worktree

        with pytest.raises(typer.BadParameter, match="No worktree found"):
            _find_worktree("nonexistent", parent_path=tmp_path)


class TestHasUncommittedChanges:
    """Tests for checking uncommitted changes."""

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    def test_has_uncommitted_returns_true(self, mock_run: MagicMock) -> None:
        """Should return True when git status has output."""
        from ktrdr.cli.kinfra.done import _has_uncommitted_changes

        mock_run.return_value = MagicMock(stdout=" M dirty.py\n", returncode=0)

        result = _has_uncommitted_changes(Path("/fake"))
        assert result is True
        mock_run.assert_called_once()

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    def test_has_uncommitted_returns_false(self, mock_run: MagicMock) -> None:
        """Should return False when git status is clean."""
        from ktrdr.cli.kinfra.done import _has_uncommitted_changes

        mock_run.return_value = MagicMock(stdout="", returncode=0)

        result = _has_uncommitted_changes(Path("/fake"))
        assert result is False


class TestHasUnpushedCommits:
    """Tests for checking unpushed commits."""

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    def test_has_unpushed_returns_true(self, mock_run: MagicMock) -> None:
        """Should return True when there are unpushed commits."""
        from ktrdr.cli.kinfra.done import _has_unpushed_commits

        mock_run.return_value = MagicMock(stdout="abc1234 Some commit\n", returncode=0)

        result = _has_unpushed_commits(Path("/fake"))
        assert result is True

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    def test_has_unpushed_returns_false(self, mock_run: MagicMock) -> None:
        """Should return False when all commits are pushed."""
        from ktrdr.cli.kinfra.done import _has_unpushed_commits

        mock_run.return_value = MagicMock(stdout="", returncode=0)

        result = _has_unpushed_commits(Path("/fake"))
        assert result is False

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    def test_has_unpushed_no_upstream(self, mock_run: MagicMock) -> None:
        """Should return True when no upstream and there are local commits."""
        from ktrdr.cli.kinfra.done import _has_unpushed_commits

        # First call (git log @{u}..HEAD) fails - no upstream
        # Second call (git rev-parse --abbrev-ref @{u}) fails - no upstream
        # Third call (git log --oneline -1) returns commit - has local commits
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="no upstream"),
            MagicMock(returncode=1, stdout="", stderr="no upstream"),
            MagicMock(returncode=0, stdout="abc123 Initial commit\n"),
        ]

        result = _has_unpushed_commits(Path("/fake"))
        assert result is True


class TestDoneChecksDirtyState:
    """Tests that done aborts on dirty state without --force."""

    @patch("ktrdr.cli.kinfra.done._find_worktree")
    @patch("ktrdr.cli.kinfra.done._has_uncommitted_changes")
    def test_done_aborts_on_uncommitted(
        self, mock_uncommitted: MagicMock, mock_find: MagicMock, runner
    ) -> None:
        """done should abort with uncommitted changes."""
        from ktrdr.cli.kinfra.main import app

        mock_find.return_value = Path("/tmp/ktrdr-impl-test-M1")
        mock_uncommitted.return_value = True

        result = runner.invoke(app, ["done", "test-M1"])

        assert result.exit_code != 0
        assert "uncommitted" in result.output.lower()

    @patch("ktrdr.cli.kinfra.done._find_worktree")
    @patch("ktrdr.cli.kinfra.done._has_uncommitted_changes")
    @patch("ktrdr.cli.kinfra.done._has_unpushed_commits")
    def test_done_aborts_on_unpushed(
        self,
        mock_unpushed: MagicMock,
        mock_uncommitted: MagicMock,
        mock_find: MagicMock,
        runner,
    ) -> None:
        """done should abort with unpushed commits."""
        from ktrdr.cli.kinfra.main import app

        mock_find.return_value = Path("/tmp/ktrdr-impl-test-M1")
        mock_uncommitted.return_value = False
        mock_unpushed.return_value = True

        result = runner.invoke(app, ["done", "test-M1"])

        assert result.exit_code != 0
        assert "unpushed" in result.output.lower()


class TestDoneForceFlag:
    """Tests that --force bypasses dirty state check."""

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    @patch("ktrdr.cli.kinfra.slots.stop_slot_containers")
    @patch("ktrdr.cli.kinfra.override.remove_override")
    @patch("ktrdr.cli.kinfra.done.load_registry")
    @patch("ktrdr.cli.kinfra.done._find_worktree")
    @patch("ktrdr.cli.kinfra.done._has_uncommitted_changes")
    @patch("ktrdr.cli.kinfra.done._has_unpushed_commits")
    def test_done_force_ignores_dirty(
        self,
        mock_unpushed: MagicMock,
        mock_uncommitted: MagicMock,
        mock_find: MagicMock,
        mock_load_registry: MagicMock,
        mock_remove_override: MagicMock,
        mock_stop: MagicMock,
        mock_run: MagicMock,
        runner,
    ) -> None:
        """done --force should proceed despite dirty state."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import SlotInfo

        mock_find.return_value = Path("/tmp/ktrdr-impl-test-M1")
        mock_uncommitted.return_value = True  # Dirty state
        mock_unpushed.return_value = False

        # Mock slot
        mock_slot = MagicMock(spec=SlotInfo)
        mock_slot.slot_id = 1
        mock_registry = MagicMock()
        mock_registry.get_slot_for_worktree.return_value = mock_slot
        mock_load_registry.return_value = mock_registry

        mock_run.return_value = MagicMock(returncode=0)

        # Note: options must come before arguments with invoke_without_command
        result = runner.invoke(app, ["done", "--force", "test-M1"])

        assert result.exit_code == 0
        mock_stop.assert_called_once()
        # With --force, dirty checks should NOT be consulted
        mock_uncommitted.assert_not_called()
        mock_unpushed.assert_not_called()


class TestDoneStopsContainers:
    """Tests that done stops containers."""

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    @patch("ktrdr.cli.kinfra.slots.stop_slot_containers")
    @patch("ktrdr.cli.kinfra.override.remove_override")
    @patch("ktrdr.cli.kinfra.done.load_registry")
    @patch("ktrdr.cli.kinfra.done._find_worktree")
    @patch("ktrdr.cli.kinfra.done._has_uncommitted_changes")
    @patch("ktrdr.cli.kinfra.done._has_unpushed_commits")
    def test_done_stops_containers(
        self,
        mock_unpushed: MagicMock,
        mock_uncommitted: MagicMock,
        mock_find: MagicMock,
        mock_load_registry: MagicMock,
        mock_remove_override: MagicMock,
        mock_stop: MagicMock,
        mock_run: MagicMock,
        runner,
    ) -> None:
        """done should stop containers for the slot."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import SlotInfo

        mock_find.return_value = Path("/tmp/ktrdr-impl-test-M1")
        mock_uncommitted.return_value = False
        mock_unpushed.return_value = False

        mock_slot = MagicMock(spec=SlotInfo)
        mock_slot.slot_id = 1
        mock_registry = MagicMock()
        mock_registry.get_slot_for_worktree.return_value = mock_slot
        mock_load_registry.return_value = mock_registry

        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(app, ["done", "test-M1"])

        assert result.exit_code == 0
        mock_stop.assert_called_once_with(mock_slot)


class TestDoneReleasesSlot:
    """Tests that done releases the slot in registry."""

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    @patch("ktrdr.cli.kinfra.slots.stop_slot_containers")
    @patch("ktrdr.cli.kinfra.override.remove_override")
    @patch("ktrdr.cli.kinfra.done.load_registry")
    @patch("ktrdr.cli.kinfra.done._find_worktree")
    @patch("ktrdr.cli.kinfra.done._has_uncommitted_changes")
    @patch("ktrdr.cli.kinfra.done._has_unpushed_commits")
    def test_done_releases_slot(
        self,
        mock_unpushed: MagicMock,
        mock_uncommitted: MagicMock,
        mock_find: MagicMock,
        mock_load_registry: MagicMock,
        mock_remove_override: MagicMock,
        mock_stop: MagicMock,
        mock_run: MagicMock,
        runner,
    ) -> None:
        """done should release slot in registry."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import SlotInfo

        mock_find.return_value = Path("/tmp/ktrdr-impl-test-M1")
        mock_uncommitted.return_value = False
        mock_unpushed.return_value = False

        mock_slot = MagicMock(spec=SlotInfo)
        mock_slot.slot_id = 2
        mock_registry = MagicMock()
        mock_registry.get_slot_for_worktree.return_value = mock_slot
        mock_load_registry.return_value = mock_registry

        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(app, ["done", "test-M1"])

        assert result.exit_code == 0
        mock_registry.release_slot.assert_called_once_with(2)


class TestDoneRemovesOverride:
    """Tests that done removes the override file."""

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    @patch("ktrdr.cli.kinfra.slots.stop_slot_containers")
    @patch("ktrdr.cli.kinfra.override.remove_override")
    @patch("ktrdr.cli.kinfra.done.load_registry")
    @patch("ktrdr.cli.kinfra.done._find_worktree")
    @patch("ktrdr.cli.kinfra.done._has_uncommitted_changes")
    @patch("ktrdr.cli.kinfra.done._has_unpushed_commits")
    def test_done_removes_override(
        self,
        mock_unpushed: MagicMock,
        mock_uncommitted: MagicMock,
        mock_find: MagicMock,
        mock_load_registry: MagicMock,
        mock_remove_override: MagicMock,
        mock_stop: MagicMock,
        mock_run: MagicMock,
        runner,
    ) -> None:
        """done should remove the override file."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import SlotInfo

        mock_find.return_value = Path("/tmp/ktrdr-impl-test-M1")
        mock_uncommitted.return_value = False
        mock_unpushed.return_value = False

        mock_slot = MagicMock(spec=SlotInfo)
        mock_slot.slot_id = 1
        mock_registry = MagicMock()
        mock_registry.get_slot_for_worktree.return_value = mock_slot
        mock_load_registry.return_value = mock_registry

        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(app, ["done", "test-M1"])

        assert result.exit_code == 0
        mock_remove_override.assert_called_once_with(mock_slot)


class TestDoneRemovesWorktree:
    """Tests that done removes the worktree."""

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    @patch("ktrdr.cli.kinfra.slots.stop_slot_containers")
    @patch("ktrdr.cli.kinfra.override.remove_override")
    @patch("ktrdr.cli.kinfra.done.load_registry")
    @patch("ktrdr.cli.kinfra.done._find_worktree")
    @patch("ktrdr.cli.kinfra.done._has_uncommitted_changes")
    @patch("ktrdr.cli.kinfra.done._has_unpushed_commits")
    def test_done_removes_worktree(
        self,
        mock_unpushed: MagicMock,
        mock_uncommitted: MagicMock,
        mock_find: MagicMock,
        mock_load_registry: MagicMock,
        mock_remove_override: MagicMock,
        mock_stop: MagicMock,
        mock_run: MagicMock,
        runner,
    ) -> None:
        """done should call git worktree remove."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import SlotInfo

        worktree_path = Path("/tmp/ktrdr-impl-test-M1")
        mock_find.return_value = worktree_path
        mock_uncommitted.return_value = False
        mock_unpushed.return_value = False

        mock_slot = MagicMock(spec=SlotInfo)
        mock_slot.slot_id = 1
        mock_registry = MagicMock()
        mock_registry.get_slot_for_worktree.return_value = mock_slot
        mock_load_registry.return_value = mock_registry

        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(app, ["done", "test-M1"])

        assert result.exit_code == 0
        # Find the git worktree remove call
        worktree_remove_calls = [
            c for c in mock_run.call_args_list if "worktree" in c[0][0]
        ]
        assert len(worktree_remove_calls) >= 1
        assert "remove" in worktree_remove_calls[0][0][0]


class TestDoneFailsOnSpec:
    """Tests that done fails gracefully on spec worktrees."""

    @patch("ktrdr.cli.kinfra.done._find_worktree")
    def test_done_fails_on_spec_worktree(self, mock_find: MagicMock, runner) -> None:
        """done should fail with clear error on spec worktrees."""
        from ktrdr.cli.kinfra.main import app

        # Return a spec worktree path
        mock_find.return_value = Path("/tmp/ktrdr-spec-mydesign")

        result = runner.invoke(app, ["done", "mydesign"])

        assert result.exit_code != 0
        assert "spec" in result.output.lower()


class TestDoneNoSlotClaimed:
    """Tests that done handles worktrees without claimed slots."""

    @patch("ktrdr.cli.kinfra.done.subprocess.run")
    @patch("ktrdr.cli.kinfra.done.load_registry")
    @patch("ktrdr.cli.kinfra.done._find_worktree")
    @patch("ktrdr.cli.kinfra.done._has_uncommitted_changes")
    @patch("ktrdr.cli.kinfra.done._has_unpushed_commits")
    def test_done_no_slot_claimed(
        self,
        mock_unpushed: MagicMock,
        mock_uncommitted: MagicMock,
        mock_find: MagicMock,
        mock_load_registry: MagicMock,
        mock_run: MagicMock,
        runner,
    ) -> None:
        """done should handle worktrees that have no slot claimed."""
        from ktrdr.cli.kinfra.main import app

        mock_find.return_value = Path("/tmp/ktrdr-impl-test-M1")
        mock_uncommitted.return_value = False
        mock_unpushed.return_value = False

        # No slot claimed
        mock_registry = MagicMock()
        mock_registry.get_slot_for_worktree.return_value = None
        mock_load_registry.return_value = mock_registry

        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(app, ["done", "test-M1"])

        assert result.exit_code == 0
        assert (
            "no sandbox slot" in result.output.lower()
            or "already released" in result.output.lower()
        )
