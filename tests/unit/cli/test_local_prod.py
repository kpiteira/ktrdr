"""Tests for local-prod CLI commands.

Local-prod is a singleton production-like environment using slot 0.
It differs from sandboxes in that it must be a clone (not worktree),
is a singleton, and destroy operates via registry lookup (not cwd).
"""

from unittest.mock import patch

import pytest


@pytest.fixture
def temp_registry_dir(tmp_path):
    """Create a temporary registry directory for testing."""
    registry_dir = tmp_path / ".ktrdr" / "sandbox"
    registry_dir.mkdir(parents=True)
    return registry_dir


@pytest.fixture
def mock_registry_path(temp_registry_dir):
    """Patch registry path to use temp directory."""
    registry_file = temp_registry_dir / "instances.json"
    with patch("ktrdr.cli.sandbox_registry.REGISTRY_DIR", temp_registry_dir):
        with patch("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_file):
            yield registry_file


class TestLocalProdInit:
    """Tests for local-prod init command."""

    def test_init_fails_on_worktree(self, runner, tmp_path, mock_registry_path):
        """init should reject worktrees (they have .git as a FILE)."""
        from ktrdr.cli.local_prod import local_prod_app

        # Create a fake worktree marker (file, not directory)
        (tmp_path / ".git").write_text("gitdir: /some/path/.git/worktrees/test")

        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=tmp_path):
            result = runner.invoke(local_prod_app, ["init"])

        assert result.exit_code != 0
        assert "must be a clone" in result.output.lower()

    def test_init_fails_if_already_exists(self, runner, tmp_path, mock_registry_path):
        """init should reject if local-prod already registered (singleton)."""
        from ktrdr.cli.local_prod import local_prod_app
        from ktrdr.cli.sandbox_registry import InstanceInfo, set_local_prod

        # Pre-register a local-prod
        set_local_prod(
            InstanceInfo(
                instance_id="ktrdr-prod",
                slot=0,
                path="/some/existing/path",
                created_at="2024-01-01T00:00:00Z",
                is_worktree=False,
            )
        )

        # Create a valid clone-like directory
        (tmp_path / ".git").mkdir()

        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=tmp_path):
            with patch("ktrdr.cli.local_prod.is_ktrdr_repo", return_value=True):
                result = runner.invoke(local_prod_app, ["init"])

        assert result.exit_code != 0
        assert "already exists" in result.output.lower()

    def test_init_succeeds_on_clone(self, runner, tmp_path, mock_registry_path):
        """init should succeed on a proper clone (not worktree)."""
        from ktrdr.cli.local_prod import local_prod_app
        from ktrdr.cli.sandbox_registry import get_local_prod, local_prod_exists

        # Create a valid clone (directory .git, not file)
        (tmp_path / ".git").mkdir()

        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=tmp_path):
            with patch("ktrdr.cli.local_prod.is_ktrdr_repo", return_value=True):
                result = runner.invoke(local_prod_app, ["init"])

        assert result.exit_code == 0, f"Failed with: {result.output}"
        assert local_prod_exists()

        info = get_local_prod()
        assert info is not None
        assert info.slot == 0
        assert info.is_worktree is False

    def test_init_creates_env_sandbox_with_slot_0(
        self, runner, tmp_path, mock_registry_path
    ):
        """init should create .env.sandbox with slot 0 (standard ports)."""
        from ktrdr.cli.local_prod import local_prod_app

        # Create a valid clone
        (tmp_path / ".git").mkdir()

        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=tmp_path):
            with patch("ktrdr.cli.local_prod.is_ktrdr_repo", return_value=True):
                result = runner.invoke(local_prod_app, ["init"])

        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Check .env.sandbox was created with slot 0
        env_file = tmp_path / ".env.sandbox"
        assert env_file.exists()
        content = env_file.read_text()
        assert "SLOT_NUMBER=0" in content
        assert "KTRDR_API_PORT=8000" in content

    def test_init_rejects_if_already_initialized(
        self, runner, tmp_path, mock_registry_path
    ):
        """init should reject if .env.sandbox already exists."""
        from ktrdr.cli.local_prod import local_prod_app

        # Create a valid clone with existing .env.sandbox
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").write_text("INSTANCE_ID=existing")

        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=tmp_path):
            result = runner.invoke(local_prod_app, ["init"])

        assert result.exit_code != 0
        assert "already initialized" in result.output.lower()


