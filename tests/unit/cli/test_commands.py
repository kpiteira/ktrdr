"""
Tests for the CLI commands module.

This module tests the hierarchical CLI commands functionality that uses
API client for data operations.
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from ktrdr.cli import cli_app

if TYPE_CHECKING:
    from typer.testing import CliRunner

# runner fixture is provided by conftest.py with NO_COLOR=1


@pytest.fixture
def sample_data():
    """Create a simple DataFrame for testing."""
    # Create sample OHLCV data
    data = {
        "open": [100.0, 101.0, 102.0],
        "high": [105.0, 106.0, 107.0],
        "low": [95.0, 96.0, 97.0],
        "close": [102.0, 103.0, 104.0],
        "volume": [1000, 1100, 1200],
    }
    df = pd.DataFrame(data)
    # Add a datetime index
    df.index = pd.date_range(start="2023-01-01", periods=3)
    return df


@pytest.fixture
def sample_api_response():
    """Create a sample API response for data loading."""
    return {
        "success": True,
        "data": {
            "dates": ["2023-01-01", "2023-01-02", "2023-01-03"],
            "ohlcv": [
                [100.0, 105.0, 95.0, 102.0, 1000],
                [101.0, 106.0, 96.0, 103.0, 1100],
                [102.0, 107.0, 97.0, 104.0, 1200],
            ],
            "metadata": {
                "symbol": "AAPL",
                "timeframe": "1d",
                "start": "2023-01-01",
                "end": "2023-01-03",
                "points": 3,
            },
        },
    }


@pytest.fixture
def mock_api_client():
    """Mock the AsyncCLIClient for testing."""
    with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
        mock_cli = AsyncMock()
        mock_cli.__aenter__.return_value = mock_cli
        mock_cli.__aexit__.return_value = None
        mock_cli_class.return_value = mock_cli
        yield mock_cli


def test_data_show_basic(runner, sample_api_response):
    """Test the basic functionality of the data show command."""

    with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
        # Set up AsyncCLIClient mock
        mock_cli = AsyncMock()
        mock_cli.__aenter__.return_value = mock_cli
        mock_cli.__aexit__.return_value = None
        # Return full API response structure, not just the data field
        mock_cli._make_request.return_value = sample_api_response
        mock_cli_class.return_value = mock_cli

        result = runner.invoke(cli_app, ["data", "show", "AAPL"])

        # Check for successful execution
        assert result.exit_code == 0

        # Check output contains expected data
        assert "AAPL" in result.stdout
        assert "3" in result.stdout  # Number of rows
        assert "102.0000" in result.stdout  # Sample data point  # Sample data point


def test_data_show_with_rows(runner, mock_api_client, sample_api_response):
    """Test the data show command with custom number of rows."""

    mock_api_client._make_request.return_value = sample_api_response

    result = runner.invoke(cli_app, ["data", "show", "AAPL", "--rows", "2"])

    assert result.exit_code == 0
    assert "AAPL" in result.stdout


def test_data_show_with_timeframe(runner, mock_api_client, sample_api_response):
    """Test the data show command with timeframe option."""

    mock_api_client._make_request.return_value = sample_api_response

    result = runner.invoke(cli_app, ["data", "show", "AAPL", "--timeframe", "1h"])

    assert result.exit_code == 0


def test_data_show_json_format(runner, sample_api_response):
    """Test the data show command with JSON output format."""

    with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
        # Set up AsyncCLIClient mock
        mock_cli = AsyncMock()
        mock_cli.__aenter__.return_value = mock_cli
        mock_cli.__aexit__.return_value = None
        # Return full API response structure, not just the data field
        mock_cli._make_request.return_value = sample_api_response
        mock_cli_class.return_value = mock_cli

        result = runner.invoke(cli_app, ["data", "show", "AAPL", "--format", "json"])

        assert result.exit_code == 0
        # Should contain JSON output
        assert "{" in result.stdout or "json" in result.stdout.lower()


def test_data_show_no_data(runner):
    """Test the data show command when no data is found."""
    from ktrdr.cli.async_cli_client import AsyncCLIClientError

    with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
        # Set up AsyncCLIClient mock to raise 404 error
        mock_cli = AsyncMock()
        mock_cli.__aenter__.return_value = mock_cli
        mock_cli.__aexit__.return_value = None
        mock_cli._make_request.side_effect = AsyncCLIClientError(
            "API request failed: Not Found",
            error_code="CLI-404",
        )
        mock_cli_class.return_value = mock_cli

        result = runner.invoke(cli_app, ["data", "show", "XYZ"])

        # Should handle gracefully - AsyncCLIClient shows friendly message and exits normally
        assert result.exit_code == 0  # New AsyncCLIClient handles 404 gracefully
        assert "No cached data found" in result.stdout


def test_data_show_empty_data(runner, mock_api_client):
    """Test the data show command when data is empty but API call succeeds."""
    # Mock _make_request to return empty data (should be handled gracefully)

    mock_api_client._make_request.return_value = {
        "success": True,
        "data": {
            "dates": [],
            "ohlcv": [],
            "metadata": {},
        },
    }

    result = runner.invoke(cli_app, ["data", "show", "AAPL"])

    # Should exit successfully but show no data message
    assert result.exit_code == 0
    assert (
        "No cached data found" in result.stdout
        or "No data points available" in result.stdout
    )


def test_data_show_api_connection_error(runner):
    """Test the data show command when API connection fails."""
    from ktrdr.cli.async_cli_client import AsyncCLIClientError

    with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
        # Set up AsyncCLIClient mock to raise connection error
        mock_cli = AsyncMock()
        mock_cli.__aenter__.return_value = mock_cli
        mock_cli.__aexit__.return_value = None
        mock_cli._make_request.side_effect = AsyncCLIClientError(
            "Could not connect to API server",
            error_code="CLI-ConnectionError",
        )
        mock_cli_class.return_value = mock_cli

        result = runner.invoke(cli_app, ["data", "show", "AAPL"])

        # Should exit with error when connection fails
        assert (
            result.exit_code == 1
        )  # AsyncCLIClient exits with code 1 for connection errors
        assert "Could not connect" in (result.stderr or "")


def test_data_show_help(runner):
    """Test that the data show command help text is displayed correctly."""
    result = runner.invoke(cli_app, ["data", "show", "--help"])
    assert result.exit_code == 0
    assert "show" in result.stdout
    assert "symbol" in result.stdout.lower()
    assert "timeframe" in result.stdout.lower()


def test_data_command_help(runner):
    """Test that the data command category help is displayed correctly."""
    result = runner.invoke(cli_app, ["data", "--help"])
    assert result.exit_code == 0
    assert "show" in result.stdout
    assert "load" in result.stdout


class TestMainCliCallback:
    """Tests for main CLI callback with --port flag and auto-detection."""

    def test_port_flag_accepted(self, runner: "CliRunner") -> None:
        """--port flag is accepted without error."""
        result = runner.invoke(cli_app, ["--port", "8001", "--help"])

        assert result.exit_code == 0
        # CLI accepted the flag without error

    def test_url_and_port_together_accepted(self, runner: "CliRunner") -> None:
        """--url and --port flags can be used together (--url wins)."""
        result = runner.invoke(
            cli_app, ["--url", "http://remote:9000", "--port", "8001", "--help"]
        )

        assert result.exit_code == 0
        # CLI accepted both flags without error

    def test_port_flag_in_help(self, runner: "CliRunner") -> None:
        """--port flag is documented in help output."""
        result = runner.invoke(cli_app, ["--help"])

        assert result.exit_code == 0
        assert "--port" in result.stdout or "-p" in result.stdout
        assert "API port on localhost" in result.stdout

    def test_url_flag_in_help(self, runner: "CliRunner") -> None:
        """--url flag is documented in help output with auto-detection note."""
        result = runner.invoke(cli_app, ["--help"])

        assert result.exit_code == 0
        assert "--url" in result.stdout or "-u" in result.stdout
        assert "Overrides auto-detection" in result.stdout

    def test_help_shows_api_resolution_priority(self, runner: "CliRunner") -> None:
        """Help output explains API URL resolution priority order."""
        result = runner.invoke(cli_app, ["--help"])

        assert result.exit_code == 0
        # Check that priority order is documented in docstring
        # Note: ANSI codes are stripped by the runner fixture automatically
        assert "Target API Resolution" in result.stdout
        assert "--url flag" in result.stdout
        assert "--port flag" in result.stdout
        assert ".env.sandbox" in result.stdout
        assert "Default" in result.stdout

    def test_existing_url_flag_accepted(self, runner: "CliRunner") -> None:
        """Existing --url flag behavior is preserved."""
        result = runner.invoke(cli_app, ["--url", "backend.example.com", "--help"])

        assert result.exit_code == 0
        # CLI accepted the flag without error


class TestResolveApiUrlIntegration:
    """Tests that verify resolve_api_url is correctly integrated."""

    def test_resolve_api_url_called_with_port(self) -> None:
        """resolve_api_url is called with explicit_port when --port provided."""
        from ktrdr.cli.sandbox_detect import resolve_api_url

        # Direct test of resolve_api_url priority
        result = resolve_api_url(explicit_port=8001)
        assert result == "http://localhost:8001"

    def test_resolve_api_url_url_wins_over_port(self) -> None:
        """resolve_api_url gives priority to explicit_url over explicit_port."""
        from ktrdr.cli.sandbox_detect import resolve_api_url

        result = resolve_api_url(
            explicit_url="http://remote:9000",
            explicit_port=8001,
        )
        assert result == "http://remote:9000"

    def test_resolve_api_url_default(self) -> None:
        """resolve_api_url returns default when no flags or sandbox."""
        import tempfile
        from pathlib import Path

        from ktrdr.cli.sandbox_detect import resolve_api_url

        # Use tmp_path to ensure no .env.sandbox exists
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve_api_url(cwd=Path(tmpdir))
        assert result == "http://localhost:8000"
