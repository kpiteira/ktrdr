"""
Tests for the CLI commands module.

This module tests the hierarchical CLI commands functionality that uses
API client for data operations.
"""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
import pandas as pd
import json

from ktrdr.cli import cli_app
from ktrdr.errors import DataError


@pytest.fixture
def runner():
    """Create a Typer CLI runner for testing."""
    return CliRunner()  # No mix_stderr parameter in current version


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
    """Mock the API client for testing."""
    with patch("ktrdr.cli.data_commands.get_api_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        yield mock_client


def test_data_show_basic(runner, mock_api_client, sample_api_response):
    """Test the basic functionality of the data show command."""
    # Mock the async get_cached_data method to return just the data portion
    # (since get_cached_data returns response.get("data", {}), not the full response)
    import asyncio

    async def mock_get_cached_data(*args, **kwargs):
        return sample_api_response["data"]

    mock_api_client.get_cached_data = mock_get_cached_data

    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "AAPL"])

        # Check for successful execution
        assert result.exit_code == 0

        # Check output contains expected data
        assert "AAPL" in result.stdout
        assert "3" in result.stdout  # Number of rows
        assert "102.0000" in result.stdout  # Sample data point


def test_data_show_with_rows(runner, mock_api_client, sample_api_response):
    """Test the data show command with custom number of rows."""
    import asyncio

    async def mock_get_cached_data(*args, **kwargs):
        return sample_api_response["data"]

    mock_api_client.get_cached_data = mock_get_cached_data

    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "AAPL", "--rows", "2"])

        assert result.exit_code == 0
        assert "AAPL" in result.stdout


def test_data_show_with_timeframe(runner, mock_api_client, sample_api_response):
    """Test the data show command with timeframe option."""
    import asyncio

    async def mock_get_cached_data(*args, **kwargs):
        return sample_api_response["data"]

    mock_api_client.get_cached_data = mock_get_cached_data

    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "AAPL", "--timeframe", "1h"])

        assert result.exit_code == 0


def test_data_show_json_format(runner, mock_api_client, sample_api_response):
    """Test the data show command with JSON output format."""
    import asyncio

    async def mock_get_cached_data(*args, **kwargs):
        return sample_api_response["data"]

    mock_api_client.get_cached_data = mock_get_cached_data

    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "AAPL", "--format", "json"])

        assert result.exit_code == 0
        # Should contain JSON output
        assert "{" in result.stdout or "json" in result.stdout.lower()


def test_data_show_no_data(runner, mock_api_client):
    """Test the data show command when no data is found."""
    # Mock get_cached_data to raise DataError (which is what happens when API returns success: False)
    from ktrdr.errors import DataError

    async def mock_get_cached_data(*args, **kwargs):
        raise DataError(
            message="Failed to get cached data for XYZ (1d)",
            error_code="API-GetCachedDataError",
        )

    mock_api_client.get_cached_data = mock_get_cached_data

    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "XYZ"])

        # Should handle gracefully with error handling
        assert result.exit_code != 0  # Should exit with error due to DataError


def test_data_show_empty_data(runner, mock_api_client):
    """Test the data show command when data is empty but API call succeeds."""
    # Mock get_cached_data to return empty data (should be handled gracefully)
    import asyncio

    async def mock_get_cached_data(*args, **kwargs):
        return {"dates": [], "ohlcv": [], "metadata": {}}

    mock_api_client.get_cached_data = mock_get_cached_data

    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "AAPL"])

        # Should exit successfully but show no data message
        assert result.exit_code == 0
        assert (
            "No cached data found" in result.stdout
            or "No data points available" in result.stdout
        )


def test_data_show_api_connection_error(runner):
    """Test the data show command when API connection fails."""
    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=False):
        result = runner.invoke(cli_app, ["data", "show", "AAPL"])

        # Should exit with error when API is not available
        assert result.exit_code != 0


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
