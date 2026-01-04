"""Shared fixtures for CLI tests."""

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    """CLI runner with colors disabled for consistent test output.

    Rich respects the NO_COLOR environment variable, so this prevents
    ANSI escape codes from appearing in test output - avoiding CI failures
    where ANSI codes can break string assertions.

    See: https://no-color.org/
    """
    return CliRunner(env={"NO_COLOR": "1"})
