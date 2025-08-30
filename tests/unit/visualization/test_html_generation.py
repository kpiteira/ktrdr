"""
Tests for the HTML/JS generation in the visualization package.

This module provides comprehensive tests for the HTML and JavaScript
generation functionality, ensuring that chart configurations and data
are correctly rendered into valid HTML output.
"""

import pytest

from ktrdr.errors import ConfigurationError
from ktrdr.visualization.config_builder import ConfigBuilder
from ktrdr.visualization.data_adapter import DataAdapter
from ktrdr.visualization.renderer import Renderer
from ktrdr.visualization.template_manager import TemplateManager

# Import test fixtures


class TestHtmlGeneration:
    """
    Tests for HTML/JS generation functionality.
    """

    @pytest.fixture
    def renderer(self):
        """Create a Renderer instance for testing."""
        return Renderer()

    @pytest.fixture
    def sample_chart_configs(self):
        """Create sample chart configurations for testing."""
        # Create a basic price chart configuration
        price_chart_options = ConfigBuilder.create_price_chart_options(
            theme="dark", height=400
        )

        price_series_options = ConfigBuilder.create_series_options(
            series_type="candlestick", upColor="#26A69A", downColor="#EF5350"
        )

        # Create chart configs
        return [
            {
                "id": "price_chart",
                "type": "price",
                "title": "Test Price Chart",
                "height": 400,
                "options": price_chart_options,
                "series_options": price_series_options,
            }
        ]

    @pytest.fixture
    def sample_indicator_chart_configs(self, sample_chart_configs):
        """Create sample chart configs with indicators for testing."""
        # Start with basic price chart
        configs = sample_chart_configs.copy()

        # Add RSI panel configuration
        indicator_chart_options = ConfigBuilder.create_indicator_chart_options(
            theme="dark", height=150
        )

        indicator_series_options = ConfigBuilder.create_series_options(
            series_type="line", color="#9C27B0", lineWidth=1.5
        )

        # Add indicator panel configuration
        configs.append(
            {
                "id": "rsi_panel",
                "type": "indicator",
                "title": "RSI (14)",
                "height": 150,
                "options": indicator_chart_options,
                "series_options": indicator_series_options,
                "sync": {"target": "price_chart"},
            }
        )

        return configs

    @pytest.fixture
    def sample_chart_data(self, sample_price_data, sample_indicators):
        """Create sample chart data for testing."""
        # Transform price data
        price_data = DataAdapter.transform_ohlc(sample_price_data)

        # Transform RSI data
        rsi_data = DataAdapter.transform_line(
            sample_indicators, time_column="date", value_column="rsi"
        )

        # Create chart data object
        return {"price_chart": price_data, "rsi_panel": rsi_data}

    def test_render_chart_basic(
        self, renderer, sample_chart_configs, sample_chart_data
    ):
        """Test basic chart rendering."""
        # Render a chart
        html = renderer.render_chart(
            title="Test Chart",
            chart_configs=sample_chart_configs,
            chart_data=sample_chart_data,
        )

        # Verify HTML structure
        assert "<!DOCTYPE html>" in html
        assert "<title>Test Chart</title>" in html
        assert "<h1>Test Chart</h1>" in html

        # Verify scripts are included
        assert "LightweightCharts.createChart" in html
        assert "price_chart_series.setData" in html

        # Verify chart elements
        assert 'id="price_chart"' in html
        assert "<h2>Test Price Chart</h2>" in html

    def test_render_chart_with_indicators(
        self, renderer, sample_indicator_chart_configs, sample_chart_data
    ):
        """Test rendering a chart with indicator panels."""
        # Render a chart with indicators
        html = renderer.render_chart(
            title="Chart with Indicators",
            chart_configs=sample_indicator_chart_configs,
            chart_data=sample_chart_data,
        )

        # Verify indicators are included
        assert 'id="rsi_panel"' in html
        assert "<h2>RSI (14)</h2>" in html
        assert "rsi_panel_series.setData" in html

        # Check for synchronization script
        assert "timeScale().subscribeVisibleLogicalRangeChange" in html
        assert "price_chart.timeScale().setVisibleLogicalRange" in html

    def test_render_chart_theme_switch(
        self, renderer, sample_chart_configs, sample_chart_data
    ):
        """Test theme switching in rendered HTML."""
        # Test dark theme (default)
        dark_html = renderer.render_chart(
            title="Dark Theme",
            chart_configs=sample_chart_configs,
            chart_data=sample_chart_data,
            theme="dark",
        )

        # Verify dark theme elements
        assert "background-color: #151924" in dark_html
        assert "color: #d1d4dc" in dark_html
        assert 'id="darkTheme" disabled' in dark_html
        assert 'id="lightTheme" ' in dark_html

        # Test light theme
        light_html = renderer.render_chart(
            title="Light Theme",
            chart_configs=sample_chart_configs,
            chart_data=sample_chart_data,
            theme="light",
        )

        # Verify light theme elements
        assert "background-color: #ffffff" in light_html
        assert "color: #333333" in light_html
        assert 'id="darkTheme" ' in light_html
        assert 'id="lightTheme" disabled' in light_html

    def test_render_chart_with_range_slider(
        self, renderer, sample_chart_configs, sample_chart_data
    ):
        """Test rendering a chart with range slider."""
        # Add range slider configuration
        configs = sample_chart_configs.copy()
        configs.append(
            {
                "id": "range_slider",
                "type": "range",
                "title": "Range Selector",
                "height": 60,
                "is_range_slider": True,
                "sync": {"target": "price_chart", "mode": "range"},
            }
        )

        # Render chart with range slider
        html = renderer.render_chart(
            title="Chart with Range Slider",
            chart_configs=configs,
            chart_data=sample_chart_data,
            has_range_slider=True,
        )

        # Verify range slider elements
        assert 'id="range_slider"' in html
        assert "<h2>Range Selector</h2>" in html
        assert "Special handling for range slider" in html

    def test_html_structure_validity(
        self, renderer, sample_chart_configs, sample_chart_data
    ):
        """Test that the HTML structure has required elements."""
        html = renderer.render_chart(
            title="Structure Test",
            chart_configs=sample_chart_configs,
            chart_data=sample_chart_data,
        )

        # Check for key HTML structure elements
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "<script>" in html
        assert "</html>" in html

        # Check for required JavaScript elements
        assert "document.addEventListener('DOMContentLoaded'" in html
        assert "window.addEventListener('resize'" in html

    def test_chart_script_generation(self):
        """Test the chart script generation function."""
        # Test chart script generation for different chart types
        price_script = TemplateManager._generate_chart_script(
            chart_id="test_chart",
            chart_type="price",
            chart_config={"options": {}, "series_options": {}},
            data=[
                {"time": 1625097600, "open": 100, "high": 110, "low": 90, "close": 105}
            ],
        )

        # Check for price chart specific elements
        assert "addCandlestickSeries" in price_script
        assert "test_chart_series.setData(" in price_script

        # Test line chart script
        line_script = TemplateManager._generate_chart_script(
            chart_id="line_chart",
            chart_type="indicator",
            chart_config={"options": {}, "series_options": {"type": "line"}},
            data=[{"time": 1625097600, "value": 100}],
        )

        # Check for line chart specific elements
        assert "addLineSeries" in line_script
        assert "line_chart_series.setData(" in line_script

        # Test histogram chart script
        histogram_script = TemplateManager._generate_chart_script(
            chart_id="histogram_chart",
            chart_type="histogram",
            chart_config={"options": {}, "series_options": {"type": "histogram"}},
            data=[{"time": 1625097600, "value": 100, "color": "#26A69A"}],
        )

        # Check for histogram chart specific elements
        assert "addHistogramSeries" in histogram_script
        assert "histogram_chart_series.setData(" in histogram_script

    def test_invalid_theme_handling(
        self, renderer, sample_chart_configs, sample_chart_data
    ):
        """Test handling of invalid theme value."""
        # Should raise ConfigurationError for invalid theme
        with pytest.raises(ConfigurationError) as exc_info:
            renderer.render_chart(
                title="Invalid Theme Test",
                chart_configs=sample_chart_configs,
                chart_data=sample_chart_data,
                theme="invalid_theme",
            )

        # Check error message
        assert "Invalid theme" in str(exc_info.value)

    def test_empty_configs_handling(self, renderer, sample_chart_data):
        """Test handling of empty chart configurations."""
        # Render with empty configs
        html = renderer.render_chart(
            title="Empty Config Test", chart_configs=[], chart_data=sample_chart_data
        )

        # Should still render valid HTML without chart elements
        assert "<!DOCTYPE html>" in html
        assert "<title>Empty Config Test</title>" in html
        assert "<h1>Empty Config Test</h1>" in html

        # No chart creation scripts should be present
        assert "LightweightCharts.createChart" not in html

    def test_save_chart_functionality(
        self, renderer, sample_chart_configs, sample_chart_data, tmp_path
    ):
        """Test saving chart HTML to file."""
        # Generate HTML
        html = renderer.render_chart(
            title="Save Test",
            chart_configs=sample_chart_configs,
            chart_data=sample_chart_data,
        )

        # Save to temp file
        output_file = tmp_path / "test_chart.html"
        saved_path = renderer.save_chart(html_content=html, output_path=output_file)

        # Verify file exists and content matches
        assert saved_path.exists()
        with open(saved_path) as f:
            content = f.read()
            assert content == html

    def test_update_theme(self, renderer):
        """Test updating theme in existing HTML content."""
        # Create sample HTML with dark theme
        html_content = """
        <html>
        <body style="background-color: #151924; color: #d1d4dc;">
        <script>
        document.getElementById('darkTheme').disabled = true;
        document.getElementById('lightTheme').disabled = false;
        </script>
        </body>
        </html>
        """

        # Update to light theme
        light_html = renderer.update_theme(html_content=html_content, theme="light")

        # Verify theme was updated
        assert "darkTheme').disabled = false" in light_html
        assert "lightTheme').disabled = true" in light_html

        # Update back to dark theme
        dark_html = renderer.update_theme(html_content=light_html, theme="dark")

        # Verify theme was updated back to dark
        assert "darkTheme').disabled = true" in dark_html
        assert "lightTheme').disabled = false" in dark_html

    def test_chart_generation_cross_browser_compatibility(
        self, renderer, sample_chart_configs, sample_chart_data
    ):
        """Test that generated HTML has cross-browser compatibility elements."""
        html = renderer.render_chart(
            title="Cross-Browser Test",
            chart_configs=sample_chart_configs,
            chart_data=sample_chart_data,
        )

        # Check for DOCTYPE to ensure browser compatibility
        assert "<!DOCTYPE html>" in html

        # Check for meta viewport tag for responsive design
        assert (
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            in html
        )

        # Check for charset declaration
        assert '<meta charset="UTF-8">' in html
