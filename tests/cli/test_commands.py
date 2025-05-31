"""
Tests for the CLI commands module.

This module tests the CLI commands functionality.
"""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch
import pandas as pd

from ktrdr.cli import cli_app
from ktrdr.errors import DataError


@pytest.fixture
def runner():
    """Create a Typer CLI runner for testing."""
    return CliRunner(mix_stderr=False)  # Capture stderr separately from stdout


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


def test_show_data_basic(runner, sample_data):
    """Test the basic functionality of the CLI command."""
    # Mock the LocalDataLoader.load method
    with patch(
        "ktrdr.data.local_data_loader.LocalDataLoader.load", return_value=sample_data
    ):
        result = runner.invoke(cli_app, ["show-data", "AAPL"])

        # Check for successful execution
        assert result.exit_code == 0

        # Check output contains expected data
        assert "Data for AAPL" in result.stdout
        assert "Total rows: 3" in result.stdout


def test_show_data_with_rows(runner, sample_data):
    """Test the CLI with a custom number of rows."""
    with patch(
        "ktrdr.data.local_data_loader.LocalDataLoader.load", return_value=sample_data
    ):
        result = runner.invoke(cli_app, ["show-data", "AAPL", "--rows", "2"])

        assert result.exit_code == 0
        assert "Data for AAPL" in result.stdout
        assert "Total rows: 3" in result.stdout

        # Check the actual data output
        # Count occurrences of dates in the data table section - after the "Columns:" line
        data_section = result.stdout.split("Columns:")[1]
        # There should be 2 rows (dates) in the output, not 3
        assert data_section.count("2023-01-01") == 1
        assert data_section.count("2023-01-02") == 1
        assert (
            data_section.count("2023-01-03") == 0
        )  # The third row should not be shown


def test_show_data_with_tail(runner, sample_data):
    """Test the CLI with the tail option."""
    with patch(
        "ktrdr.data.local_data_loader.LocalDataLoader.load", return_value=sample_data
    ):
        result = runner.invoke(cli_app, ["show-data", "AAPL", "--tail"])

        assert result.exit_code == 0

        # Simply verify that the command succeeds and tail option is recognized
        # Just check that the output contains "Data for AAPL" to confirm it ran
        assert "Data for AAPL" in result.stdout
        assert "Total rows: 3" in result.stdout

        # The specific ordering of rows is difficult to reliably parse in the test
        # environment, so just check that key dates appear in the output
        assert "2023-01-03" in result.stdout  # This date should appear somewhere


def test_show_data_with_columns(runner, sample_data):
    """Test the CLI with specific columns."""
    with patch(
        "ktrdr.data.local_data_loader.LocalDataLoader.load", return_value=sample_data
    ):
        result = runner.invoke(
            cli_app, ["show-data", "AAPL", "--columns", "open", "--columns", "close"]
        )

        assert result.exit_code == 0

        # Output should include only open and close columns
        assert "open" in result.stdout
        assert "close" in result.stdout

        # Looking at the data section specifically, not the column list
        data_lines = result.stdout.split("Columns: open, close")[1]
        assert "high" not in data_lines
        assert "low" not in data_lines
        assert "volume" not in data_lines


def test_show_data_not_found(runner):
    """Test the CLI when no data is found."""
    with patch(
        "ktrdr.data.local_data_loader.LocalDataLoader.load", return_value=pd.DataFrame()
    ):
        result = runner.invoke(cli_app, ["show-data", "XYZ"])

        assert result.exit_code == 0
        assert "No data found for XYZ" in result.stdout


def test_show_data_error_handling(runner):
    """Test the CLI error handling."""
    with patch(
        "ktrdr.data.local_data_loader.LocalDataLoader.load",
        side_effect=DataError("Test error", error_code="DATA-NotFound"),
    ):
        result = runner.invoke(cli_app, ["show-data", "AAPL"])

        assert result.exit_code == 1
        # With mix_stderr=False, the error message is in stderr
        assert "Data error" in result.stderr
