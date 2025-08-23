"""
Integration tests for the visualization components.

This module contains tests that verify the integrated functionality
of the visualization components working together.
"""

import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.visualization import (
    Visualizer,
)

# Import test fixtures
from tests.visualization.test_fixtures import (
    histogram_data,
    multiple_series_data,
    sample_indicators,
    sample_price_data,
)


class TestVisualizationIntegration:
    """
    Integration tests for the visualization components.

    These tests verify that all components of the visualization system
    work correctly together.
    """

    @pytest.fixture
    def sample_chart(self, sample_price_data):
        """Create a sample chart for testing."""
        visualizer = Visualizer(theme="dark")
        return visualizer.create_chart(
            data=sample_price_data,
            title="Test Integration Chart",
            chart_type="candlestick",
        )

    @pytest.fixture
    def sample_multi_panel_chart(self, sample_price_data, sample_indicators):
        """Create a sample multi-panel chart for testing."""
        visualizer = Visualizer(theme="dark")

        # Create base chart
        chart = visualizer.create_chart(
            data=sample_price_data, title="Multi-Panel Chart", chart_type="candlestick"
        )

        # Add SMA overlays
        chart = visualizer.add_indicator_overlay(
            chart=chart,
            data=sample_indicators,
            column="sma_10",
            color="#2962FF",
            title="SMA 10",
        )

        chart = visualizer.add_indicator_overlay(
            chart=chart,
            data=sample_indicators,
            column="sma_20",
            color="#FF6D00",
            title="SMA 20",
        )

        # Add RSI panel
        chart = visualizer.add_indicator_panel(
            chart=chart,
            data=sample_indicators,
            column="rsi",
            panel_type="line",
            height=150,
            color="#9C27B0",
            title="RSI",
        )

        # Add volume panel
        chart = visualizer.add_indicator_panel(
            chart=chart,
            data=sample_price_data,
            column="volume",
            panel_type="histogram",
            height=100,
            color="#26A69A",
            title="Volume",
        )

        # Configure range slider
        chart = visualizer.configure_range_slider(chart, height=60, show=True)

        return chart

    def test_end_to_end_chart_creation(self, sample_price_data, tmp_path):
        """Test end-to-end chart creation, from data to HTML file."""
        # Create a visualizer
        visualizer = Visualizer()

        # Create a chart
        chart = visualizer.create_chart(
            data=sample_price_data, title="End-to-End Test", chart_type="candlestick"
        )

        # Save chart to file
        output_path = tmp_path / "end_to_end_test.html"
        saved_path = visualizer.save(chart, output_path)

        # Verify file was created with content
        assert saved_path.exists()
        with open(saved_path) as f:
            html_content = f.read()
            assert "End-to-End Test" in html_content
            assert "LightweightCharts" in html_content
            assert "candlestick" in html_content.lower()

    def test_theme_switching(self, sample_chart, tmp_path):
        """Test theme switching functionality end-to-end."""
        visualizer = Visualizer(theme="dark")

        # Save with dark theme
        dark_output_path = tmp_path / "dark_theme_test.html"
        visualizer.save(sample_chart, dark_output_path)

        # Read content
        with open(dark_output_path) as f:
            dark_content = f.read()
            assert "background-color: #151924" in dark_content

        # Switch to light theme and save
        visualizer.theme = "light"
        light_output_path = tmp_path / "light_theme_test.html"
        visualizer.save(sample_chart, light_output_path)

        # Read content
        with open(light_output_path) as f:
            light_content = f.read()
            assert "background-color: #ffffff" in light_content

    def test_data_transformation_with_visualizer(self, sample_indicators, tmp_path):
        """Test that data transformation works correctly with visualizer."""
        visualizer = Visualizer()

        # Create a line chart with missing data (NaN values in indicators)
        chart = visualizer.create_chart(
            data=sample_indicators,
            title="Indicator with NaNs",
            chart_type="line",
            height=300,
        )

        # Save chart
        output_path = tmp_path / "indicator_nan_test.html"
        visualizer.save(chart, output_path)

        # Chart should be created despite NaN values
        assert output_path.exists()

    def test_multi_panel_chart_generation(self, sample_multi_panel_chart, tmp_path):
        """Test that multi-panel charts are correctly generated."""
        visualizer = Visualizer()

        # Save multi-panel chart
        output_path = tmp_path / "multi_panel_test.html"
        visualizer.save(sample_multi_panel_chart, output_path)

        # Verify file exists
        assert output_path.exists()

        # Check content for panel elements
        with open(output_path) as f:
            content = f.read()
            assert "Multi-Panel Chart" in content
            assert "SMA 10" in content
            assert "SMA 20" in content
            assert "RSI" in content
            assert "Volume" in content
            assert "range_slider" in content

            # Check for synchronization scripts
            assert "subscribeVisibleLogicalRangeChange" in content
            assert "setVisibleLogicalRange" in content

    def test_chart_with_multiple_overlays(
        self, sample_price_data, sample_indicators, tmp_path
    ):
        """Test chart with multiple indicator overlays."""
        visualizer = Visualizer()

        # Create base chart
        chart = visualizer.create_chart(
            data=sample_price_data,
            title="Multiple Overlays Test",
            chart_type="candlestick",
        )

        # Add multiple overlays
        for i, col in enumerate(
            ["bollinger_upper", "bollinger_middle", "bollinger_lower"]
        ):
            chart = visualizer.add_indicator_overlay(
                chart=chart,
                data=sample_indicators,
                column=col,
                color=f"#FF{i*3:02d}FF",
                title=f"Bollinger {col.split('_')[1].capitalize()}",
            )

        # Save chart
        output_path = tmp_path / "multiple_overlays_test.html"
        visualizer.save(chart, output_path)

        # Check content for overlay elements
        with open(output_path) as f:
            content = f.read()
            assert "Multiple Overlays Test" in content
            assert "Bollinger Upper" in content
            assert "Bollinger Middle" in content
            assert "Bollinger Lower" in content

    def test_error_handling_invalid_data(self, tmp_path):
        """Test error handling for invalid data."""
        visualizer = Visualizer()

        # Create invalid data (missing required columns)
        invalid_data = pd.DataFrame(
            {
                "date": pd.date_range(start="2020-01-01", periods=10),
                "value": [i * 10 for i in range(10)],
            }
        )

        # Attempt to create candlestick chart with invalid data
        with pytest.raises(DataError):
            chart = visualizer.create_chart(
                data=invalid_data, title="Invalid Data Test", chart_type="candlestick"
            )

    def test_existing_file_handling(self, sample_chart, tmp_path):
        """Test handling of existing files when saving."""
        visualizer = Visualizer()

        # Create file path
        output_path = tmp_path / "existing_file_test.html"

        # Save chart first time
        visualizer.save(sample_chart, output_path)

        # Attempt to save again without overwrite flag (should raise error)
        with pytest.raises(DataError):
            visualizer.save(sample_chart, output_path, overwrite=False)

        # Save again with overwrite flag
        visualizer.save(sample_chart, output_path, overwrite=True)

        # File should still exist
        assert output_path.exists()

    def test_html_content_validity(self, sample_multi_panel_chart):
        """Test that HTML content is valid and contains expected elements."""
        visualizer = Visualizer()

        # Get HTML content
        html_content = visualizer.show(sample_multi_panel_chart)

        # Check for key HTML elements
        assert "<!DOCTYPE html>" in html_content
        assert "<html" in html_content
        assert "<head>" in html_content
        assert "<body>" in html_content
        assert "<script>" in html_content
        assert "</html>" in html_content

        # Check for lightweight-charts script inclusion
        assert "lightweight-charts" in html_content

        # Check for chart container elements
        assert 'class="chart-container"' in html_content
        assert 'class="chart-inner"' in html_content
        assert 'class="chart-wrapper"' in html_content

        # Check for responsive design elements
        assert '<meta name="viewport"' in html_content
        assert "@media (max-width: 768px)" in html_content

        # Check for theme switching elements
        assert 'id="darkTheme"' in html_content
        assert 'id="lightTheme"' in html_content

        # Check for key JavaScript functionality
        assert "DOMContentLoaded" in html_content
        assert "window.addEventListener('resize'" in html_content
        assert "zoomFit" in html_content
