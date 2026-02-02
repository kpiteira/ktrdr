"""Tests for kinfra impl command.

Tests the impl worktree creation command which creates git worktrees
for implementation work and claims a sandbox slot.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestImplCommandExists:
    """Tests that impl command is properly registered."""

    def test_impl_command_in_help(self, runner) -> None:
        """kinfra --help should list impl command."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "impl" in result.output.lower()

    def test_impl_help_shows_usage(self, runner) -> None:
        """kinfra impl --help should show feature_milestone argument."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["impl", "--help"])
        assert result.exit_code == 0
        assert "feature" in result.output.lower()


class TestParseFeatureMilestone:
    """Tests for parsing feature/milestone argument."""

    def test_parse_valid_format(self) -> None:
        """Should parse 'feature/M1' into (feature, M1)."""
        from ktrdr.cli.kinfra.impl import _parse_feature_milestone

        feature, milestone = _parse_feature_milestone("genome/M1")
        assert feature == "genome"
        assert milestone == "M1"

    def test_parse_complex_feature_name(self) -> None:
        """Should handle complex feature names with hyphens."""
        from ktrdr.cli.kinfra.impl import _parse_feature_milestone

        feature, milestone = _parse_feature_milestone("my-cool-feature/M2")
        assert feature == "my-cool-feature"
        assert milestone == "M2"

    def test_parse_invalid_format_no_slash(self) -> None:
        """Should raise error for format without slash."""
        from ktrdr.cli.kinfra.impl import _parse_feature_milestone

        with pytest.raises(ValueError, match="feature/milestone"):
            _parse_feature_milestone("invalid")


class TestFindMilestoneFile:
    """Tests for finding milestone file in docs/designs."""

    def test_finds_milestone_file(self, tmp_path: Path) -> None:
        """Should find M1_*.md file in implementation folder."""
        from ktrdr.cli.kinfra.impl import _find_milestone_file

        # Create test structure
        impl_dir = tmp_path / "docs" / "designs" / "myfeature" / "implementation"
        impl_dir.mkdir(parents=True)
        milestone_file = impl_dir / "M1_core.md"
        milestone_file.write_text("# M1")

        result = _find_milestone_file("myfeature", "M1", base_path=tmp_path)
        assert result == milestone_file

    def test_finds_uppercase_milestone(self, tmp_path: Path) -> None:
        """Should find milestone regardless of case."""
        from ktrdr.cli.kinfra.impl import _find_milestone_file

        impl_dir = tmp_path / "docs" / "designs" / "myfeature" / "implementation"
        impl_dir.mkdir(parents=True)
        milestone_file = impl_dir / "m1_test.md"
        milestone_file.write_text("# M1")

        result = _find_milestone_file("myfeature", "M1", base_path=tmp_path)
        assert result == milestone_file

    def test_returns_none_if_not_found(self, tmp_path: Path) -> None:
        """Should return None if milestone file not found."""
        from ktrdr.cli.kinfra.impl import _find_milestone_file

        # Create empty implementation folder
        impl_dir = tmp_path / "docs" / "designs" / "myfeature" / "implementation"
        impl_dir.mkdir(parents=True)

        result = _find_milestone_file("myfeature", "M1", base_path=tmp_path)
        assert result is None

    def test_returns_none_if_feature_not_found(self, tmp_path: Path) -> None:
        """Should return None if feature folder doesn't exist."""
        from ktrdr.cli.kinfra.impl import _find_milestone_file

        result = _find_milestone_file("nonexistent", "M1", base_path=tmp_path)
        assert result is None


class TestImplChecksSlotFirst:
    """Tests that impl checks slot availability before creating worktree (GAP-6)."""

    @patch("ktrdr.cli.kinfra.impl._find_milestone_file")
    @patch("ktrdr.cli.kinfra.impl.load_registry")
    def test_impl_checks_slot_before_worktree(
        self, mock_load_registry: MagicMock, mock_find_milestone: MagicMock, runner
    ) -> None:
        """impl should check slot availability before creating worktree."""
        from ktrdr.cli.kinfra.main import app

        # Mock milestone found
        mock_find_milestone.return_value = Path("/tmp/milestone.md")

        # Mock no available slots
        mock_registry = MagicMock()
        mock_registry.get_available_slot.return_value = None
        mock_load_registry.return_value = mock_registry

        with patch("ktrdr.cli.kinfra.impl._is_git_repo", return_value=True):
            result = runner.invoke(app, ["impl", "feature/M1"])

        assert result.exit_code != 0
        assert "slot" in result.output.lower()
        # Should NOT have tried to create worktree
        mock_registry.get_available_slot.assert_called_once()


