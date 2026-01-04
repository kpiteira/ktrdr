"""
Tests for the sandbox CLI subcommand module.

Task 2.3: Verify the sandbox CLI module is properly registered and provides help.
Task 2.4: Test the create command functionality.
Task 2.5: Test the up and down commands.
Task 2.6: Test the destroy command.
Task 2.7: Test the list command.
"""

import re
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ktrdr.cli import cli_app


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text for consistent assertions."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


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

    def test_up_has_timeout_option(self, runner):
        """Verify up command has --timeout option."""
        result = runner.invoke(cli_app, ["sandbox", "up", "--help"])

        assert result.exit_code == 0
        assert "--timeout" in result.output

    def test_up_runs_gate_by_default(self, runner, tmp_path):
        """Verify gate runs when up is called without --no-wait."""
        # Setup sandbox environment
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "INSTANCE_ID=test\nSLOT_NUMBER=1\nKTRDR_API_PORT=8001\nKTRDR_DB_PORT=5433\n"
        )
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        # Mock run_gate to return a passing result
        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus, GateResult

        mock_gate_result = GateResult(
            passed=True,
            checks=[
                CheckResult(name="Database", status=CheckStatus.PASSED),
                CheckResult(name="Backend", status=CheckStatus.PASSED),
                CheckResult(name="Workers", status=CheckStatus.PASSED),
                CheckResult(name="Observability", status=CheckStatus.PASSED),
            ],
            duration_seconds=5.0,
        )

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run"):  # Mock docker compose up
                with patch(
                    "ktrdr.cli.sandbox.run_gate", return_value=mock_gate_result
                ) as mock_run_gate:
                    result = runner.invoke(cli_app, ["sandbox", "up"])

        # Gate should have been called
        mock_run_gate.assert_called_once()
        assert result.exit_code == 0
        # Should show gate results
        assert "startability gate" in result.output.lower()
        assert "passed" in result.output.lower()

    def test_up_no_wait_skips_gate(self, runner, tmp_path):
        """Verify gate is skipped with --no-wait flag."""
        # Setup sandbox environment
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test\nSLOT_NUMBER=1\n")
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run"):  # Mock docker compose up
                with patch("ktrdr.cli.sandbox.run_gate") as mock_run_gate:
                    result = runner.invoke(cli_app, ["sandbox", "up", "--no-wait"])

        # Gate should NOT have been called
        mock_run_gate.assert_not_called()
        assert result.exit_code == 0
        # Should show "starting" message instead of gate results
        assert "starting" in result.output.lower()

    def test_up_exits_on_gate_failure(self, runner, tmp_path):
        """Verify exit code 2 when gate fails."""
        # Setup sandbox environment
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "INSTANCE_ID=test\nSLOT_NUMBER=1\nKTRDR_API_PORT=8001\nKTRDR_DB_PORT=5433\n"
        )
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        # Mock run_gate to return a failing result
        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus, GateResult

        mock_gate_result = GateResult(
            passed=False,
            checks=[
                CheckResult(name="Database", status=CheckStatus.PASSED),
                CheckResult(
                    name="Backend",
                    status=CheckStatus.FAILED,
                    message="Connection refused",
                ),
                CheckResult(name="Workers", status=CheckStatus.SKIPPED),
                CheckResult(name="Observability", status=CheckStatus.PASSED),
            ],
            duration_seconds=10.0,
        )

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run"):  # Mock docker compose up
                with patch("ktrdr.cli.sandbox.run_gate", return_value=mock_gate_result):
                    result = runner.invoke(cli_app, ["sandbox", "up"])

        # Should exit with code 2 on gate failure
        assert result.exit_code == 2
        assert "failed" in result.output.lower()

    def test_up_shows_check_results(self, runner, tmp_path):
        """Verify up shows individual check results with symbols."""
        # Setup sandbox environment
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "INSTANCE_ID=test\nSLOT_NUMBER=1\nKTRDR_API_PORT=8001\nKTRDR_DB_PORT=5433\n"
            "KTRDR_GRAFANA_PORT=3001\nKTRDR_JAEGER_UI_PORT=16687\n"
        )
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus, GateResult

        mock_gate_result = GateResult(
            passed=True,
            checks=[
                CheckResult(name="Database", status=CheckStatus.PASSED),
                CheckResult(name="Backend", status=CheckStatus.PASSED),
                CheckResult(name="Workers", status=CheckStatus.PASSED),
                CheckResult(name="Observability", status=CheckStatus.PASSED),
            ],
            duration_seconds=5.0,
        )

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run"):
                with patch("ktrdr.cli.sandbox.run_gate", return_value=mock_gate_result):
                    result = runner.invoke(cli_app, ["sandbox", "up"])

        # Check that results show check names
        assert "database" in result.output.lower()
        assert "backend" in result.output.lower()
        # Should show service URLs on success
        assert "http://localhost:8001" in result.output

    def test_up_detects_port_conflict(self, runner, tmp_path):
        """Verify up fails with exit code 3 when ports are in use (Task 3.4)."""
        # Setup sandbox environment
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test\nSLOT_NUMBER=1\n")
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        # Mock check_ports_available to return conflicting ports
        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch(
                "ktrdr.cli.sandbox.check_ports_available", return_value=[8001, 5433]
            ):
                result = runner.invoke(cli_app, ["sandbox", "up"])

        # Should exit with code 3 on port conflict
        assert result.exit_code == 3
        # Should show which ports are in use
        assert "8001" in result.output or "port" in result.output.lower()
        # Should suggest diagnostic command
        assert "lsof" in result.output.lower()

    def test_up_proceeds_when_ports_free(self, runner, tmp_path):
        """Verify up proceeds normally when no port conflicts (Task 3.4)."""
        # Setup sandbox environment
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "INSTANCE_ID=test\nSLOT_NUMBER=1\nKTRDR_API_PORT=8001\nKTRDR_DB_PORT=5433\n"
        )
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus, GateResult

        mock_gate_result = GateResult(
            passed=True,
            checks=[
                CheckResult(name="Database", status=CheckStatus.PASSED),
                CheckResult(name="Backend", status=CheckStatus.PASSED),
                CheckResult(name="Workers", status=CheckStatus.PASSED),
                CheckResult(name="Observability", status=CheckStatus.PASSED),
            ],
            duration_seconds=5.0,
        )

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            # Mock ports as free (empty list = no conflicts)
            with patch("ktrdr.cli.sandbox.check_ports_available", return_value=[]):
                with patch("subprocess.run"):  # Mock docker compose up
                    with patch(
                        "ktrdr.cli.sandbox.run_gate", return_value=mock_gate_result
                    ):
                        result = runner.invoke(cli_app, ["sandbox", "up"])

        # Should succeed when ports are free
        assert result.exit_code == 0
        assert "passed" in result.output.lower()


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