class TestLocalProdDestroy:
    """Tests for local-prod destroy command.

    CRITICAL: destroy MUST use registry lookup, NOT current directory.
    This prevents the disaster where destroy was run from a sandbox
    and deleted the sandbox instead of the registered local-prod.
    """

    def test_destroy_uses_registry_not_cwd(self, runner, tmp_path, mock_registry_path):
        """destroy must use registry path, not current directory.

        Scenario: User is in /path/sandbox but local-prod is at /path/local-prod.
        Destroy should destroy /path/local-prod, NOT /path/sandbox.
        """
        from ktrdr.cli.local_prod import local_prod_app
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            local_prod_exists,
            set_local_prod,
        )

        # Create two directories
        sandbox_dir = tmp_path / "sandbox"
        local_prod_dir = tmp_path / "local-prod"
        sandbox_dir.mkdir()
        local_prod_dir.mkdir()

        # Create .env.sandbox in local-prod dir
        (local_prod_dir / ".env.sandbox").write_text(
            "INSTANCE_ID=ktrdr-prod\nSLOT_NUMBER=0"
        )

        # Register local-prod pointing to local_prod_dir
        set_local_prod(
            InstanceInfo(
                instance_id="ktrdr-prod",
                slot=0,
                path=str(local_prod_dir),
                created_at="2024-01-01T00:00:00Z",
                is_worktree=False,
            )
        )

        # Run destroy from sandbox_dir (different from registered path)
        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=sandbox_dir):
            with patch("ktrdr.cli.instance_core.stop_instance", return_value=0):
                result = runner.invoke(local_prod_app, ["destroy", "--force"])

        # Should succeed and clear registry
        assert result.exit_code == 0, f"Failed with: {result.output}"
        assert not local_prod_exists()

        # Sandbox dir should NOT have been touched
        assert sandbox_dir.exists()

    def test_destroy_fails_if_no_local_prod(self, runner, mock_registry_path):
        """destroy should fail if no local-prod is registered."""
        from ktrdr.cli.local_prod import local_prod_app

        result = runner.invoke(local_prod_app, ["destroy", "--force"])

        assert result.exit_code != 0
        assert (
            "no local-prod" in result.output.lower()
            or "not found" in result.output.lower()
        )

    def test_destroy_keeps_clone_directory(self, runner, tmp_path, mock_registry_path):
        """destroy should unregister but keep the clone directory."""
        from ktrdr.cli.local_prod import local_prod_app
        from ktrdr.cli.sandbox_registry import (
            InstanceInfo,
            local_prod_exists,
            set_local_prod,
        )

        # Setup local-prod
        local_prod_dir = tmp_path / "ktrdr-prod"
        local_prod_dir.mkdir()
        (local_prod_dir / ".git").mkdir()  # Clone marker
        (local_prod_dir / ".env.sandbox").write_text(
            "INSTANCE_ID=ktrdr-prod\nSLOT_NUMBER=0"
        )
        (local_prod_dir / "ktrdr").mkdir()  # Source code

        set_local_prod(
            InstanceInfo(
                instance_id="ktrdr-prod",
                slot=0,
                path=str(local_prod_dir),
                created_at="2024-01-01T00:00:00Z",
                is_worktree=False,
            )
        )

        with patch("ktrdr.cli.instance_core.stop_instance", return_value=0):
            result = runner.invoke(local_prod_app, ["destroy", "--force"])

        assert result.exit_code == 0
        assert not local_prod_exists()

        # Clone directory should still exist
        assert local_prod_dir.exists()
        assert (local_prod_dir / "ktrdr").exists()
        # But .env.sandbox should be removed
        assert not (local_prod_dir / ".env.sandbox").exists()


