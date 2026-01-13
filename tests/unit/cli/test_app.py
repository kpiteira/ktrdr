"""Tests for CLI app entry point.

Tests the main Typer app entry point that processes global flags
(--json, --verbose, --url, --port) and stores CLIState in context.
"""

import re

import typer
from typer.testing import CliRunner


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text for reliable string matching in CI."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_pattern.sub("", text)


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
            assert captured_state.api_url == "http://custom.example.com:9000"
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
            assert captured_state.api_url == "http://short.example.com:8080"
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
            assert captured_state.api_url == "http://localhost:8001"
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
            assert captured_state.api_url == "http://localhost:8002"
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
            assert captured_state.api_url == "http://explicit.example.com:9999"
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

    def test_app_help_shows_global_flags(self) -> None:
        """--help shows all global flags."""
        from ktrdr.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        # Strip ANSI codes for reliable matching in CI
        output = strip_ansi(result.output)
        # Check for global flags
        assert "--json" in output
        assert "--verbose" in output or "-v" in output
        assert "--url" in output or "-u" in output
        assert "--port" in output or "-p" in output

    def test_app_help_shows_description(self) -> None:
        """--help shows app description."""
        from ktrdr.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        # Check for description keywords
        assert "ktrdr" in result.output.lower() or "trading" in result.output.lower()


class TestTrainCommandRegistration:
    """Tests for train command registration in app."""

    def test_train_command_registered(self) -> None:
        """Train command appears in --help output."""
        from ktrdr.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        # Train command should be listed in help output
        assert "train" in result.output.lower()

    def test_train_command_help(self) -> None:
        """Train command has its own help text."""
        from ktrdr.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["train", "--help"])

        assert result.exit_code == 0
        # Strip ANSI codes for reliable matching in CI
        output = strip_ansi(result.output)
        # Should show train-specific options
        assert "--start" in output
        assert "--end" in output
        assert "--follow" in output or "-f" in output
        assert "strategy" in output.lower()


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
