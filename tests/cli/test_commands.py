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
                [102.0, 107.0, 97.0, 104.0, 1200]
            ],
            "metadata": {
                "symbol": "AAPL",
                "timeframe": "1d",
                "start": "2023-01-01",
                "end": "2023-01-03",
                "points": 3
            }
        }
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
    # Mock the API client response
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "AAPL"])

        # Check for successful execution
        assert result.exit_code == 0

        # Check output contains expected data
        assert "AAPL" in result.stdout
        assert "3" in result.stdout  # Number of rows


def test_data_show_with_rows(runner, mock_api_client, sample_api_response):
    """Test the data show command with custom number of rows."""
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "AAPL", "--rows", "2"])

        assert result.exit_code == 0
        assert "AAPL" in result.stdout


def test_data_show_with_timeframe(runner, mock_api_client, sample_api_response):
    """Test the data show command with timeframe option."""
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "AAPL", "--timeframe", "1h"])

        assert result.exit_code == 0


def test_data_show_json_format(runner, mock_api_client, sample_api_response):
    """Test the data show command with JSON output format."""
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "AAPL", "--format", "json"])

        assert result.exit_code == 0
        # Should contain JSON output
        assert "{" in result.stdout or "json" in result.stdout.lower()


def test_data_show_no_data(runner, mock_api_client):
    """Test the data show command when no data is found."""
    # Mock API response for no data
    no_data_response = {
        "success": False,
        "error": "No data found for symbol XYZ"
    }
    mock_api_client.post.return_value.json.return_value = no_data_response
    mock_api_client.post.return_value.status_code = 404
    
    with patch("ktrdr.cli.data_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["data", "show", "XYZ"])

        # Should handle gracefully, might exit with error code
        assert "XYZ" in result.stdout or "XYZ" in result.stderr


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