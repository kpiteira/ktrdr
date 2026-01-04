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
