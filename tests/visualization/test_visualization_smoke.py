"""
Smoke tests for the visualization module.

This module contains smoke tests that verify basic functionality
of the visualization components working together.
"""

import os
import pandas as pd
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from ktrdr.visualization import Visualizer
from ktrdr.visualization.data_adapter import DataAdapter
from ktrdr.visualization.config_builder import ConfigBuilder
from ktrdr.visualization.template_manager import TemplateManager
from ktrdr.visualization.renderer import Renderer


@pytest.fixture
def sample_ohlc_data():
    """Create a sample OHLC DataFrame for testing."""
    dates = [datetime.now() - timedelta(days=i) for i in range(30)]

    return pd.DataFrame(
        {
            "date": dates,
            "open": [100.0 + i * 0.5 for i in range(30)],
            "high": [105.0 + i * 0.5 for i in range(30)],
            "low": [95.0 + i * 0.5 for i in range(30)],
            "close": [102.0 + i * 0.5 for i in range(30)],
            "volume": [1000 + i * 50 for i in range(30)],
        }
    )


@pytest.fixture
def sample_indicator_data(sample_ohlc_data):
    """Create sample indicator data for testing."""
    # Add a simple SMA indicator
    sma_10 = sample_ohlc_data["close"].rolling(10).mean()
    sma_20 = sample_ohlc_data["close"].rolling(20).mean()

    df = sample_ohlc_data.copy()
    df["sma_10"] = sma_10
    df["sma_20"] = sma_20
    df["rsi"] = (
        50 + 25 * (df["close"].pct_change(1).fillna(0)).cumsum()
    )  # Simplified RSI for testing
    df["rsi"] = df["rsi"].clip(0, 100)  # Clip to RSI range

    return df


class TestVisualizationSmoke:
    """
    Smoke tests for the visualization module.

    These tests verify that the basic functionality of the visualization
    components work together correctly. They don't test all the edge cases
    or details, which are covered in the specific component tests.
    """

    def test_create_basic_chart(self, sample_ohlc_data, tmp_path):
        """Test creating a basic candlestick chart."""
        # Create visualizer
        visualizer = Visualizer(theme="dark")

        # Create a chart
        chart = visualizer.create_chart(
            data=sample_ohlc_data,
            title="Test Candlestick Chart",
            chart_type="candlestick",
        )

        # Save the chart to a temporary file
        output_file = tmp_path / "basic_chart.html"
        saved_path = visualizer.save(chart, output_file)

        # Verify the file exists and has content
        assert saved_path.exists()
        with open(saved_path, "r") as f:
            content = f.read()
            assert "Test Candlestick Chart" in content
            assert "LightweightCharts" in content

    def test_create_chart_with_indicator_overlay(self, sample_indicator_data, tmp_path):
        """Test creating a chart with an indicator overlay."""
        # Create visualizer
        visualizer = Visualizer(theme="dark")

        # Create a chart
        chart = visualizer.create_chart(
            data=sample_indicator_data,
            title="Chart with Indicator Overlay",
            chart_type="candlestick",
        )

        # Add an SMA overlay
        chart = visualizer.add_indicator_overlay(
            chart=chart,
            data=sample_indicator_data,
            column="sma_10",
            color="#2962FF",
            title="SMA 10",
        )

        # Add another indicator overlay
        chart = visualizer.add_indicator_overlay(
            chart=chart,
            data=sample_indicator_data,
            column="sma_20",
            color="#FF2962",
            title="SMA 20",
        )

        # Save the chart to a temporary file
        output_file = tmp_path / "chart_with_overlay.html"
        saved_path = visualizer.save(chart, output_file)

        # Verify the file exists and has content
        assert saved_path.exists()
        with open(saved_path, "r") as f:
            content = f.read()
            assert "Chart with Indicator Overlay" in content
            assert "SMA 10" in content
            assert "SMA 20" in content

    def test_create_chart_with_indicator_panel(self, sample_indicator_data, tmp_path):
        """Test creating a chart with a separate indicator panel."""
        # Create visualizer
        visualizer = Visualizer(theme="light")  # Test light theme

        # Create a chart
        chart = visualizer.create_chart(
            data=sample_indicator_data,
            title="Chart with Indicator Panel",
            chart_type="candlestick",
        )

        # Add an RSI panel
        chart = visualizer.add_indicator_panel(
            chart=chart,
            data=sample_indicator_data,
            column="rsi",
            panel_type="line",
            height=150,
            color="#9C27B0",
            title="RSI",
        )

        # Save the chart to a temporary file
        output_file = tmp_path / "chart_with_panel.html"
        saved_path = visualizer.save(chart, output_file)

        # Verify the file exists and has content
        assert saved_path.exists()
        with open(saved_path, "r") as f:
            content = f.read()
            assert "Chart with Indicator Panel" in content
            assert "RSI" in content
            assert "light" in content.lower()  # Check for light theme elements

    def test_create_chart_with_range_slider(self, sample_indicator_data, tmp_path):
        """Test creating a chart with a range slider."""
        # Create visualizer
        visualizer = Visualizer()

        # Create a chart
        chart = visualizer.create_chart(
            data=sample_indicator_data,
            title="Chart with Range Slider",
            chart_type="candlestick",
        )

        # Configure range slider
        chart = visualizer.configure_range_slider(chart, height=60, show=True)

        # Save the chart to a temporary file
        output_file = tmp_path / "chart_with_range_slider.html"
        saved_path = visualizer.save(chart, output_file)

        # Verify the file exists and has content
        assert saved_path.exists()
        with open(saved_path, "r") as f:
            content = f.read()
            assert "Chart with Range Slider" in content
            assert "range_slider" in content

    def test_show_method_returns_html(self, sample_ohlc_data):
        """Test that the show method returns HTML content."""
        # Create visualizer
        visualizer = Visualizer()

        # Create a chart
        chart = visualizer.create_chart(data=sample_ohlc_data, title="Test Show Method")

        # Get HTML content using the show method
        html_content = visualizer.show(chart)

        # Verify the content is HTML and contains expected elements
        assert isinstance(html_content, str)
        assert "Test Show Method" in html_content
        assert "<!DOCTYPE html>" in html_content
        assert "LightweightCharts" in html_content
