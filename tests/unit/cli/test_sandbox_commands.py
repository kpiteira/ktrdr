"""
Tests for the sandbox CLI subcommand module.

Task 2.3: Verify the sandbox CLI module is properly registered and provides help.
Task 2.4: Test the create command functionality.
Task 2.5: Test the up and down commands.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ktrdr.cli import cli_app


@pytest.fixture
def runner():
    """Create a Typer CLI runner for testing."""
    return CliRunner()


class TestSandboxCLIRegistration:
    """Tests that sandbox CLI is properly registered."""

    def test_sandbox_module_imports_without_error(self):
        """Verify sandbox module can be imported."""
        # This will fail if the module doesn't exist or has import errors
        from ktrdr.cli.sandbox import sandbox_app

        assert sandbox_app is not None
        assert sandbox_app.info.name == "sandbox"

    def test_sandbox_registered_in_cli(self, runner):
        """Verify sandbox subcommand is registered in main CLI."""
        result = runner.invoke(cli_app, ["--help"])

        assert result.exit_code == 0
        assert "sandbox" in result.output.lower()

    def test_sandbox_help_displays(self, runner):
        """Verify 'ktrdr sandbox --help' shows help text."""
        result = runner.invoke(cli_app, ["sandbox", "--help"])

        assert result.exit_code == 0
        assert "sandbox" in result.output.lower()
        # Should describe what sandbox does
        assert "isolated" in result.output.lower() or "manage" in result.output.lower()

    def test_sandbox_no_args_shows_help(self, runner):
        """Verify 'ktrdr sandbox' with no args shows help (no_args_is_help=True)."""
        result = runner.invoke(cli_app, ["sandbox"])

        # With no_args_is_help=True, Typer shows help but returns exit code 2
        # (standard behavior - help shown but no command executed)
        assert result.exit_code == 2
        assert "Usage" in result.output or "usage" in result.output.lower()


class TestSlugify:
    """Tests for the slugify helper function."""

    def test_slugify_removes_special_chars(self):
        """Verify slugify removes special characters."""
        from ktrdr.cli.sandbox import slugify

        assert slugify("my-feature") == "my-feature"
        assert slugify("my_feature") == "my-feature"
        assert slugify("My Feature!") == "my-feature"
        assert slugify("feature/branch") == "feature-branch"

    def test_slugify_normalizes_dashes(self):
        """Verify slugify collapses multiple dashes."""
        from ktrdr.cli.sandbox import slugify

        assert slugify("my--feature") == "my-feature"
        assert slugify("---test---") == "test"

    def test_slugify_lowercase(self):
        """Verify slugify converts to lowercase."""
        from ktrdr.cli.sandbox import slugify

        assert slugify("MyFeature") == "myfeature"
        assert slugify("UPPERCASE") == "uppercase"


class TestDeriveInstanceId:
    """Tests for instance ID derivation."""

    def test_derive_instance_id_from_path(self):
        """Verify instance ID is derived from directory name."""
        from ktrdr.cli.sandbox import derive_instance_id

        assert (
            derive_instance_id(Path("/home/user/ktrdr--my-feature"))
            == "ktrdr--my-feature"
        )
        assert derive_instance_id(Path("/tmp/ktrdr--test")) == "ktrdr--test"


class TestGenerateEnvFile:
    """Tests for .env.sandbox generation."""

    def test_generate_env_file_content(self, tmp_path):
        """Verify .env.sandbox contains all required variables."""
        from ktrdr.cli.sandbox import generate_env_file

        generate_env_file(tmp_path, "test-instance", slot=1)

        env_file = tmp_path / ".env.sandbox"
        assert env_file.exists()

        content = env_file.read_text()

        # Check required port variables
        assert "KTRDR_API_PORT=8001" in content
        assert "KTRDR_DB_PORT=5433" in content
        assert "KTRDR_GRAFANA_PORT=3001" in content
        assert "SLOT_NUMBER=1" in content

        # Check instance identity
        assert "INSTANCE_ID=test-instance" in content
        assert "COMPOSE_PROJECT_NAME=test-instance" in content

        # Check shared data dir
        assert "KTRDR_SHARED_DIR=" in content


class TestCreateCommand:
    """Tests for the create command."""

    @pytest.fixture
    def mock_registry_path(self, tmp_path):
        """Mock registry to use temp directory."""
        registry_dir = tmp_path / ".ktrdr" / "sandbox"
        registry_dir.mkdir(parents=True)
        registry_file = registry_dir / "instances.json"
        with patch("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir):
            with patch("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_file):
                yield registry_file

    def test_create_help_displays(self, runner):
        """Verify create command has help text."""
        result = runner.invoke(cli_app, ["sandbox", "create", "--help"])

        assert result.exit_code == 0
        assert "create" in result.output.lower()
        assert "name" in result.output.lower()

    def test_create_rejects_existing_dir(self, runner, tmp_path, mock_registry_path):
        """Verify create fails if directory already exists."""
        # The worktree is created at cwd().parent / "ktrdr--<name>"
        # So if cwd is tmp_path, worktree will be at tmp_path.parent / "ktrdr--test-exists"
        existing_dir = tmp_path.parent / "ktrdr--test-exists"
        existing_dir.mkdir(exist_ok=True)

        try:
            with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
                result = runner.invoke(cli_app, ["sandbox", "create", "test-exists"])

            assert result.exit_code == 1
            assert "already exists" in result.output.lower()
        finally:
            # Clean up
            if existing_dir.exists():
                existing_dir.rmdir()

    def test_create_rejects_invalid_slot(self, runner, tmp_path, mock_registry_path):
        """Verify create fails with invalid slot number."""
        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            result = runner.invoke(
                cli_app, ["sandbox", "create", "test", "--slot", "15"]
            )

        assert result.exit_code == 1
        assert "1-10" in result.output or "slot" in result.output.lower()


class TestLoadEnvSandbox:
    """Tests for load_env_sandbox helper."""

    def test_load_env_sandbox_parses_file(self, tmp_path):
        """Verify .env.sandbox is parsed correctly."""
        from ktrdr.cli.sandbox import load_env_sandbox

        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "KEY1=value1\nKEY2=value2\n# comment\nKEY3=value=with=equals\n"
        )

        env = load_env_sandbox(tmp_path)

        assert env["KEY1"] == "value1"
        assert env["KEY2"] == "value2"
        assert env["KEY3"] == "value=with=equals"
        assert "# comment" not in env

    def test_load_env_sandbox_returns_empty_if_missing(self, tmp_path):
        """Verify empty dict returned if file doesn't exist."""
        from ktrdr.cli.sandbox import load_env_sandbox

        env = load_env_sandbox(tmp_path)

        assert env == {}