class TestDestroyCommand:
    """Tests for the destroy command."""

    def test_destroy_help_displays(self, runner):
        """Verify destroy command has help text."""
        result = runner.invoke(cli_app, ["sandbox", "destroy", "--help"])

        assert result.exit_code == 0
        assert "destroy" in result.output.lower()
        assert "remove" in result.output.lower()

    def test_destroy_requires_env_sandbox(self, runner, tmp_path):
        """Verify destroy fails if not in sandbox directory."""
        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli_app, ["sandbox", "destroy", "--force"])

        assert result.exit_code == 1
        assert "not in a sandbox" in result.output.lower()

    def test_destroy_has_force_option(self, runner):
        """Verify destroy command has --force option."""
        result = runner.invoke(cli_app, ["sandbox", "destroy", "--help"])

        assert result.exit_code == 0
        assert "--force" in result.output or "-f" in result.output

    def test_destroy_has_keep_worktree_option(self, runner):
        """Verify destroy command has --keep-worktree option."""
        result = runner.invoke(cli_app, ["sandbox", "destroy", "--help"])

        assert result.exit_code == 0
        # Strip ANSI codes for consistent assertions across local/CI
        assert "--keep-worktree" in strip_ansi(result.output)

    def test_destroy_requires_confirmation(self, runner, tmp_path):
        """Verify destroy asks for confirmation without --force."""
        # Create .env.sandbox
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test-instance\nSLOT_NUMBER=1\n")

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            # Input "n" for no confirmation
            result = runner.invoke(cli_app, ["sandbox", "destroy"], input="n\n")

        # Should abort when user says no
        assert result.exit_code == 1 or "abort" in result.output.lower()

    def test_destroy_skips_confirmation_with_force(self, runner, tmp_path):
        """Verify destroy skips confirmation with --force."""
        # Create .env.sandbox and compose file
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test-instance\nSLOT_NUMBER=1\n")
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run") as mock_run:
                # Mock successful docker compose down
                mock_run.return_value.returncode = 0
                result = runner.invoke(cli_app, ["sandbox", "destroy", "--force"])

        # Should not prompt for confirmation
        assert "confirm" not in result.output.lower() or result.exit_code == 0


