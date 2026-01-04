"""
Tests for the sandbox CLI subcommand module.

Task 2.3: Verify the sandbox CLI module is properly registered and provides help.
Task 2.4: Test the create command functionality.
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
