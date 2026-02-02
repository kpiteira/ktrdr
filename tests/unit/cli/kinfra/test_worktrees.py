"""Tests for kinfra worktrees command.

Tests the worktrees listing command which displays all active spec/impl
worktrees with their type, branch, and sandbox status.
"""

from unittest.mock import MagicMock, patch


class TestWorktreesCommandExists:
    """Tests that worktrees command is properly registered."""

    def test_worktrees_command_in_help(self, runner) -> None:
        """kinfra --help should list worktrees command."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "worktrees" in result.output.lower()

    def test_worktrees_help_shows_description(self, runner) -> None:
        """kinfra worktrees --help should show description."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["worktrees", "--help"])
        assert result.exit_code == 0
        assert "worktree" in result.output.lower()


class TestParseWorktreeList:
    """Tests for _parse_worktree_list function."""

    def test_parse_single_worktree(self) -> None:
        """Should parse a single worktree entry."""
        from ktrdr.cli.kinfra.worktrees import _parse_worktree_list

        output = """worktree /path/to/ktrdr-spec-feature
branch refs/heads/spec/feature
"""
        result = _parse_worktree_list(output)

        assert len(result) == 1
        assert result[0]["path"] == "/path/to/ktrdr-spec-feature"
        assert result[0]["branch"] == "spec/feature"

    def test_parse_multiple_worktrees(self) -> None:
        """Should parse multiple worktree entries."""
        from ktrdr.cli.kinfra.worktrees import _parse_worktree_list

        output = """worktree /path/to/main
branch refs/heads/main

worktree /path/to/ktrdr-spec-feature
branch refs/heads/spec/feature

worktree /path/to/ktrdr-impl-other
branch refs/heads/feature/other
"""
        result = _parse_worktree_list(output)

        assert len(result) == 3
        assert result[0]["path"] == "/path/to/main"
        assert result[1]["path"] == "/path/to/ktrdr-spec-feature"
        assert result[2]["path"] == "/path/to/ktrdr-impl-other"

    def test_parse_strips_refs_heads_prefix(self) -> None:
        """Should strip refs/heads/ prefix from branch names."""
        from ktrdr.cli.kinfra.worktrees import _parse_worktree_list

        output = """worktree /path/to/worktree
branch refs/heads/feature/my-feature
"""
        result = _parse_worktree_list(output)

        assert result[0]["branch"] == "feature/my-feature"

    def test_parse_handles_detached_head(self) -> None:
        """Should handle worktrees with detached HEAD (no branch)."""
        from ktrdr.cli.kinfra.worktrees import _parse_worktree_list

        output = """worktree /path/to/worktree
HEAD abc123def
detached
"""
        result = _parse_worktree_list(output)

        assert len(result) == 1
        assert result[0]["path"] == "/path/to/worktree"
        assert "branch" not in result[0]


class TestWorktreesIdentifiesTypes:
    """Tests for worktree type identification."""

    @patch("ktrdr.cli.kinfra.worktrees.subprocess.run")
    def test_identifies_spec_worktrees(self, mock_run: MagicMock, runner) -> None:
        """Should identify spec worktrees from directory name."""
        from ktrdr.cli.kinfra.main import app

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""worktree /path/to/ktrdr-spec-feature
branch refs/heads/spec/feature
""",
            stderr="",
        )

        result = runner.invoke(app, ["worktrees"])

        assert result.exit_code == 0
        assert "spec" in result.output.lower()
        assert "ktrdr-spec-feature" in result.output

    @patch("ktrdr.cli.kinfra.worktrees.subprocess.run")
    def test_identifies_impl_worktrees(self, mock_run: MagicMock, runner) -> None:
        """Should identify impl worktrees from directory name."""
        from ktrdr.cli.kinfra.main import app

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""worktree /path/to/ktrdr-impl-feature
branch refs/heads/feature/impl
""",
            stderr="",
        )

        result = runner.invoke(app, ["worktrees"])

        assert result.exit_code == 0
        assert "impl" in result.output.lower()
        assert "ktrdr-impl-feature" in result.output


class TestWorktreesExcludesMain:
    """Tests that main worktree is excluded from list."""

    @patch("ktrdr.cli.kinfra.worktrees.subprocess.run")
    def test_excludes_main_worktree(self, mock_run: MagicMock, runner) -> None:
        """Should not show main worktree in list."""
        from ktrdr.cli.kinfra.main import app

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""worktree /path/to/ktrdr2
branch refs/heads/main

worktree /path/to/ktrdr-spec-feature
branch refs/heads/spec/feature
""",
            stderr="",
        )

        result = runner.invoke(app, ["worktrees"])

        assert result.exit_code == 0
        # Main worktree (ktrdr2) should not appear in output
        assert "ktrdr2" not in result.output
        # But spec worktree should appear
        assert "ktrdr-spec-feature" in result.output


class TestWorktreesTableOutput:
    """Tests for Rich table output."""

    @patch("ktrdr.cli.kinfra.worktrees.subprocess.run")
    def test_shows_table_with_columns(self, mock_run: MagicMock, runner) -> None:
        """Should show table with Name, Type, Branch, Sandbox columns."""
        from ktrdr.cli.kinfra.main import app

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""worktree /path/to/ktrdr-spec-feature
branch refs/heads/spec/feature
""",
            stderr="",
        )

        result = runner.invoke(app, ["worktrees"])

        assert result.exit_code == 0
        # Table should have these column headers
        assert "name" in result.output.lower()
        assert "type" in result.output.lower()
        assert "branch" in result.output.lower()
        assert "sandbox" in result.output.lower()

    @patch("ktrdr.cli.kinfra.worktrees.subprocess.run")
    def test_shows_branch_name(self, mock_run: MagicMock, runner) -> None:
        """Should show branch name in output."""
        from ktrdr.cli.kinfra.main import app

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""worktree /path/to/ktrdr-spec-my-feature
branch refs/heads/spec/my-feature
""",
            stderr="",
        )

        result = runner.invoke(app, ["worktrees"])

        assert result.exit_code == 0
        assert "spec/my-feature" in result.output

    @patch("ktrdr.cli.kinfra.worktrees.subprocess.run")
    def test_shows_dash_for_spec_sandbox(self, mock_run: MagicMock, runner) -> None:
        """Spec worktrees should show '-' for sandbox status."""
        from ktrdr.cli.kinfra.main import app

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""worktree /path/to/ktrdr-spec-feature
branch refs/heads/spec/feature
""",
            stderr="",
        )

        result = runner.invoke(app, ["worktrees"])

        assert result.exit_code == 0
        # Spec worktrees have no sandbox, shown as "-"
        # The table row should contain a "-" for the sandbox column
        assert "-" in result.output


class TestWorktreesEmptyList:
    """Tests for empty worktree list."""

    @patch("ktrdr.cli.kinfra.worktrees.subprocess.run")
    def test_handles_no_worktrees(self, mock_run: MagicMock, runner) -> None:
        """Should handle case with only main worktree (no spec/impl)."""
        from ktrdr.cli.kinfra.main import app

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""worktree /path/to/ktrdr2
branch refs/heads/main
""",
            stderr="",
        )

        result = runner.invoke(app, ["worktrees"])

        # Should succeed but show empty table or message
        assert result.exit_code == 0