class TestListCommand:
    """Tests for the list command."""

    def test_list_help_displays(self, runner):
        """Verify list command has help text."""
        result = runner.invoke(cli_app, ["sandbox", "list", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()

    def test_list_empty_registry(self, runner, tmp_path):
        """Verify list shows message when no instances exist."""
        registry_dir = tmp_path / ".ktrdr" / "sandbox"
        registry_dir.mkdir(parents=True)
        registry_file = registry_dir / "instances.json"

        with patch("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir):
            with patch("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_file):
                result = runner.invoke(cli_app, ["sandbox", "list"])

        assert result.exit_code == 0
        assert "no sandbox instances" in result.output.lower()

    def test_list_shows_instances(self, runner, tmp_path):
        """Verify list shows registered instances."""
        import json

        # Create registry with an instance
        registry_dir = tmp_path / ".ktrdr" / "sandbox"
        registry_dir.mkdir(parents=True)
        registry_file = registry_dir / "instances.json"

        # Create instance directory with .env.sandbox
        instance_dir = tmp_path / "ktrdr--test-instance"
        instance_dir.mkdir()
        env_file = instance_dir / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=ktrdr--test-instance\nKTRDR_API_PORT=8001\n")

        registry_data = {
            "version": 1,
            "instances": {
                "ktrdr--test-instance": {
                    "instance_id": "ktrdr--test-instance",
                    "slot": 1,
                    "path": str(instance_dir),
                    "created_at": "2024-01-01T00:00:00Z",
                    "is_worktree": True,
                    "parent_repo": str(tmp_path),
                }
            },
        }
        registry_file.write_text(json.dumps(registry_data))

        with patch("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir):
            with patch("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_file):
                result = runner.invoke(cli_app, ["sandbox", "list"])

        assert result.exit_code == 0
        assert "ktrdr--test-instance" in result.output
        assert "8001" in result.output


class TestStatusCommand:
    """Tests for the status command (Task 3.3)."""

    def test_status_help_displays(self, runner):
        """Verify status command has help text."""
        result = runner.invoke(cli_app, ["sandbox", "status", "--help"])

        assert result.exit_code == 0
        assert "status" in result.output.lower()

    def test_status_requires_env_sandbox(self, runner, tmp_path):
        """Verify status fails if not in sandbox directory."""
        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli_app, ["sandbox", "status"])

        assert result.exit_code == 1
        assert "not in a sandbox" in result.output.lower()

    def test_status_shows_instance_info(self, runner, tmp_path):
        """Verify status shows instance ID and slot."""
        # Setup sandbox environment
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "INSTANCE_ID=ktrdr--test-feature\n"
            "SLOT_NUMBER=1\n"
            "KTRDR_API_PORT=8001\n"
            "KTRDR_DB_PORT=5433\n"
        )
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "[]"
                result = runner.invoke(cli_app, ["sandbox", "status"])

        assert result.exit_code == 0
        # Should show instance ID and slot
        assert "ktrdr--test-feature" in result.output
        assert "slot 1" in result.output.lower() or "(slot 1)" in result.output

    def test_status_shows_container_counts(self, runner, tmp_path):
        """Verify status shows running/total container counts."""
        import json

        # Setup sandbox environment
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "INSTANCE_ID=ktrdr--test\n" "SLOT_NUMBER=1\n" "KTRDR_API_PORT=8001\n"
        )
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        # Mock docker compose ps output with running containers
        containers = [
            {"Name": "backend", "State": "running"},
            {"Name": "db", "State": "running"},
            {"Name": "worker-1", "State": "running"},
        ]

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = json.dumps(containers)
                result = runner.invoke(cli_app, ["sandbox", "status"])

        assert result.exit_code == 0
        # Should show container count (3/3 or 3 of 3)
        assert "3" in result.output

    def test_status_shows_urls(self, runner, tmp_path):
        """Verify status shows all service URLs."""
        # Setup sandbox environment with all ports
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "INSTANCE_ID=ktrdr--test\n"
            "SLOT_NUMBER=1\n"
            "KTRDR_API_PORT=8001\n"
            "KTRDR_DB_PORT=5433\n"
            "KTRDR_GRAFANA_PORT=3001\n"
            "KTRDR_JAEGER_UI_PORT=16687\n"
            "KTRDR_PROMETHEUS_PORT=9091\n"
            "KTRDR_WORKER_PORT_1=5010\n"
            "KTRDR_WORKER_PORT_2=5011\n"
            "KTRDR_WORKER_PORT_3=5012\n"
            "KTRDR_WORKER_PORT_4=5013\n"
        )
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "[]"
                result = runner.invoke(cli_app, ["sandbox", "status"])

        assert result.exit_code == 0
        # Should show all service URLs
        assert "8001" in result.output  # Backend/API
        assert "5433" in result.output  # Database
        assert "3001" in result.output  # Grafana
        assert "16687" in result.output  # Jaeger
        assert "9091" in result.output  # Prometheus
        # Should show worker ports
        assert "5010" in result.output
        assert "5011" in result.output
        assert "5012" in result.output
        assert "5013" in result.output

    def test_status_works_when_stopped(self, runner, tmp_path):
        """Verify status works even when containers are stopped."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "INSTANCE_ID=ktrdr--stopped\n" "SLOT_NUMBER=2\n" "KTRDR_API_PORT=8002\n"
        )
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "[]"
                result = runner.invoke(cli_app, ["sandbox", "status"])

        assert result.exit_code == 0
        assert "ktrdr--stopped" in result.output
        # Should indicate stopped state
        assert "stopped" in result.output.lower() or "0" in result.output


class TestLogsCommand:
    """Tests for the logs command (Task 3.5)."""

    def test_logs_help_displays(self, runner):
        """Verify logs command has help text."""
        result = runner.invoke(cli_app, ["sandbox", "logs", "--help"])

        assert result.exit_code == 0
        assert "logs" in result.output.lower()
        assert "--follow" in result.output or "-f" in result.output

    def test_logs_requires_env_sandbox(self, runner, tmp_path):
        """Verify logs fails if not in sandbox directory."""
        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli_app, ["sandbox", "logs"])

        assert result.exit_code == 1
        assert "not in a sandbox" in result.output.lower()

    def test_logs_requires_compose_file(self, runner, tmp_path):
        """Verify logs fails if no compose file exists."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test\nSLOT_NUMBER=1\n")

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            result = runner.invoke(cli_app, ["sandbox", "logs"])

        assert result.exit_code == 1
        assert "compose" in result.output.lower()

    def test_logs_calls_docker_compose(self, runner, tmp_path):
        """Verify logs calls docker compose logs with correct args."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test\nSLOT_NUMBER=1\n")
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run") as mock_run:
                result = runner.invoke(cli_app, ["sandbox", "logs"])

        assert result.exit_code == 0
        # Should have called docker compose logs
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "compose" in call_args
        assert "logs" in call_args
        assert "--tail" in call_args

    def test_logs_with_service_filter(self, runner, tmp_path):
        """Verify logs can filter to specific service."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test\nSLOT_NUMBER=1\n")
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run") as mock_run:
                result = runner.invoke(cli_app, ["sandbox", "logs", "backend"])

        assert result.exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert "backend" in call_args

    def test_logs_with_follow_option(self, runner, tmp_path):
        """Verify --follow/-f option is passed to docker compose."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test\nSLOT_NUMBER=1\n")
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run") as mock_run:
                result = runner.invoke(cli_app, ["sandbox", "logs", "-f"])

        assert result.exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert "-f" in call_args

    def test_logs_with_tail_option(self, runner, tmp_path):
        """Verify --tail/-n option controls line count."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=test\nSLOT_NUMBER=1\n")
        compose_file = tmp_path / "docker-compose.sandbox.yml"
        compose_file.touch()

        with patch("ktrdr.cli.sandbox.Path.cwd", return_value=tmp_path):
            with patch("subprocess.run") as mock_run:
                result = runner.invoke(cli_app, ["sandbox", "logs", "--tail", "50"])

        assert result.exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert "--tail" in call_args
        assert "50" in call_args


class TestGetInstanceStatus:
    """Tests for get_instance_status helper."""

    def test_get_instance_status_returns_unknown_on_error(self, tmp_path):
        """Verify unknown status on docker compose error."""
        from ktrdr.cli.sandbox import get_instance_status

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            status = get_instance_status("test", compose_file, {})

        assert status == "unknown"

    def test_get_instance_status_returns_stopped_on_empty(self, tmp_path):
        """Verify stopped status when no containers found."""
        from ktrdr.cli.sandbox import get_instance_status

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "[]"
            status = get_instance_status("test", compose_file, {})

        assert status == "stopped"