class TestLocalProdUp:
    """Tests for local-prod up command."""

    def test_up_requires_local_prod_context(self, runner, tmp_path, mock_registry_path):
        """up should require being in the local-prod directory."""
        from ktrdr.cli.local_prod import local_prod_app

        # No .env.sandbox in cwd
        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=tmp_path):
            result = runner.invoke(local_prod_app, ["up"])

        assert result.exit_code != 0
        assert (
            "not in" in result.output.lower() or ".env.sandbox" in result.output.lower()
        )

    def test_up_uses_local_prod_profile(self, runner, tmp_path, mock_registry_path):
        """up should pass profile='local-prod' to start_instance."""
        from ktrdr.cli.local_prod import local_prod_app

        # Setup valid local-prod context
        (tmp_path / ".env.sandbox").write_text(
            "INSTANCE_ID=ktrdr-prod\nSLOT_NUMBER=0\nKTRDR_API_PORT=8000"
        )
        (tmp_path / "docker-compose.sandbox.yml").write_text("version: '3'")

        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=tmp_path):
            with patch("ktrdr.cli.local_prod.load_env_file") as mock_load:
                mock_load.return_value = {
                    "INSTANCE_ID": "ktrdr-prod",
                    "SLOT_NUMBER": "0",
                    "KTRDR_API_PORT": "8000",
                }
                with patch(
                    "ktrdr.cli.local_prod.start_instance", return_value=0
                ) as mock_start:
                    result = runner.invoke(local_prod_app, ["up", "--no-secrets"])

        assert result.exit_code == 0, f"Failed with: {result.output}"
        mock_start.assert_called_once()
        call_kwargs = mock_start.call_args.kwargs
        assert call_kwargs.get("profile") == "local-prod"


class TestLocalProdDown:
    """Tests for local-prod down command."""

    def test_down_requires_local_prod_context(
        self, runner, tmp_path, mock_registry_path
    ):
        """down should require being in the local-prod directory."""
        from ktrdr.cli.local_prod import local_prod_app

        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=tmp_path):
            result = runner.invoke(local_prod_app, ["down"])

        assert result.exit_code != 0

    def test_down_uses_local_prod_profile(self, runner, tmp_path, mock_registry_path):
        """down should pass profile='local-prod' to stop_instance."""
        from ktrdr.cli.local_prod import local_prod_app

        # Setup valid local-prod context
        (tmp_path / ".env.sandbox").write_text("INSTANCE_ID=ktrdr-prod\nSLOT_NUMBER=0")
        (tmp_path / "docker-compose.sandbox.yml").write_text("version: '3'")

        with patch("ktrdr.cli.local_prod.Path.cwd", return_value=tmp_path):
            with patch("ktrdr.cli.local_prod.load_env_file") as mock_load:
                mock_load.return_value = {
                    "INSTANCE_ID": "ktrdr-prod",
                    "SLOT_NUMBER": "0",
                }
                with patch(
                    "ktrdr.cli.local_prod.stop_instance", return_value=0
                ) as mock_stop:
                    result = runner.invoke(local_prod_app, ["down"])

        assert result.exit_code == 0, f"Failed with: {result.output}"
        mock_stop.assert_called_once()
        call_kwargs = mock_stop.call_args.kwargs
        assert call_kwargs.get("profile") == "local-prod"


class TestLocalProdCommandHelp:
    """Tests for command help text."""

    def test_local_prod_help_shows_commands(self, runner):
        """local-prod --help should show available commands."""
        from ktrdr.cli.local_prod import local_prod_app

        result = runner.invoke(local_prod_app, ["--help"])

        assert result.exit_code == 0
        assert "init" in result.output
        assert "up" in result.output
        assert "down" in result.output
        assert "destroy" in result.output
        assert "status" in result.output
        assert "logs" in result.output
        # Should NOT have create command
        assert (
            "create" not in result.output.lower()
            or "create" not in result.output.split()
        )

    def test_init_help(self, runner):
        """init --help should explain the command."""
        from ktrdr.cli.local_prod import local_prod_app

        result = runner.invoke(local_prod_app, ["init", "--help"])

        assert result.exit_code == 0
        assert "clone" in result.output.lower()
