"""
Tests for visualization-related CLI commands.

This module contains tests for the 'plot' and 'plot-indicators' CLI commands
added as part of Task 3.4 to integrate visualization capabilities into the CLI.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from ktrdr.cli.commands import cli_app, plot, plot_indicators
from ktrdr.errors import ConfigurationError, DataError


# Create a CliRunner instance for testing
runner = CliRunner()


@pytest.fixture
def mock_datamanager():
    """Mock DataManager to avoid loading real data files during tests."""
    with patch('ktrdr.cli.commands.DataManager') as mock_dm:
        # Set up the mock to return a DataFrame with test data
        import pandas as pd
        import numpy as np

        # Create test data
        dates = pd.date_range(start='2023-01-01', periods=20)
        test_data = pd.DataFrame({
            'open': np.random.uniform(100, 110, 20),
            'high': np.random.uniform(105, 115, 20),
            'low': np.random.uniform(95, 105, 20),
            'close': np.random.uniform(100, 110, 20),
            'volume': np.random.uniform(1000, 5000, 20),
        }, index=dates)
        
        # Configure the mock
        instance = mock_dm.return_value
        instance.load_data.return_value = test_data
        
        yield mock_dm


@pytest.fixture
def mock_visualizer():
    """Mock Visualizer to avoid creating actual HTML files during tests."""
    with patch('ktrdr.cli.commands.Visualizer') as mock_viz:
        # Set up the mock visualizer instance
        instance = mock_viz.return_value
        
        # Configure mock return values
        instance.create_chart.return_value = {'configs': [], 'data': {}}
        instance.add_indicator_overlay.return_value = {'configs': [], 'data': {}}
        instance.add_indicator_panel.return_value = {'configs': [], 'data': {}}
        instance.configure_range_slider.return_value = {'configs': [], 'data': {}}
        instance.save.return_value = Path('output/test_chart.html')
        
        yield mock_viz


@pytest.fixture
def mock_indicator_factory():
    """Mock IndicatorFactory to avoid computing real indicators during tests."""
    with patch('ktrdr.cli.commands.IndicatorFactory') as mock_if:
        # Set up the mock to return test indicators
        mock_indicator = MagicMock()
        mock_indicator.get_column_name.return_value = 'test_indicator'
        mock_indicator.compute.return_value = [1.0] * 20  # Mock indicator values
        mock_indicator.name = 'TestIndicator'
        mock_indicator.params = {'period': 20, 'source': 'close'}
        
        # Configure the factory to return our mock indicator
        instance = mock_if.return_value
        instance.build.return_value = [mock_indicator]
        
        yield mock_if


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary directory for output files."""
    output_dir = tmp_path / 'output'
    output_dir.mkdir()
    
    # Store original directory
    original_dir = os.getcwd()
    
    # Change to temp directory for the test
    os.chdir(tmp_path)
    
    # After test is done, change back to original directory
    yield output_dir
    os.chdir(original_dir)


