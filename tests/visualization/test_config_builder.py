"""
Tests for the ConfigBuilder class in the visualization module.
"""

import pytest

from ktrdr.visualization.config_builder import ConfigBuilder
from ktrdr.errors import ConfigurationError


class TestConfigBuilder:
    """
    Test suite for the ConfigBuilder class.
    """
    
    def test_create_chart_options_default(self):
        """Test creating chart options with default parameters."""
        options = ConfigBuilder.create_chart_options()
        
        # Check that the required keys are present
        assert 'layout' in options
        assert 'grid' in options
        assert 'crosshair' in options
        assert 'timeScale' in options
        assert 'rightPriceScale' in options
        
        # Check default theme (dark)
        assert options['layout']['background']['color'] == '#151924'
        assert options['layout']['textColor'] == '#d1d4dc'
    
    def test_create_chart_options_light_theme(self):
        """Test creating chart options with light theme."""
        options = ConfigBuilder.create_chart_options(theme='light')
        
        # Check light theme colors
        assert options['layout']['background']['color'] == '#ffffff'
        assert options['layout']['textColor'] == '#333333'
        assert options['grid']['vertLines']['color'] == '#e6e6e6'
    
    def test_create_chart_options_invalid_theme(self):
        """Test creating chart options with invalid theme."""
        # This should raise a ConfigurationError
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigBuilder.create_chart_options(theme='invalid')
        
        # Check the error details
        assert "Invalid theme" in str(exc_info.value)
        assert exc_info.value.error_code == "CONFIG-InvalidTheme"
    
    def test_create_chart_options_custom_dimensions(self):
        """Test creating chart options with custom dimensions."""
        width = 800
        height = 500
        options = ConfigBuilder.create_chart_options(width=width, height=height)
        
        # Check dimensions
        assert options['width'] == width
        assert options['height'] == height
    
    def test_create_price_chart_options(self):
        """Test creating price chart options."""
        options = ConfigBuilder.create_price_chart_options(height=400)
        
        # Check the height is set correctly
        assert options['height'] == 400
        
        # Check that price chart specific options are set
        assert 'rightPriceScale' in options
        assert options['rightPriceScale']['borderColor'] == '#2a2e39'  # Dark theme default
    
    def test_create_indicator_chart_options(self):
        """Test creating indicator chart options."""
        options = ConfigBuilder.create_indicator_chart_options(height=150)
        
        # Check the height is set correctly
        assert options['height'] == 150
        
        # Check that indicator chart specific options are set
        assert 'timeScale' in options
        assert options['timeScale']['visible'] is False  # Default for indicator charts
        
        # Check scaleMargins
        assert 'scaleMargins' in options['rightPriceScale']
        assert 'top' in options['rightPriceScale']['scaleMargins']
        assert 'bottom' in options['rightPriceScale']['scaleMargins']
    
    def test_create_series_options_candlestick(self):
        """Test creating series options for candlestick charts."""
        options = ConfigBuilder.create_series_options(series_type='candlestick')
        
        # Check candlestick specific options
        assert 'upColor' in options
        assert 'downColor' in options
        assert 'wickUpColor' in options
        assert 'wickDownColor' in options
    
    def test_create_series_options_line(self):
        """Test creating series options for line charts."""
        color = '#FF0000'
        line_width = 2.5
        options = ConfigBuilder.create_series_options(
            series_type='line', 
            color=color, 
            line_width=line_width
        )
        
        # Check line specific options
        assert options['color'] == color
        assert options['lineWidth'] == line_width
    
    def test_create_series_options_histogram(self):
        """Test creating series options for histogram charts."""
        options = ConfigBuilder.create_series_options(series_type='histogram')
        
        # Check histogram specific options
        assert 'color' in options
        assert 'priceFormat' in options
        assert options['priceFormat']['type'] == 'volume'
    
    def test_create_series_options_invalid_type(self):
        """Test creating series options with invalid series type."""
        # This should raise a ConfigurationError
        with pytest.raises(ConfigurationError) as exc_info:
            ConfigBuilder.create_series_options(series_type='invalid')
        
        # Check the error details
        assert "Invalid series type" in str(exc_info.value)
        assert exc_info.value.error_code == "CONFIG-InvalidSeriesType"
    
    def test_create_series_options_with_title(self):
        """Test creating series options with a title."""
        title = "SMA 20"
        options = ConfigBuilder.create_series_options(
            series_type='line', 
            title=title
        )
        
        # Check that title is set
        assert options['title'] == title
    
    def test_create_sync_options(self):
        """Test creating synchronization options."""
        target_chart = 'price_chart'
        source_charts = ['indicator_chart1', 'indicator_chart2']
        
        sync_options = ConfigBuilder.create_sync_options(
            target_chart_id=target_chart, 
            source_charts=source_charts
        )
        
        # Check sync options
        assert sync_options['targetChartId'] == target_chart
        assert sync_options['sourceCharts'] == source_charts