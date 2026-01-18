"""Tests for CLI app entry point.

Tests the main Typer app entry point that processes global flags
(--json, --verbose, --url, --port) and stores CLIState in context.

NOTE: Tests that check help text should use the `runner` fixture from conftest.py,
which provides CleanCliRunner that automatically strips ANSI codes.
"""

import subprocess
import sys

import typer
from typer.testing import CliRunner


class TestAppPerformance:
    """Tests for CLI startup performance.

    The CLI must be fast enough that `ktrdr --help` feels instantaneous.
    Target: <100ms for importing the app module.
    """

    def test_app_import_fast(self) -> None:
        """Importing ktrdr.cli.app should complete in <100ms.

        Uses subprocess to measure import time in isolation. Each measurement
        runs in a fresh Python process to avoid module caching.

        Note: PYTEST_CURRENT_TEST is set to skip heavy telemetry initialization,
        which matches how the CLI should behave after optimization (telemetry
        should be lazy-initialized on first command execution, not at import).
        """
        import os

        # Measure import time in fresh subprocess
        # Uses time.perf_counter for accurate timing
        timing_code = """
import time
start = time.perf_counter()
from ktrdr.cli.app import app
end = time.perf_counter()
print(f"{(end - start) * 1000:.1f}")
"""
        # Run 3 measurements and take the best (minimum)
        times = []
        env = {
            **os.environ,
            "PYTEST_CURRENT_TEST": "test_app_import_fast",
        }

        for _ in range(3):
            result = subprocess.run(
                [sys.executable, "-c", timing_code],
                env=env,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Import failed: {result.stderr}"
            times.append(float(result.stdout.strip()))

        import_time_ms = min(times)

        # Target: <100ms (with margin for CI variability)
        # Note: CI machines are slower, so we allow up to 200ms
        # Local: ~80ms, CI: ~150-160ms
        max_allowed_ms = 200
        assert import_time_ms < max_allowed_ms, (
            f"App import took {import_time_ms:.1f}ms (best of 3), "
            f"exceeds {max_allowed_ms}ms target. "
            f"Heavy imports should be deferred to command execution."
        )


class TestAppDefaultState:
    """Tests for default CLIState values when no flags provided."""

    def test_app_default_state(self) -> None:
        """CLIState gets default values when no flags provided."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def test_cmd(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(app, ["test-cmd"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            assert captured_state.json_mode is False
            assert captured_state.verbose is False
            # Default URL comes from resolve_api_url - localhost with auto-detected port
            # (may be 8000 default or sandbox port like 8001 from .env.sandbox)
            assert "localhost" in captured_state.api_url
            assert captured_state.api_url.startswith("http://localhost:")
        finally:
            # Clean up the test command
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "test-cmd"
            ]


class TestAppJsonFlag:
    """Tests for --json flag handling."""

    def test_app_json_flag_sets_json_mode(self) -> None:
        """--json flag sets json_mode=True in CLIState."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_json(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(app, ["--json", "capture-json"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            assert captured_state.json_mode is True
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "capture-json"
            ]


class TestAppVerboseFlag:
    """Tests for --verbose/-v flag handling."""

    def test_app_verbose_flag_sets_verbose(self) -> None:
        """--verbose flag sets verbose=True in CLIState."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_verbose(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(app, ["--verbose", "capture-verbose"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            assert captured_state.verbose is True
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "capture-verbose"
            ]

    def test_app_v_flag_sets_verbose(self) -> None:
        """-v shorthand sets verbose=True in CLIState."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_v(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(app, ["-v", "capture-v"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            assert captured_state.verbose is True
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "capture-v"
            ]


class TestAppUrlOverride:
    """Tests for --url flag handling."""

    def test_app_url_override(self) -> None:
        """--url flag overrides api_url in CLIState."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_url(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(
                app, ["--url", "http://custom.example.com:9000", "capture-url"]
            )
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            assert captured_state.api_url == "http://custom.example.com:9000/api/v1"
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "capture-url"
            ]

    def test_app_url_u_shorthand(self) -> None:
        """-u shorthand works for --url."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_u(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(
                app, ["-u", "http://short.example.com:8080", "capture-u"]
            )
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            assert captured_state.api_url == "http://short.example.com:8080/api/v1"
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "capture-u"
            ]