class TestPlotCommand:
    """Tests for the 'plot' CLI command."""
    
    def test_plot_command_help(self):
        """Test that the plot command help text is displayed correctly."""
        result = runner.invoke(cli_app, ["plot", "--help"])
        assert result.exit_code == 0
        assert "Create and save interactive price charts" in result.stdout
    
    def test_plot_basic_chart(self, mock_datamanager, mock_visualizer, temp_output_dir):
        """Test creating a basic chart with the plot command."""
        # Run the plot command
        result = runner.invoke(cli_app, [
            "plot", 
            "MSFT", 
            "--output", str(temp_output_dir / "test_chart.html")
        ])
        
        # Verify command execution
        assert result.exit_code == 0
        
        # Check that the DataManager was called correctly
        mock_datamanager.assert_called_once()
        mock_datamanager.return_value.load_data.assert_called_once_with("MSFT", "1d")
        
        # Check that the Visualizer was used correctly
        mock_visualizer.assert_called_once_with(theme="dark")
        mock_visualizer.return_value.create_chart.assert_called_once()
        mock_visualizer.return_value.save.assert_called_once()
    
    def test_plot_with_indicator_overlay(self, mock_datamanager, mock_visualizer, mock_indicator_factory, temp_output_dir):
        """Test creating a chart with an indicator overlay."""
        # Run the plot command with indicator
        result = runner.invoke(cli_app, [
            "plot", 
            "MSFT", 
            "--indicator", "SMA", 
            "--period", "20",
            "--output", str(temp_output_dir / "test_chart_indicator.html")
        ])
        
        # Verify command execution
        assert result.exit_code == 0
        
        # Check that the indicator factory was called correctly
        mock_indicator_factory.assert_called_once()
        
        # Check that the indicator was added as an overlay
        mock_visualizer.return_value.add_indicator_overlay.assert_called_once()
        
        # We need to verify that the indicator was not added as a panel
        # (but the volume panel is still added by default)
        indicator_added_as_panel = False
        for call in mock_visualizer.return_value.add_indicator_panel.call_args_list:
            args, kwargs = call
            if kwargs.get('column') == 'test_indicator':
                indicator_added_as_panel = True
                break
        assert not indicator_added_as_panel, "Indicator should be added as overlay, not as panel"
    
    def test_plot_with_indicator_panel(self, mock_datamanager, mock_visualizer, mock_indicator_factory, temp_output_dir):
        """Test creating a chart with an indicator in a separate panel."""
        # Run the plot command with indicator as panel
        result = runner.invoke(cli_app, [
            "plot", 
            "MSFT", 
            "--indicator", "RSI", 
            "--period", "14",
            "--panel",
            "--output", str(temp_output_dir / "test_chart_panel.html")
        ])
        
        # Verify command execution
        assert result.exit_code == 0
        
        # Check that the indicator factory was called correctly
        mock_indicator_factory.assert_called_once()
        
        # Check that the indicator was added as a panel
        # We need to verify that add_indicator_panel was called with our test_indicator
        indicator_added_as_panel = False
        for call in mock_visualizer.return_value.add_indicator_panel.call_args_list:
            args, kwargs = call
            if kwargs.get('column') == 'test_indicator':
                indicator_added_as_panel = True
                break
        assert indicator_added_as_panel, "Indicator should be added as panel"
        
        # Check that the indicator was NOT added as an overlay
        mock_visualizer.return_value.add_indicator_overlay.assert_not_called()
    
    def test_plot_with_light_theme(self, mock_datamanager, mock_visualizer, temp_output_dir):
        """Test creating a chart with light theme."""
        # Run the plot command with light theme
        result = runner.invoke(cli_app, [
            "plot", 
            "MSFT", 
            "--theme", "light",
            "--output", str(temp_output_dir / "test_chart_light.html")
        ])
        
        # Verify command execution
        assert result.exit_code == 0
        
        # Check that the visualizer was created with light theme
        mock_visualizer.assert_called_once_with(theme="light")
    
    def test_plot_without_volume(self, mock_datamanager, mock_visualizer, temp_output_dir):
        """Test creating a chart without volume panel."""
        # Run the plot command without volume
        result = runner.invoke(cli_app, [
            "plot", 
            "MSFT", 
            "--no-volume",
            "--output", str(temp_output_dir / "test_chart_no_volume.html")
        ])
        
        # Verify command execution
        assert result.exit_code == 0
        
        # Verify that add_indicator_panel wasn't called for volume
        for call in mock_visualizer.return_value.add_indicator_panel.call_args_list:
            args, kwargs = call
            if 'column' in kwargs and kwargs['column'] == 'volume':
                pytest.fail("Volume panel was added despite --no-volume flag")
    
    def test_plot_without_range_slider(self, mock_datamanager, mock_visualizer, temp_output_dir):
        """Test creating a chart without range slider."""
        # Run the plot command without range slider
        result = runner.invoke(cli_app, [
            "plot", 
            "MSFT", 
            "--no-range-slider",
            "--output", str(temp_output_dir / "test_chart_no_slider.html")
        ])
        
        # Verify command execution
        assert result.exit_code == 0
        
        # Verify that configure_range_slider wasn't called
        mock_visualizer.return_value.configure_range_slider.assert_not_called()
    