class TestImplFailsNoSlots:
    """Tests error handling when no slots available."""

    @patch("ktrdr.cli.kinfra.impl._find_milestone_file")
    @patch("ktrdr.cli.kinfra.impl.load_registry")
    def test_impl_fails_gracefully_no_slots(
        self, mock_load_registry: MagicMock, mock_find_milestone: MagicMock, runner
    ) -> None:
        """impl should fail gracefully when all slots are in use."""
        from ktrdr.cli.kinfra.main import app

        mock_find_milestone.return_value = Path("/tmp/milestone.md")
        mock_registry = MagicMock()
        mock_registry.get_available_slot.return_value = None
        mock_load_registry.return_value = mock_registry

        with patch("ktrdr.cli.kinfra.impl._is_git_repo", return_value=True):
            result = runner.invoke(app, ["impl", "feature/M1"])

        assert result.exit_code != 0
        assert "slot" in result.output.lower()


class TestImplFailsMilestoneNotFound:
    """Tests error handling when milestone file not found."""

    @patch("ktrdr.cli.kinfra.impl._find_milestone_file")
    def test_impl_fails_milestone_not_found(
        self, mock_find_milestone: MagicMock, runner
    ) -> None:
        """impl should fail gracefully when milestone file not found."""
        from ktrdr.cli.kinfra.main import app

        mock_find_milestone.return_value = None

        with patch("ktrdr.cli.kinfra.impl._is_git_repo", return_value=True):
            result = runner.invoke(app, ["impl", "nonexistent/M1"])

        assert result.exit_code != 0
        assert (
            "milestone" in result.output.lower() or "not found" in result.output.lower()
        )


class TestImplBranchBehavior:
    """Tests for branch creation/reuse behavior."""

    @patch("ktrdr.cli.kinfra.slots.start_slot_containers")
    @patch("ktrdr.cli.kinfra.override.generate_override")
    @patch("ktrdr.cli.kinfra.impl.subprocess.run")
    @patch("ktrdr.cli.kinfra.impl._find_milestone_file")
    @patch("ktrdr.cli.kinfra.impl.load_registry")
    def test_impl_uses_existing_branch(
        self,
        mock_load_registry: MagicMock,
        mock_find_milestone: MagicMock,
        mock_run: MagicMock,
        mock_override: MagicMock,
        mock_start: MagicMock,
        runner,
    ) -> None:
        """impl should use existing branch if impl/feature-milestone exists."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import SlotInfo

        mock_find_milestone.return_value = Path("/tmp/milestone.md")

        # Mock available slot
        mock_slot = MagicMock(spec=SlotInfo)
        mock_slot.slot_id = 1
        mock_slot.profile = "light"
        mock_slot.ports = {"api": 8001}
        mock_registry = MagicMock()
        mock_registry.get_available_slot.return_value = mock_slot
        mock_load_registry.return_value = mock_registry

        # Mock git commands
        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            if "branch" in cmd and "--list" in cmd:
                # Branch exists
                return MagicMock(returncode=0, stdout="impl/feature-M1\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = run_side_effect

        with patch("ktrdr.cli.kinfra.impl._is_git_repo", return_value=True):
            with patch("ktrdr.cli.kinfra.impl.Path.exists", return_value=False):
                runner.invoke(app, ["impl", "feature/M1"])

        # Find the worktree add call
        worktree_calls = [
            c
            for c in mock_run.call_args_list
            if "worktree" in c[0][0] and "add" in c[0][0]
        ]
        assert len(worktree_calls) >= 1
        # Should NOT have -b flag (using existing branch)
        assert "-b" not in worktree_calls[0][0][0]

    @patch("ktrdr.cli.kinfra.slots.start_slot_containers")
    @patch("ktrdr.cli.kinfra.override.generate_override")
    @patch("ktrdr.cli.kinfra.impl.subprocess.run")
    @patch("ktrdr.cli.kinfra.impl._find_milestone_file")
    @patch("ktrdr.cli.kinfra.impl.load_registry")
    def test_impl_creates_new_branch(
        self,
        mock_load_registry: MagicMock,
        mock_find_milestone: MagicMock,
        mock_run: MagicMock,
        mock_override: MagicMock,
        mock_start: MagicMock,
        runner,
    ) -> None:
        """impl should create new branch if impl/feature-milestone doesn't exist."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import SlotInfo

        mock_find_milestone.return_value = Path("/tmp/milestone.md")

        mock_slot = MagicMock(spec=SlotInfo)
        mock_slot.slot_id = 1
        mock_slot.profile = "light"
        mock_slot.ports = {"api": 8001}
        mock_registry = MagicMock()
        mock_registry.get_available_slot.return_value = mock_slot
        mock_load_registry.return_value = mock_registry

        # Mock git commands - branch doesn't exist
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("ktrdr.cli.kinfra.impl._is_git_repo", return_value=True):
            with patch("ktrdr.cli.kinfra.impl.Path.exists", return_value=False):
                runner.invoke(app, ["impl", "feature/M1"])

        # Find the worktree add call
        worktree_calls = [
            c
            for c in mock_run.call_args_list
            if "worktree" in c[0][0] and "add" in c[0][0]
        ]
        assert len(worktree_calls) >= 1
        # Should have -b flag (creating new branch)
        assert "-b" in worktree_calls[0][0][0]


