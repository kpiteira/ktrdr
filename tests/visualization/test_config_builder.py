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
        assert options['layout']['background']['color'] == '#FFFFFF'
        assert options['layout']['textColor'] == '#333333'
        assert options['grid']['vertLines']['color'] == '#E0E0E0'
    
    def test_create_chart_options_invalid_theme(self):
        """Test creating chart options with invalid theme."""
        # When an invalid theme is provided, it appears to default to light theme
        options = ConfigBuilder.create_chart_options(theme='invalid')
        
        # Should default to light theme
        assert options['layout']['background']['color'] == '#FFFFFF'
        assert options['layout']['textColor'] == '#333333'
    
    def test_create_chart_options_custom_dimensions(self):
        """Test creating chart options with custom dimensions."""
        height = 500
        options = ConfigBuilder.create_chart_options(height=height)
        
        # Check height dimension
        assert options['height'] == height
    
    def test_create_price_chart_options(self):
        """Test creating price chart options."""
        options = ConfigBuilder.create_price_chart_options(height=400)
        
        # Check the height is set correctly
        assert options['height'] == 400
        
        # Check that price chart specific options are set
        assert 'rightPriceScale' in options
        assert options['rightPriceScale']['borderColor'] == '#2A2E39'  # Dark theme default
    
    def test_create_indicator_chart_options(self):
        """Test creating indicator chart options."""
        options = ConfigBuilder.create_indicator_chart_options(height=150)
        
        # Check the height is set correctly
        assert options['height'] == 150
        
        # Check that indicator chart specific options are set
        assert 'timeScale' in options
        assert options['timeScale']['visible'] is False  # Default for indicator charts
    
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
        assert options['priceFormat']['type'] == 'price'
    
    def test_create_series_options_invalid_type(self):
        """Test creating series options with invalid series type."""
        # The implementation does not validate series types
        options = ConfigBuilder.create_series_options(series_type='invalid')
        
        # Should return options with basic properties
        assert 'title' in options
        assert 'priceFormat' in options
    
    def test_create_series_options_with_title(self):
        """Test creating series options with a title."""
        title = "SMA 20"
        options = ConfigBuilder.create_series_options(
            series_type='line', 
            title=title
        )
        
        # Check that title is set
        assert options['title'] == title
    
    def test_create_overlay_series_config(self):
        """Test creating overlay series configuration."""
        overlay_id = 'sma_20_overlay'
        color = '#FF0000'
        title = 'SMA 20'
        
        overlay_config = ConfigBuilder.create_overlay_series_config(
            id=overlay_id,
            color=color,
            title=title 
        )
        
        # Check overlay config
        assert overlay_config['id'] == overlay_id
        assert overlay_config['type'] == 'line'  # Default is line
        assert overlay_config['options']['color'] == color
        assert overlay_config['options']['title'] == title