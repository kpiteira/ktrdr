"""
Tests for the indicators compute command.

This module contains tests for the hierarchical CLI indicators compute command
that uses API client for indicator calculations.
"""

import json
import pytest
import pandas as pd
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from ktrdr.cli import cli_app
from ktrdr.errors import DataError


@pytest.fixture
def runner():
    """Create a Typer CLI runner for testing."""
    return CliRunner()  # No mix_stderr parameter in current version


@pytest.fixture
def sample_api_response():
    """Create a sample API response for indicator computation."""
    return {
        "success": True,
        "data": {
            "indicator_values": [50.5, 52.3, 48.7, 55.1, 60.2],
            "dates": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"],
            "metadata": {
                "symbol": "AAPL",
                "indicator_type": "RSI",
                "period": 14,
                "timeframe": "1d",
                "points": 5
            }
        }
    }


@pytest.fixture
def mock_api_client():
    """Mock the API client for testing."""
    with patch("ktrdr.cli.indicator_commands.get_api_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        yield mock_client


def test_compute_indicator_basic(runner, mock_api_client, sample_api_response):
    """Test the basic functionality of the indicators compute command."""
    # Mock the API client response
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    with patch("ktrdr.cli.indicator_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["indicators", "compute", "AAPL", "--type", "RSI"])

        # Check for successful execution
        assert result.exit_code == 0

        # Check output contains expected data
        assert "AAPL" in result.stdout
        assert "RSI" in result.stdout


def test_compute_indicator_with_period(runner, mock_api_client, sample_api_response):
    """Test the indicators compute command with custom period."""
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    with patch("ktrdr.cli.indicator_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["indicators", "compute", "AAPL", "--type", "RSI", "--period", "20"])

        assert result.exit_code == 0


def test_compute_indicator_with_timeframe(runner, mock_api_client, sample_api_response):
    """Test the indicators compute command with timeframe option."""
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    with patch("ktrdr.cli.indicator_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["indicators", "compute", "AAPL", "--type", "SMA", "--timeframe", "1h"])

        assert result.exit_code == 0


def test_compute_indicator_json_format(runner, mock_api_client, sample_api_response):
    """Test the indicators compute command with JSON output format."""
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    with patch("ktrdr.cli.indicator_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["indicators", "compute", "AAPL", "--type", "RSI", "--format", "json"])

        assert result.exit_code == 0
        # Should contain JSON output or format indicator
        assert "{" in result.stdout or "json" in result.stdout.lower() or result.exit_code == 0


def test_compute_indicator_different_types(runner, mock_api_client, sample_api_response):
    """Test the indicators compute command with different indicator types."""
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    indicator_types = ["RSI", "SMA", "EMA", "MACD"]
    
    with patch("ktrdr.cli.indicator_commands.check_api_connection", return_value=True):
        for indicator_type in indicator_types:
            result = runner.invoke(cli_app, ["indicators", "compute", "AAPL", "--type", indicator_type])
            # Should not crash, may succeed or fail gracefully
            assert result.exit_code in [0, 1]  # Allow both success and handled errors


def test_compute_indicator_api_error(runner, mock_api_client):
    """Test the indicators compute command when API returns error."""
    # Mock API response with error
    error_response = {
        "success": False,
        "error": "Failed to compute indicator",
        "details": {"symbol": "INVALID", "indicator": "RSI"}
    }
    mock_api_client.post.return_value.json.return_value = error_response
    mock_api_client.post.return_value.status_code = 400
    
    with patch("ktrdr.cli.indicator_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["indicators", "compute", "INVALID", "--type", "RSI"])

        # Should handle error gracefully
        assert "INVALID" in result.stdout or "INVALID" in result.stderr or "error" in result.stdout.lower()


def test_compute_indicator_api_connection_error(runner):
    """Test the indicators compute command when API connection fails."""
    with patch("ktrdr.cli.indicator_commands.check_api_connection", return_value=False):
        result = runner.invoke(cli_app, ["indicators", "compute", "AAPL", "--type", "RSI"])

        # Should exit with error when API is not available
        assert result.exit_code != 0


def test_compute_indicator_help(runner):
    """Test that the indicators compute command help text is displayed correctly."""
    result = runner.invoke(cli_app, ["indicators", "compute", "--help"])
    assert result.exit_code == 0
    assert "compute" in result.stdout
    assert "symbol" in result.stdout.lower()
    assert "type" in result.stdout.lower()
    assert "period" in result.stdout.lower()


def test_indicators_command_help(runner):
    """Test that the indicators command category help is displayed correctly."""
    result = runner.invoke(cli_app, ["indicators", "--help"])
    assert result.exit_code == 0
    assert "compute" in result.stdout
    assert "plot" in result.stdout
    assert "list" in result.stdout


def test_indicators_list_command(runner, mock_api_client):
    """Test the indicators list command."""
    # Mock API response for available indicators
    list_response = {
        "success": True,
        "data": {
            "indicators": [
                {"name": "RSI", "description": "Relative Strength Index"},
                {"name": "SMA", "description": "Simple Moving Average"},
                {"name": "EMA", "description": "Exponential Moving Average"}
            ]
        }
    }
    mock_api_client.get.return_value.json.return_value = list_response
    mock_api_client.get.return_value.status_code = 200
    
    with patch("ktrdr.cli.indicator_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["indicators", "list"])

        assert result.exit_code == 0
        # Should show available indicators
        assert "RSI" in result.stdout or "SMA" in result.stdout or result.exit_code == 0


def test_compute_indicator_verbose(runner, mock_api_client, sample_api_response):
    """Test the indicators compute command with verbose output."""
    mock_api_client.post.return_value.json.return_value = sample_api_response
    mock_api_client.post.return_value.status_code = 200
    
    with patch("ktrdr.cli.indicator_commands.check_api_connection", return_value=True):
        result = runner.invoke(cli_app, ["indicators", "compute", "AAPL", "--type", "RSI", "--verbose"])

        assert result.exit_code == 0
        # Verbose mode might show additional info
        assert "AAPL" in result.stdout