"""
Tests for the Visualizer class.
"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile
import os
from unittest.mock import patch, MagicMock

from ktrdr.visualization import Visualizer
from ktrdr.errors import ConfigurationError


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    dates = pd.date_range(start="2023-01-01", periods=100)
    data = {
        'date': dates,
        'open': range(100, 200),
        'high': range(110, 210),
        'low': range(90, 190),
        'close': range(105, 205),
        'volume': range(1000, 1100),
        'indicator1': range(50, 150),
        'indicator2': range(20, 120)
    }
    return pd.DataFrame(data)


class TestVisualizer:
    """Tests for the Visualizer class."""
    
    def test_init(self):
        """Test Visualizer initialization."""
        # Test with default theme
        viz = Visualizer()
        assert viz.theme == "dark"
        
        # Test with light theme
        viz = Visualizer(theme="light")
        assert viz.theme == "light"
        
        # Test with invalid theme
        with pytest.raises(ConfigurationError):
            Visualizer(theme="invalid")
    
    def test_create_chart(self, sample_df):
        """Test creating a chart."""
        viz = Visualizer()
        
        # Test with default parameters
        chart = viz.create_chart(sample_df)
        assert isinstance(chart, dict)
        assert "configs" in chart
        assert "data" in chart
        assert len(chart["configs"]) == 1
        assert chart["configs"][0]["type"] == "price"
        assert chart["configs"][0]["id"] == "main_chart"
        
        # Test with custom title and chart type
        chart = viz.create_chart(sample_df, title="Test Chart", chart_type="line")
        assert chart["title"] == "Test Chart"
        assert chart["configs"][0]["type"] == "indicator"
        
        # Test with invalid chart type
        with pytest.raises(ConfigurationError):
            viz.create_chart(sample_df, chart_type="invalid")
    
    def test_add_indicator_overlay(self, sample_df):
        """Test adding an indicator overlay to a chart."""
        viz = Visualizer()
        chart = viz.create_chart(sample_df)
        
        # Add an indicator overlay
        chart = viz.add_indicator_overlay(chart, sample_df, "indicator1")
        
        # Verify the overlay was added
        assert "indicator1_overlay" in chart["data"]
        assert len(chart["overlay_series"]) == 1
        assert chart["overlay_series"][0]["column"] == "indicator1"
        
        # Test with a non-existent column
        with pytest.raises(ConfigurationError):
            viz.add_indicator_overlay(chart, sample_df, "non_existent_column")
        
        # Test with an invalid chart object
        with pytest.raises(ConfigurationError):
            viz.add_indicator_overlay({}, sample_df, "indicator1")
    
    def test_add_indicator_panel(self, sample_df):
        """Test adding an indicator panel to a chart."""
        viz = Visualizer()
        chart = viz.create_chart(sample_df)
        
        # Add an indicator panel
        chart = viz.add_indicator_panel(chart, sample_df, "indicator1")
        
        # Verify the panel was added
        assert len(chart["configs"]) == 2
        assert "indicator1_panel" in chart["data"]
        assert len(chart["panels"]) == 1
        assert chart["panels"][0]["column"] == "indicator1"
        
        # Test with a different panel type
        chart = viz.add_indicator_panel(chart, sample_df, "indicator2", panel_type="histogram")
        assert len(chart["configs"]) == 3
        assert chart["panels"][1]["type"] == "histogram"
        
        # Test with a non-existent column
        with pytest.raises(ConfigurationError):
            viz.add_indicator_panel(chart, sample_df, "non_existent_column")
        
        # Test with an invalid panel type
        with pytest.raises(ConfigurationError):
            viz.add_indicator_panel(chart, sample_df, "indicator1", panel_type="invalid")
    
    def test_configure_range_slider(self, sample_df):
        """Test configuring a range slider for a chart."""
        viz = Visualizer()
        chart = viz.create_chart(sample_df)
        
        # Add a range slider
        chart = viz.configure_range_slider(chart)
        
        # Verify the range slider was added
        assert len(chart["configs"]) == 2
        assert chart["configs"][1]["is_range_slider"] == True
        assert "range_slider" in chart["data"]
        
        # Update the range slider height
        chart = viz.configure_range_slider(chart, height=80)
        assert chart["configs"][1]["height"] == 80
        
        # Remove the range slider
        chart = viz.configure_range_slider(chart, show=False)
        assert len(chart["configs"]) == 1
        assert all(not c.get("is_range_slider", False) for c in chart["configs"])
    
    @patch('ktrdr.visualization.renderer.Renderer.render_chart')
    @patch('ktrdr.visualization.renderer.Renderer.save_chart')
    def test_save(self, mock_save_chart, mock_render_chart, sample_df):
        """Test saving a chart to a file."""
        # Setup mocks
        mock_render_chart.return_value = "<html>Mock Chart</html>"
        mock_save_chart.return_value = Path("/mock/path.html")
        
        viz = Visualizer()
        chart = viz.create_chart(sample_df)
        
        # Save the chart
        output_path = viz.save(chart, "test.html")
        
        # Verify the methods were called correctly
        mock_render_chart.assert_called_once()
        mock_save_chart.assert_called_once_with("<html>Mock Chart</html>", "test.html", False)
        assert output_path == Path("/mock/path.html")
        
        # Test with an invalid chart object
        with pytest.raises(ConfigurationError):
            viz.save({}, "test.html")
    
    @patch('ktrdr.visualization.renderer.Renderer.render_chart')
    def test_show(self, mock_render_chart, sample_df):
        """Test generating HTML content for displaying a chart."""
        # Setup mock
        mock_render_chart.return_value = "<html>Mock Chart</html>"
        
        viz = Visualizer()
        chart = viz.create_chart(sample_df)
        
        # Show the chart
        html_content = viz.show(chart)
        
        # Verify the method was called correctly
        mock_render_chart.assert_called_once()
        assert html_content == "<html>Mock Chart</html>"
        
        # Test with an invalid chart object
        with pytest.raises(ConfigurationError):
            viz.show({})


if __name__ == "__main__":
    pytest.main(["-v", __file__])