class TestFindComposeFile:
    """Tests for find_compose_file helper."""

    def test_find_compose_file_sandbox(self, tmp_path):
        """Verify sandbox compose file is found first."""
        from ktrdr.cli.sandbox import find_compose_file

        sandbox_compose = tmp_path / "docker-compose.sandbox.yml"
        sandbox_compose.touch()

        result = find_compose_file(tmp_path)

        assert result == sandbox_compose

    def test_find_compose_file_fallback(self, tmp_path):
        """Verify fallback to main compose file."""
        from ktrdr.cli.sandbox import find_compose_file

        main_compose = tmp_path / "docker-compose.yml"
        main_compose.touch()

        result = find_compose_file(tmp_path)

        assert result == main_compose

    def test_find_compose_file_not_found(self, tmp_path):
        """Verify FileNotFoundError when no compose file exists."""
        from ktrdr.cli.sandbox import find_compose_file

        with pytest.raises(FileNotFoundError):
            find_compose_file(tmp_path)


class TestUpCommand:
    """Tests for the up command."""

    def test_up_help_displays(self, runner):
        """Verify up command has help text."""
        result = runner.invoke(cli_app, ["sandbox", "up", "--help"])

        assert result.exit_code == 0
        assert "up" in result.output.lower()
        assert "start" in result.output.lower()

    def test_up_requires_env_sandbox(self, runner, tmp_path):
        """Verify up fails if not in sandbox directory."""
        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli_app, ["sandbox", "up"])

        assert result.exit_code == 1
        assert (
            "not in a sandbox" in result.output.lower()
            or ".env.sandbox" in result.output
        )

    def test_up_requires_compose_file(self, runner, tmp_path):
        """Verify up fails if no compose file exists."""
        # Create .env.sandbox but no compose file
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test\nSLOT_NUMBER=1\n")

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli_app, ["sandbox", "up"])

        assert result.exit_code == 1
        assert "compose" in result.output.lower() or "docker" in result.output.lower()


class TestDownCommand:
    """Tests for the down command."""

    def test_down_help_displays(self, runner):
        """Verify down command has help text."""
        result = runner.invoke(cli_app, ["sandbox", "down", "--help"])

        assert result.exit_code == 0
        assert "down" in result.output.lower()
        assert "stop" in result.output.lower()

    def test_down_requires_env_sandbox(self, runner, tmp_path):
        """Verify down fails if not in sandbox directory."""
        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli_app, ["sandbox", "down"])

        assert result.exit_code == 1
        assert "not in a sandbox" in result.output.lower()

    def test_down_has_volumes_option(self, runner):
        """Verify down command has --volumes option."""
        result = runner.invoke(cli_app, ["sandbox", "down", "--help"])

        assert result.exit_code == 0
        assert "--volumes" in result.output or "-v" in result.output