class TestImplFailsWorktreeExists:
    """Tests error handling when worktree already exists."""

    @patch("ktrdr.cli.kinfra.impl._find_milestone_file")
    @patch("ktrdr.cli.kinfra.impl.load_registry")
    def test_impl_fails_worktree_exists(
        self, mock_load_registry: MagicMock, mock_find_milestone: MagicMock, runner
    ) -> None:
        """impl should fail gracefully if worktree directory already exists."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import SlotInfo

        mock_find_milestone.return_value = Path("/tmp/milestone.md")

        mock_slot = MagicMock(spec=SlotInfo)
        mock_slot.slot_id = 1
        mock_registry = MagicMock()
        mock_registry.get_available_slot.return_value = mock_slot
        mock_load_registry.return_value = mock_registry

        with patch("ktrdr.cli.kinfra.impl._is_git_repo", return_value=True):
            # Worktree path already exists
            with patch("ktrdr.cli.kinfra.impl.Path.exists", return_value=True):
                result = runner.invoke(app, ["impl", "feature/M1"])

        assert result.exit_code != 0
        assert "exists" in result.output.lower()


class TestImplRollbackOnDockerFailure:
    """Tests rollback behavior when Docker fails (GAP-7)."""

    @patch("ktrdr.cli.kinfra.slots.start_slot_containers")
    @patch("ktrdr.cli.kinfra.override.generate_override")
    @patch("ktrdr.cli.kinfra.impl.subprocess.run")
    @patch("ktrdr.cli.kinfra.impl._find_milestone_file")
    @patch("ktrdr.cli.kinfra.impl.load_registry")
    def test_impl_releases_slot_on_docker_failure(
        self,
        mock_load_registry: MagicMock,
        mock_find_milestone: MagicMock,
        mock_run: MagicMock,
        mock_override: MagicMock,
        mock_start: MagicMock,
        runner,
    ) -> None:
        """impl should release slot but keep worktree on Docker failure."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import SlotInfo

        mock_find_milestone.return_value = Path("/tmp/milestone.md")

        mock_slot = MagicMock(spec=SlotInfo)
        mock_slot.slot_id = 1
        mock_slot.profile = "light"
        mock_slot.ports = {"api": 8001}
        mock_registry = MagicMock()
        mock_registry.get_available_slot.return_value = mock_slot
        mock_load_registry.return_value = mock_registry

        # Git commands succeed
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Docker start fails
        mock_start.side_effect = RuntimeError("Container start failed")

        with patch("ktrdr.cli.kinfra.impl._is_git_repo", return_value=True):
            with patch("ktrdr.cli.kinfra.impl.Path.exists", return_value=False):
                result = runner.invoke(app, ["impl", "feature/M1"])

        # Should have released the slot
        mock_registry.release_slot.assert_called_once_with(1)

        # Output should indicate slot released but worktree kept
        assert result.exit_code != 0
        assert "slot" in result.output.lower() or "worktree" in result.output.lower()


class TestImplProfileOption:
    """Tests for --profile option."""

    def test_impl_help_shows_profile_option(self, runner) -> None:
        """impl --help should show --profile option."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["impl", "--help"])
        assert result.exit_code == 0
        assert "profile" in result.output.lower()
