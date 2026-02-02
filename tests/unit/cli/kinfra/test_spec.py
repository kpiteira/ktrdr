"""Tests for kinfra spec command.

Tests the spec worktree creation command which creates git worktrees
for design/spec work without claiming a sandbox.
"""

from unittest.mock import MagicMock, patch


class TestSpecCommandExists:
    """Tests that spec command is properly registered."""

    def test_spec_command_in_help(self, runner) -> None:
        """kinfra --help should list spec command."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "spec" in result.output.lower()

    def test_spec_help_shows_usage(self, runner) -> None:
        """kinfra spec --help should show feature argument."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["spec", "--help"])
        assert result.exit_code == 0
        assert "feature" in result.output.lower()


class TestSpecCreatesWorktree:
    """Tests for worktree creation."""

    @patch("ktrdr.cli.kinfra.spec.subprocess.run")
    def test_spec_creates_worktree_directory(self, mock_run: MagicMock, runner) -> None:
        """spec should create worktree at ../ktrdr-spec-<feature>/."""
        from ktrdr.cli.kinfra.main import app

        # Mock git branch --list (branch doesn't exist)
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("ktrdr.cli.kinfra.spec.Path.exists", return_value=False):
            with patch("ktrdr.cli.kinfra.spec.Path.mkdir"):
                result = runner.invoke(app, ["spec", "my-feature"])

        assert result.exit_code == 0

        # Should have called git worktree add with -b (new branch)
        calls = mock_run.call_args_list
        assert len(calls) >= 2, f"Expected at least 2 git calls, got {len(calls)}"

        # Second call should be worktree add
        worktree_call = calls[1]
        args = worktree_call[0][0]  # First positional arg is the command list
        assert "worktree" in args
        assert "add" in args
        assert "-b" in args  # New branch flag
        assert "spec/my-feature" in args

    @patch("ktrdr.cli.kinfra.spec.subprocess.run")
    def test_spec_uses_existing_branch(self, mock_run: MagicMock, runner) -> None:
        """spec should use existing branch if it exists."""
        from ktrdr.cli.kinfra.main import app

        # Mock git branch --list (branch exists)
        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            if "branch" in cmd and "--list" in cmd:
                return MagicMock(
                    returncode=0, stdout="spec/existing-feature\n", stderr=""
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = run_side_effect

        with patch("ktrdr.cli.kinfra.spec.Path.exists", return_value=False):
            with patch("ktrdr.cli.kinfra.spec.Path.mkdir"):
                result = runner.invoke(app, ["spec", "existing-feature"])

        assert result.exit_code == 0

        # Second call should be worktree add without -b
        calls = mock_run.call_args_list
        worktree_call = calls[1]
        args = worktree_call[0][0]
        assert "worktree" in args
        assert "add" in args
        assert "-b" not in args  # No new branch flag


class TestSpecCreatesDesignFolder:
    """Tests for design folder creation."""

    @patch("ktrdr.cli.kinfra.spec.subprocess.run")
    def test_spec_creates_design_folder(self, mock_run: MagicMock, runner) -> None:
        """spec should create docs/designs/<feature>/ in worktree."""
        from ktrdr.cli.kinfra.main import app

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        mkdir_calls = []

        def mock_mkdir(*args, **kwargs):
            mkdir_calls.append(kwargs)

        with patch("ktrdr.cli.kinfra.spec.Path.exists", return_value=False):
            with patch("ktrdr.cli.kinfra.spec.Path.mkdir", mock_mkdir):
                result = runner.invoke(app, ["spec", "my-feature"])

        assert result.exit_code == 0

        # Should have called mkdir with parents=True, exist_ok=True
        assert len(mkdir_calls) == 1
        assert mkdir_calls[0].get("parents") is True
        assert mkdir_calls[0].get("exist_ok") is True


class TestSpecFailsIfWorktreeExists:
    """Tests for error handling when worktree exists."""

    def test_spec_fails_if_worktree_directory_exists(self, runner) -> None:
        """spec should fail gracefully if worktree directory exists."""
        from ktrdr.cli.kinfra.main import app

        with patch("ktrdr.cli.kinfra.spec.Path.exists", return_value=True):
            result = runner.invoke(app, ["spec", "existing"])

        assert result.exit_code != 0
        assert "exists" in result.output.lower()


class TestSpecBranchDetection:
    """Tests for branch existence detection."""

    @patch("ktrdr.cli.kinfra.spec.subprocess.run")
    def test_spec_creates_new_branch(self, mock_run: MagicMock, runner) -> None:
        """spec should create new branch if it doesn't exist."""
        from ktrdr.cli.kinfra.main import app

        # Empty stdout means branch doesn't exist
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("ktrdr.cli.kinfra.spec.Path.exists", return_value=False):
            with patch("ktrdr.cli.kinfra.spec.Path.mkdir"):
                result = runner.invoke(app, ["spec", "new-feature"])

        assert result.exit_code == 0

        # Verify branch creation flag was used
        calls = mock_run.call_args_list
        worktree_call = calls[1]
        args = worktree_call[0][0]
        assert "-b" in args
        assert "spec/new-feature" in args


class TestSpecOutputMessages:
    """Tests for command output messages."""

    @patch("ktrdr.cli.kinfra.spec.subprocess.run")
    def test_spec_shows_success_message(self, mock_run: MagicMock, runner) -> None:
        """spec should show success message with worktree path."""
        from ktrdr.cli.kinfra.main import app

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("ktrdr.cli.kinfra.spec.Path.exists", return_value=False):
            with patch("ktrdr.cli.kinfra.spec.Path.mkdir"):
                result = runner.invoke(app, ["spec", "my-feature"])

        assert result.exit_code == 0
        assert "ktrdr-spec-my-feature" in result.output
        # Should mention design folder
        assert "design" in result.output.lower()
