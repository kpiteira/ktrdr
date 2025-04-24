"""
Tests for the compute-indicator command.

This module contains tests for the compute-indicator CLI command.
"""

import json
import pytest
import pandas as pd
from typer.testing import CliRunner
from unittest.mock import patch, mock_open
from pathlib import Path

from ktrdr.cli.commands import cli_app
from ktrdr.errors import DataError
from ktrdr.indicators import RSIIndicator, SimpleMovingAverage


@pytest.fixture
def runner():
    """Create a Typer CLI runner for testing."""
    return CliRunner(mix_stderr=False)


@pytest.fixture
def sample_data():
    """Create a simple DataFrame for testing with ascending prices."""
    # Create sample OHLCV data with a clear trend for predictable indicator values
    data = {
        'open': [100.0, 101.0, 103.0, 106.0, 109.0, 110.0, 112.0, 115.0, 110.0, 108.0],
        'high': [105.0, 106.0, 107.0, 110.0, 115.0, 116.0, 118.0, 120.0, 115.0, 112.0],
        'low': [95.0, 96.0, 100.0, 102.0, 105.0, 105.0, 108.0, 110.0, 105.0, 103.0],
        'close': [102.0, 105.0, 107.0, 110.0, 112.0, 114.0, 116.0, 118.0, 112.0, 105.0],
        'volume': [1000, 1100, 1200, 1250, 1300, 1350, 1400, 1450, 1300, 1200]
    }
    df = pd.DataFrame(data)
    # Add a datetime index
    df.index = pd.date_range(start='2023-01-01', periods=10)
    return df


@pytest.fixture
def sample_config():
    """Create a sample indicator configuration."""
    return {
        "indicators": [
            {
                "type": "RSI",
                "params": {
                    "period": 2,
                    "source": "close"
                }
            },
            {
                "type": "SMA",
                "params": {
                    "period": 3,
                    "source": "close"
                }
            }
        ]
    }


def test_compute_indicator_with_type_params(runner, sample_data):
    """Test computing an indicator using type and parameters."""
    with patch('ktrdr.data.data_manager.DataManager.load_data', return_value=sample_data):
        result = runner.invoke(cli_app, [
            "compute-indicator", 
            "AAPL", 
            "--type", "RSI", 
            "--period", "2"
        ])
        
        # Check for successful execution
        assert result.exit_code == 0
        
        # Check that the output contains expected information
        assert "Data for AAPL (1d) with indicators" in result.stdout
        assert "RSI" in result.stdout
        
        # RSI values should be in the output with a 2-period calculation
        # The exact values aren't important for the test, but the output should contain RSI values
        assert "Indicator Details" in result.stdout
        assert "period" in result.stdout
        assert "2" in result.stdout


def test_compute_indicator_with_config_file(runner, sample_data, sample_config):
    """Test computing indicators using a configuration file."""
    with patch('ktrdr.data.data_manager.DataManager.load_data', return_value=sample_data), \
         patch('pathlib.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=json.dumps(sample_config))), \
         patch('yaml.safe_load', return_value=sample_config):
        
        result = runner.invoke(cli_app, [
            "compute-indicator", 
            "AAPL", 
            "--config", "test_config.yaml"
        ])
        
        # Check for successful execution
        assert result.exit_code == 0
        
        # Check that the output contains expected indicators
        assert "RSI" in result.stdout
        assert "SMA" in result.stdout


def test_compute_indicator_output_formats(runner, sample_data):
    """Test different output formats."""
    with patch('ktrdr.data.data_manager.DataManager.load_data', return_value=sample_data):
        # Test CSV format
        result_csv = runner.invoke(cli_app, [
            "compute-indicator", 
            "AAPL", 
            "--type", "SMA", 
            "--period", "3",
            "--format", "csv"
        ])
        assert result_csv.exit_code == 0
        assert "," in result_csv.stdout  # CSV should contain commas
        
        # Test JSON format
        result_json = runner.invoke(cli_app, [
            "compute-indicator", 
            "AAPL", 
            "--type", "SMA", 
            "--period", "3",
            "--format", "json"
        ])
        assert result_json.exit_code == 0
        assert "{" in result_json.stdout  # JSON should contain curly braces
        
        # Verify we can parse the JSON output
        try:
            json_lines = result_json.stdout.strip().split('\n')
            json_str = '\n'.join(json_lines)
            parsed_json = json.loads(json_str)
            assert isinstance(parsed_json, list)
            assert len(parsed_json) > 0
        except json.JSONDecodeError:
            pytest.fail("JSON output is not valid")


def test_compute_indicator_missing_params(runner):
    """Test error handling when missing required parameters."""
    # Test missing both config and type
    result = runner.invoke(cli_app, [
        "compute-indicator", 
        "AAPL"
    ])
    assert result.exit_code != 0
    assert "Either --config or --type must be specified" in result.stderr
    
    # Test type specified but missing period
    result = runner.invoke(cli_app, [
        "compute-indicator", 
        "AAPL",
        "--type", "RSI"
    ])
    assert result.exit_code != 0
    assert "Period must be specified when using --type" in result.stderr


def test_compute_indicator_invalid_inputs(runner):
    """Test error handling with invalid inputs."""
    # Test invalid symbol
    result = runner.invoke(cli_app, [
        "compute-indicator", 
        "A@PL",
        "--type", "RSI",
        "--period", "14"
    ])
    assert result.exit_code != 0
    assert "Validation error" in result.stderr
    
    # Test invalid format
    result = runner.invoke(cli_app, [
        "compute-indicator", 
        "AAPL",
        "--type", "RSI",
        "--period", "14",
        "--format", "xml"  # Not a supported format
    ])
    assert result.exit_code != 0
    assert "Validation error" in result.stderr


def test_compute_indicator_data_not_found(runner):
    """Test behavior when no data is found."""
    with patch('ktrdr.data.data_manager.DataManager.load_data', return_value=None):
        result = runner.invoke(cli_app, [
            "compute-indicator", 
            "NONEXIST",  # Using a valid symbol format that passes validation
            "--type", "RSI",
            "--period", "14"
        ])
        
        assert "No data found" in result.stdout


def test_compute_indicator_data_error(runner):
    """Test behavior when a DataError is raised."""
    with patch('ktrdr.data.data_manager.DataManager.load_data', 
               side_effect=DataError(message="Data error", error_code="TEST-Error")):
        result = runner.invoke(cli_app, [
            "compute-indicator", 
            "AAPL",
            "--type", "RSI",
            "--period", "14"
        ])
        
        assert result.exit_code != 0
        assert "Data error" in result.stderr


def test_compute_indicator_insufficient_data(runner, sample_data):
    """Test graceful handling of insufficient data for indicator calculation."""
    with patch('ktrdr.data.data_manager.DataManager.load_data', return_value=sample_data):
        # Try to compute RSI with a period that's too large for the sample data
        result = runner.invoke(cli_app, [
            "compute-indicator", 
            "AAPL", 
            "--type", "RSI", 
            "--period", "20"  # This is larger than our sample data size
        ])
        
        # The command should execute but show an error about insufficient data
        assert "Error computing RSI" in result.stderr
        assert "Insufficient data" in result.stderr