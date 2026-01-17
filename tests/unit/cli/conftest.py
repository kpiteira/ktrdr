"""Shared fixtures for CLI tests."""

import re
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from typer.testing import Result

# ANSI escape code pattern for stripping styling from output
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


class CleanResult:
    """Result wrapper that strips ANSI codes from stdout/stderr/output.

    Rich/Typer applies markdown-style formatting to help text even with
    NO_COLOR=1 - it disables colors but not bold/dim styling. This causes
    patterns like '--url' to be rendered as '\x1b[1;2m-\x1b[0m\x1b[1;2m-url\x1b[0m'
    which breaks string assertions.

    This wrapper automatically strips all ANSI escape sequences from all
    text properties while preserving the original Result behavior.
    """

    def __init__(self, result: "Result") -> None:
        self._result = result

    @property
    def exit_code(self) -> int:
        return self._result.exit_code

    @property
    def stdout(self) -> str:
        return ANSI_ESCAPE_PATTERN.sub("", self._result.stdout)

    @property
    def stderr(self) -> str:
        if self._result.stderr is None:
            return ""
        return ANSI_ESCAPE_PATTERN.sub("", self._result.stderr)

    @property
    def output(self) -> str:
        """The terminal output (mixed stdout+stderr) with ANSI codes stripped."""
        return ANSI_ESCAPE_PATTERN.sub("", self._result.output)

    @property
    def exception(self):
        return self._result.exception

    @property
    def exc_info(self):
        return self._result.exc_info

    @property
    def return_value(self):
        return self._result.return_value


class CleanCliRunner(CliRunner):
    """CLI runner that returns results with ANSI codes stripped."""

    def invoke(self, *args, **kwargs) -> CleanResult:
        result = super().invoke(*args, **kwargs)
        return CleanResult(result)


@pytest.fixture
def runner():
    """CLI runner with ANSI codes stripped for consistent test output.

    This fixture provides a CliRunner that:
    1. Sets NO_COLOR=1 to disable Rich color output
    2. Strips any remaining ANSI escape codes from stdout/stderr

    Rich's markdown processor applies bold/dim styling to CLI-like patterns
    (e.g., '--url') even with NO_COLOR. This causes string assertions to fail
    in CI. The CleanResult wrapper handles this automatically.
    """
    return CleanCliRunner(env={"NO_COLOR": "1"})


# Names of dynamically registered test commands that should be cleaned up
_TEST_COMMAND_NAMES = {
    "test-cmd",
    "capture-json",
    "capture-verbose",
    "capture-v",
    "capture-url",
    "capture-u",
    "capture-port",
    "capture-p",
    "capture-precedence",
    "check-state",
    "capture-norm",
    "capture-port-norm",
}


def _cleanup_test_commands():
    """Remove dynamically registered test commands from the app."""
    try:
        from ktrdr.cli.app import app

        app.registered_commands = [
            cmd
            for cmd in app.registered_commands
            if cmd.name not in _TEST_COMMAND_NAMES
        ]
    except ImportError:
        pass  # App not imported in this test


def _restore_m3_commands():
    """Ensure M3 commands (list, show, validate, migrate) are registered.

    Some tests re-register and then remove these commands, which breaks
    subsequent tests. This ensures they're always present.
    """
    try:
        from ktrdr.cli.app import app
        from ktrdr.cli.commands.list_cmd import list_app
        from ktrdr.cli.commands.migrate import migrate_cmd
        from ktrdr.cli.commands.show import show_app
        from ktrdr.cli.commands.validate import validate_cmd

        # Restore list_app group
        list_registered = any(
            g.typer_instance is list_app for g in app.registered_groups
        )
        if not list_registered:
            app.add_typer(list_app)

        # Restore show_app group
        show_registered = any(
            g.typer_instance is show_app for g in app.registered_groups
        )
        if not show_registered:
            app.add_typer(show_app)

        # Restore validate command
        validate_registered = any(
            cmd.name == "validate" for cmd in app.registered_commands
        )
        if not validate_registered:
            app.command("validate")(validate_cmd)

        # Restore migrate command
        migrate_registered = any(
            cmd.name == "migrate" for cmd in app.registered_commands
        )
        if not migrate_registered:
            app.command("migrate")(migrate_cmd)
    except ImportError:
        pass  # App or commands not imported in this test


@pytest.fixture(autouse=True)
def cleanup_app_commands():
    """Clean up dynamically registered test commands before and after each test.

    Some tests register temporary commands on the app to capture state.
    This fixture ensures those commands are cleaned up even if tests fail,
    preventing test pollution. Cleanup runs both before (to handle pollution
    from previous tests) and after each test.

    Also ensures M3 commands (list, show, validate, migrate) remain registered,
    as some tests incorrectly remove them during cleanup.
    """
    # Clean up before test (handle pollution from previous tests)
    _cleanup_test_commands()
    _restore_m3_commands()
    yield
    # Clean up after test
    _cleanup_test_commands()
    _restore_m3_commands()