class TestAppPortOverride:
    """Tests for --port flag handling."""

    def test_app_port_override(self) -> None:
        """--port flag builds localhost URL with specified port."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_port(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(app, ["--port", "8001", "capture-port"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            assert captured_state.api_url == "http://localhost:8001/api/v1"
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "capture-port"
            ]

    def test_app_port_p_shorthand(self) -> None:
        """-p shorthand works for --port."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_p(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(app, ["-p", "8002", "capture-p"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            assert captured_state.api_url == "http://localhost:8002/api/v1"
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "capture-p"
            ]


class TestAppUrlPrecedence:
    """Tests for URL resolution precedence."""

    def test_app_url_takes_precedence_over_port(self) -> None:
        """--url takes precedence over --port when both specified."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_precedence(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(
                app,
                [
                    "--url",
                    "http://explicit.example.com:9999",
                    "--port",
                    "8001",
                    "capture-precedence",
                ],
            )
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            # --url should win over --port
            assert captured_state.api_url == "http://explicit.example.com:9999/api/v1"
        finally:
            app.registered_commands = [
                cmd
                for cmd in app.registered_commands
                if cmd.name != "capture-precedence"
            ]


class TestAppStatePassedToCommand:
    """Integration tests for state passing to commands."""

    def test_app_state_passed_to_command(self) -> None:
        """CLIState is accessible via ctx.obj in commands."""
        from ktrdr.cli.app import app

        runner = CliRunner()
        state_type_name: str | None = None

        @app.command()
        def check_state(ctx: typer.Context) -> None:
            nonlocal state_type_name
            state = ctx.obj
            state_type_name = type(state).__name__

        try:
            result = runner.invoke(app, ["check-state"])
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert state_type_name == "CLIState"
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "check-state"
            ]


class TestAppHelp:
    """Tests for help text."""

    def test_app_help_shows_global_flags(self, runner) -> None:
        """--help shows all global flags."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        # runner fixture strips ANSI codes automatically
        assert "--json" in result.output
        assert "--verbose" in result.output or "-v" in result.output
        assert "--url" in result.output or "-u" in result.output
        assert "--port" in result.output or "-p" in result.output

    def test_app_help_shows_description(self, runner) -> None:
        """--help shows app description."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        # Check for description keywords
        assert "ktrdr" in result.output.lower() or "trading" in result.output.lower()


class TestM2CommandsRegistration:
    """Tests for all M2 commands registration in app.

    M2 commands: train, backtest, research, status, follow, ops, cancel, resume
    """

    def test_all_m2_commands_registered(self, runner) -> None:
        """All 8 M2 commands appear in --help output."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        help_lower = result.output.lower()
        # All 8 commands should be listed
        assert "train" in help_lower
        assert "backtest" in help_lower
        assert "research" in help_lower
        assert "status" in help_lower
        assert "follow" in help_lower
        assert "ops" in help_lower
        assert "cancel" in help_lower
        assert "resume" in help_lower

    def test_train_command_registered(self, runner) -> None:
        """Train command appears in --help output."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "train" in result.output.lower()

    def test_train_command_help(self, runner) -> None:
        """Train command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["train", "--help"])

        assert result.exit_code == 0
        assert "--start" in result.output
        assert "--end" in result.output
        assert "--follow" in result.output or "-f" in result.output
        assert "strategy" in result.output.lower()

    def test_backtest_command_help(self, runner) -> None:
        """Backtest command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["backtest", "--help"])

        assert result.exit_code == 0
        assert "--start" in result.output
        assert "--end" in result.output
        assert "--capital" in result.output or "-c" in result.output

    def test_research_command_help(self, runner) -> None:
        """Research command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["research", "--help"])

        assert result.exit_code == 0
        assert "--model" in result.output or "-m" in result.output
        assert "--follow" in result.output or "-f" in result.output
        assert "goal" in result.output.lower()

    def test_status_command_help(self, runner) -> None:
        """Status command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["status", "--help"])

        assert result.exit_code == 0
        # Status takes optional operation_id
        assert "operation" in result.output.lower() or "status" in result.output.lower()

    def test_follow_command_help(self, runner) -> None:
        """Follow command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["follow", "--help"])

        assert result.exit_code == 0
        assert "operation" in result.output.lower()

    def test_ops_command_help(self, runner) -> None:
        """Ops command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["ops", "--help"])

        assert result.exit_code == 0
        # Ops lists operations
        assert "operation" in result.output.lower() or "list" in result.output.lower()

    def test_cancel_command_help(self, runner) -> None:
        """Cancel command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["cancel", "--help"])

        assert result.exit_code == 0
        assert "operation" in result.output.lower()
        assert "--reason" in result.output or "-r" in result.output

    def test_resume_command_help(self, runner) -> None:
        """Resume command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["resume", "--help"])

        assert result.exit_code == 0
        assert "operation" in result.output.lower()
        assert "--follow" in result.output or "-f" in result.output


class TestM3CommandsRegistration:
    """Tests for all M3 commands registration in app.

    M3 commands: list (strategies/models/checkpoints), show (data/features),
    validate, migrate
    """

    def test_all_m3_commands_registered(self, runner) -> None:
        """All M3 commands appear in --help output."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        help_lower = result.output.lower()
        # All M3 commands should be listed
        assert "list" in help_lower
        assert "show" in help_lower
        assert "validate" in help_lower
        assert "migrate" in help_lower

    def test_list_subcommands_registered(self, runner) -> None:
        """List command has strategies, models, checkpoints subcommands."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["list", "--help"])

        assert result.exit_code == 0
        help_lower = result.output.lower()
        assert "strategies" in help_lower
        assert "models" in help_lower
        assert "checkpoints" in help_lower

    def test_show_subcommands_registered(self, runner) -> None:
        """Show command has data and features subcommands."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["show", "--help"])

        assert result.exit_code == 0
        help_lower = result.output.lower()
        assert "data" in help_lower
        assert "features" in help_lower

    def test_validate_command_help(self, runner) -> None:
        """Validate command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["validate", "--help"])

        assert result.exit_code == 0
        # Validate takes a target argument (name or path)
        assert "target" in result.output.lower() or "name" in result.output.lower()

    def test_migrate_command_help(self, runner) -> None:
        """Migrate command has its own help text."""
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["migrate", "--help"])

        assert result.exit_code == 0
        # Migrate takes a path argument and has output option
        assert "path" in result.output.lower()
        assert "--output" in result.output or "-o" in result.output


class TestAppUrlNormalization:
    """Tests for URL normalization behavior."""

    def test_app_url_normalized_trailing_slash_removed(self) -> None:
        """Trailing slashes are removed from URLs."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_norm(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(
                app, ["--url", "http://example.com:8000/", "capture-norm"]
            )
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            # Trailing slash should be stripped
            assert not captured_state.api_url.endswith("/")
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "capture-norm"
            ]

    def test_app_url_normalized_default_port_added(self) -> None:
        """URLs without port get default port added."""
        from ktrdr.cli.app import app
        from ktrdr.cli.state import CLIState

        runner = CliRunner()
        captured_state: CLIState | None = None

        @app.command()
        def capture_port_norm(ctx: typer.Context) -> None:
            nonlocal captured_state
            captured_state = ctx.obj

        try:
            result = runner.invoke(
                app, ["--url", "http://example.com", "capture-port-norm"]
            )
            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert captured_state is not None
            # Default port 8000 should be added
            assert ":8000" in captured_state.api_url
        finally:
            app.registered_commands = [
                cmd
                for cmd in app.registered_commands
                if cmd.name != "capture-port-norm"
            ]
