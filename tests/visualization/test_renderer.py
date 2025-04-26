"""
Tests for the Renderer class in the visualization module.
"""

import pytest
from pathlib import Path
import os
import tempfile

from ktrdr.visualization.renderer import Renderer
from ktrdr.errors import ConfigurationError, DataError


class TestRenderer:
    """
    Test suite for the Renderer class.
    """
    
    @pytest.fixture
    def renderer(self):
        """Create a Renderer instance for testing."""
        return Renderer()
    
    @pytest.fixture
    def sample_chart_configs(self):
        """Create sample chart configurations for testing."""
        return [
            {
                "id": "price_chart",
                "type": "price",
                "title": "Price Chart",
                "options": {"height": 400},
                "series_options": {"upColor": "#26a69a", "downColor": "#ef5350"}
            }
        ]
    
    @pytest.fixture
    def sample_chart_data(self):
        """Create sample chart data for testing."""
        return {
            "price_chart": [
                {"time": 1625097600, "open": 100, "high": 110, "low": 90, "close": 105}
            ]
        }
    
    def test_init(self, renderer):
        """Test initialization of Renderer."""
        # Just verify that it initializes without errors
        assert isinstance(renderer, Renderer)
    
    def test_render_chart_basic(self, renderer, sample_chart_configs, sample_chart_data):
        """Test basic chart rendering."""
        title = "Test Chart"
        html = renderer.render_chart(
            title=title,
            chart_configs=sample_chart_configs,
            chart_data=sample_chart_data,
            theme="dark"
        )
        
        # Verify that it returns a string
        assert isinstance(html, str)
        
        # Verify that the title is included
        assert f"<title>{title}</title>" in html
        assert f"<h1>{title}</h1>" in html
        
        # Verify that chart creation code is included
        assert "const price_chart = LightweightCharts.createChart" in html
        
        # Verify data is included
        assert "price_chart_series.setData" in html
    
    def test_render_chart_invalid_configs(self, renderer, sample_chart_data):
        """Test rendering with invalid chart configs."""
        # Pass a non-list configs
        with pytest.raises(ConfigurationError) as exc_info:
            renderer.render_chart(
                title="Test",
                chart_configs="not_a_list",  # Should be a list
                chart_data=sample_chart_data
            )
        
        # Check error
        assert "chart_configs must be a list" in str(exc_info.value)
    
    def test_render_chart_invalid_data(self, renderer, sample_chart_configs):
        """Test rendering with invalid chart data."""
        # Pass non-dict data
        with pytest.raises(ConfigurationError) as exc_info:
            renderer.render_chart(
                title="Test",
                chart_configs=sample_chart_configs,
                chart_data="not_a_dict"  # Should be a dict
            )
        
        # Check error
        assert "chart_data must be a dictionary" in str(exc_info.value)
    
    def test_render_chart_light_theme(self, renderer, sample_chart_configs, sample_chart_data):
        """Test rendering chart with light theme."""
        html = renderer.render_chart(
            title="Test Chart",
            chart_configs=sample_chart_configs,
            chart_data=sample_chart_data,
            theme="light"
        )
        
        # Check for light theme elements
        assert "background-color: #ffffff" in html
        assert "color: #333333" in html
        
        # Check for disabled dark theme button
        assert 'id="darkTheme" ' in html
        assert 'id="lightTheme" disabled' in html
    
    def test_save_chart(self, renderer, tmp_path):
        """Test saving chart HTML to file."""
        # Create simple HTML content
        html_content = "<html><body>Test Chart</body></html>"
        
        # Create a temporary file path
        output_path = tmp_path / "test_chart.html"
        
        # Save the chart
        saved_path = renderer.save_chart(
            html_content=html_content,
            output_path=output_path
        )
        
        # Check that the file exists
        assert saved_path.exists()
        
        # Check the content of the file
        with open(saved_path, 'r') as f:
            content = f.read()
            assert content == html_content
    
    def test_save_chart_file_exists(self, renderer, tmp_path):
        """Test saving chart when file already exists."""
        # Create a file
        output_path = tmp_path / "existing.html"
        with open(output_path, 'w') as f:
            f.write("Existing content")
        
        # Try to save without overwrite flag
        # Modified to match the implementation: ConfigurationError is wrapped in DataError
        with pytest.raises(DataError) as exc_info:
            renderer.save_chart(
                html_content="New content",
                output_path=output_path,
                overwrite=False
            )
        
        # Check error cause
        original_error = exc_info.value.__cause__
        assert isinstance(original_error, ConfigurationError)
        assert "already exists and overwrite=False" in str(original_error)
        
        # Now try with overwrite flag
        saved_path = renderer.save_chart(
            html_content="New content",
            output_path=output_path,
            overwrite=True
        )
        
        # Verify that the file was overwritten
        with open(saved_path, 'r') as f:
            content = f.read()
            assert content == "New content"
    
    def test_update_theme(self, renderer):
        """Test updating theme in existing HTML content."""
        # Create sample HTML content with dark theme
        html_content = """
        <html>
        <body style="background-color: #151924;">
        <script>
        document.getElementById('darkTheme').disabled = true;
        document.getElementById('lightTheme').disabled = false;
        </script>
        </body>
        </html>
        """
        
        # Update to light theme
        updated_html = renderer.update_theme(
            html_content=html_content,
            theme="light"
        )
        
        # Check that button states were changed
        assert "document.getElementById('darkTheme').disabled = false" in updated_html
        assert "document.getElementById('lightTheme').disabled = true" in updated_html
    
    def test_update_theme_invalid_theme(self, renderer):
        """Test updating theme with invalid theme value."""
        html_content = "<html></html>"
        
        with pytest.raises(ConfigurationError) as exc_info:
            renderer.update_theme(
                html_content=html_content,
                theme="invalid"
            )
        
        # Check error
        assert "Invalid theme: invalid" in str(exc_info.value)
    
    def test_generate_standalone_html(self, renderer, sample_chart_configs, sample_chart_data, monkeypatch):
        """Test generating and saving a standalone HTML file."""
        # Mock the save_chart method to avoid file system operations
        saved_path = Path("/mock/path/chart.html")
        
        def mock_save_chart(*args, **kwargs):
            return saved_path
        
        monkeypatch.setattr(renderer, "save_chart", mock_save_chart)
        
        # Call the method
        html_content, path = renderer.generate_standalone_html(
            title="Test Standalone Chart",
            chart_configs=sample_chart_configs,
            chart_data=sample_chart_data
        )
        
        # Check that it returns expected values
        assert isinstance(html_content, str)
        assert path == saved_path