class TestPlotIndicatorsCommand:
    """Tests for the 'plot-indicators' CLI command."""
    
    def test_plot_indicators_command_help(self):
        """Test that the plot-indicators command help text is displayed correctly."""
        result = runner.invoke(cli_app, ["plot-indicators", "--help"])
        assert result.exit_code == 0
        assert "Create multi-indicator charts" in result.stdout
    
    def test_plot_indicators_basic(self, mock_datamanager, mock_visualizer, mock_indicator_factory, temp_output_dir):
        """Test creating a multi-indicator chart."""
        # Run the plot-indicators command
        result = runner.invoke(cli_app, [
            "plot-indicators", 
            "MSFT", 
            "--output", str(temp_output_dir / "test_multi_indicator.html")
        ])
        
        # Verify command execution
        assert result.exit_code == 0
        
        # Check that the DataManager was called correctly
        mock_datamanager.assert_called_once()
        mock_datamanager.return_value.load_data.assert_called_once_with("MSFT", "1d")
        
        # Check that the Visualizer was used correctly
        mock_visualizer.assert_called_once_with(theme="dark")
        mock_visualizer.return_value.create_chart.assert_called_once()
        
        # Verify that default indicators were created and added
        mock_indicator_factory.assert_called_once()
    
    def test_plot_indicators_with_overlays(self, mock_datamanager, mock_visualizer, mock_indicator_factory, temp_output_dir):
        """Test creating a chart with indicators as overlays."""
        # Run the plot-indicators command with overlays
        result = runner.invoke(cli_app, [
            "plot-indicators", 
            "MSFT", 
            "--overlays",
            "--output", str(temp_output_dir / "test_multi_overlays.html")
        ])
        
        # Verify command execution
        assert result.exit_code == 0
        
        # At least one indicator should be added as an overlay
        assert mock_visualizer.return_value.add_indicator_overlay.called
    
    def test_plot_indicators_with_light_theme(self, mock_datamanager, mock_visualizer, mock_indicator_factory, temp_output_dir):
        """Test creating a multi-indicator chart with light theme."""
        # Run the plot-indicators command with light theme
        result = runner.invoke(cli_app, [
            "plot-indicators", 
            "MSFT", 
            "--theme", "light",
            "--output", str(temp_output_dir / "test_multi_light.html")
        ])
        
        # Verify command execution
        assert result.exit_code == 0
        
        # Check that the visualizer was created with light theme
        mock_visualizer.assert_called_once_with(theme="light")


class TestErrorHandling:
    """Tests for error handling in visualization CLI commands."""
    
    def test_plot_no_data_found(self, mock_datamanager, mock_visualizer):
        """Test error handling when no data is found."""
        # Configure mock to return None (no data)
        mock_datamanager.return_value.load_data.return_value = None
        
        # Run the plot command with a valid symbol that passes validation
        # but for which we'll return no data
        result = runner.invoke(cli_app, ["plot", "MSFT"])
        
        # Verify command execution indicates error but is properly handled
        assert "No data found" in result.stdout
    
    def test_plot_invalid_chart_type(self, mock_datamanager):
        """Test error handling with invalid chart type."""
        # Run the plot command with invalid chart type
        result = runner.invoke(cli_app, [
            "plot", 
            "MSFT", 
            "--chart-type", "invalid_type"
        ])
        
        # Verify command execution failed with appropriate error
        assert result.exit_code == 1
        assert "Validation error" in result.stdout
    
    def test_plot_invalid_theme(self, mock_datamanager):
        """Test error handling with invalid theme."""
        # Run the plot command with invalid theme
        result = runner.invoke(cli_app, [
            "plot", 
            "MSFT", 
            "--theme", "invalid_theme"
        ])
        
        # Verify command execution failed with appropriate error
        assert result.exit_code == 1
        assert "Validation error" in result.stdout
    
    def test_plot_indicators_invalid_config_file(self, mock_datamanager):
        """Test error handling with invalid config file."""
        # Run the plot-indicators command with nonexistent config file
        result = runner.invoke(cli_app, [
            "plot-indicators", 
            "MSFT", 
            "--config", "nonexistent_file.yaml"
        ])
        
        # Verify command execution failed with appropriate error
        assert result.exit_code == 1
        assert "Configuration error" in result.stdout