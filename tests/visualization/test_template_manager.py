"""
Tests for the TemplateManager class in the visualization module.
"""

from ktrdr.visualization.template_manager import TemplateManager


class TestTemplateManager:
    """
    Test suite for the TemplateManager class.
    """

    def test_get_base_template(self):
        """Test getting the base template."""
        template = TemplateManager.get_base_template()

        # Check that it's a string
        assert isinstance(template, str)

        # Check that it contains key HTML elements
        assert "<!DOCTYPE html>" in template
        assert "<html" in template
        assert "</html>" in template
        assert "<head>" in template
        assert "</head>" in template
        assert "<body>" in template
        assert "</body>" in template

        # Check for lightweight-charts script
        assert "lightweight-charts" in template

    def test_render_chart_html_default(self):
        """Test rendering chart HTML with default parameters."""
        html = TemplateManager.render_chart_html()

        # Check that it's a string
        assert isinstance(html, str)

        # Check for dark theme elements (default)
        assert "background-color: #151924" in html
        assert "color: #d1d4dc" in html

        # Check that title is set properly
        assert "<title>KTRDR Chart</title>" in html
        assert "<h1>KTRDR Chart</h1>" in html

    def test_render_chart_html_light_theme(self):
        """Test rendering chart HTML with light theme."""
        html = TemplateManager.render_chart_html(theme="light")

        # Check for light theme elements
        assert "background-color: #ffffff" in html
        assert "color: #333333" in html

    def test_render_chart_html_custom_title(self):
        """Test rendering chart HTML with custom title."""
        title = "Custom Test Chart"
        html = TemplateManager.render_chart_html(title=title)

        # Check that title is set properly
        assert f"<title>{title}</title>" in html
        assert f"<h1>{title}</h1>" in html

    def test_render_chart_html_with_configs(self):
        """Test rendering chart HTML with chart configurations."""
        # Create some test chart configs
        chart_configs = [
            {
                "id": "price_chart",
                "type": "price",
                "title": "Price Chart",
                "height": 400,
                "options": {"width": 800},
            },
            {
                "id": "volume_chart",
                "type": "histogram",
                "title": "Volume",
                "height": 150,
                "options": {"width": 800},
            },
        ]

        html = TemplateManager.render_chart_html(chart_configs=chart_configs)

        # Check that chart containers are created
        assert 'id="price_chart"' in html
        assert 'id="volume_chart"' in html

        # Check that titles are included
        assert "<h2>Price Chart</h2>" in html
        assert "<h2>Volume</h2>" in html

        # Check that chart creation scripts are included
        assert "const price_chart = LightweightCharts.createChart" in html
        assert "const volume_chart = LightweightCharts.createChart" in html

    def test_render_chart_html_with_data(self):
        """Test rendering chart HTML with chart data."""
        # Create some test chart configs and data
        chart_configs = [{"id": "test_chart", "type": "price", "title": "Test Chart"}]

        chart_data = {
            "test_chart": [
                {"time": 1625097600, "open": 100, "high": 110, "low": 90, "close": 105}
            ]
        }

        html = TemplateManager.render_chart_html(
            chart_configs=chart_configs, chart_data=chart_data
        )

        # Check that data is included in the script
        assert "test_chart_series.setData(" in html

        # Convert the data to a string representation that should be in the HTML
        # The exact format might vary, but we can check for key elements
        assert "1625097600" in html  # Timestamp in the data
        assert "100" in html  # Open price in the data

    def test_render_chart_html_with_range_slider(self):
        """Test rendering chart HTML with range slider."""
        # Create chart configs with a range slider
        chart_configs = [
            {"id": "main_chart", "type": "price", "title": "Main Chart"},
            {
                "id": "range_slider",
                "type": "range",
                "title": "Range Selector",
                "is_range_slider": True,
                "sync": {"target": "main_chart", "mode": "range"},
            },
        ]

        html = TemplateManager.render_chart_html(
            chart_configs=chart_configs, has_range_slider=True
        )

        # Check that range slider special behavior is triggered
        assert "Special handling for range slider" in html

        # Check for range slider chart container
        assert "<h2>Range Selector</h2>" in html

    def test_generate_chart_script_price(self):
        """Test generating script for price chart."""
        chart_id = "price_test"
        chart_type = "price"
        chart_config = {
            "options": {"width": 800, "height": 400},
            "series_options": {"upColor": "#00FF00"},
        }
        data = [{"time": 1625097600, "open": 100, "high": 110, "low": 90, "close": 105}]

        script = TemplateManager._generate_chart_script(
            chart_id=chart_id,
            chart_type=chart_type,
            chart_config=chart_config,
            data=data,
        )

        # Check script content
        assert f"const {chart_id} = LightweightCharts.createChart" in script
        assert f"const {chart_id}_series = {chart_id}.addCandlestickSeries" in script
        assert f"{chart_id}_series.setData" in script
        assert f"{chart_id}.timeScale().fitContent()" in script

    def test_generate_chart_script_indicator(self):
        """Test generating script for indicator chart."""
        chart_id = "rsi_test"
        chart_type = "indicator"
        chart_config = {
            "options": {"height": 150},
            "series_options": {"color": "#FF0000"},
        }
        data = [{"time": 1625097600, "value": 70}]

        script = TemplateManager._generate_chart_script(
            chart_id=chart_id,
            chart_type=chart_type,
            chart_config=chart_config,
            data=data,
        )

        # Check script content
        assert f"const {chart_id} = LightweightCharts.createChart" in script
        assert f"const {chart_id}_series = {chart_id}.addLineSeries" in script
        assert f"{chart_id}_series.setData" in script

    def test_generate_chart_script_with_sync(self):
        """Test generating chart script with sync configuration."""
        chart_id = "sync_test"
        chart_type = "indicator"
        chart_config = {
            "options": {"height": 150},
            "series_options": {"color": "#FF0000"},
            "sync": {"target": "main_chart"},
        }
        data = [{"time": 1625097600, "value": 70}]

        script = TemplateManager._generate_chart_script(
            chart_id=chart_id,
            chart_type=chart_type,
            chart_config=chart_config,
            data=data,
        )

        # The current implementation doesn't include sync code directly in the
        # _generate_chart_script method, but in the render_chart_html method.
        # Check that the basic chart creation is done correctly
        assert f"const {chart_id} = LightweightCharts.createChart" in script
        assert f"const {chart_id}_series = {chart_id}.addLineSeries" in script
        assert f"{chart_id}_series.setData" in script
