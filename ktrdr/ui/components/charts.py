"""
Chart components for the KTRDR Streamlit UI.

This module provides functions to create and render charts consistently.
"""
import streamlit as st
import traceback
from typing import Dict, Any, Optional

from ktrdr import get_logger
from ktrdr.visualization import Visualizer
from ktrdr.ui.utils.ui_helpers import safe_render

# Create module-level logger
logger = get_logger(__name__)

@safe_render
def render_price_chart(data, symbol: str, timeframe: str, theme: str, height: int = 600, key: Optional[str] = None) -> None:
    """Render a price chart with candlesticks and volume.
    
    Args:
        data: DataFrame containing price data
        symbol: Symbol name for the chart title
        timeframe: Timeframe for the chart title
        theme: Chart theme ('dark' or 'light')
        height: Height of the chart in pixels
        key: Optional cache key for chart persistence
    """
    try:
        # Create a cache key if not provided
        if key is None:
            import hashlib
            # Create a fingerprint based on data and parameters
            data_hash = hashlib.md5(str(data.index[-1]).encode()).hexdigest()[:8]
            key = f"chart_{symbol}_{timeframe}_{theme}_{data_hash}"
        
        # Check if we have a cached version of this chart
        if key == st.session_state.get("last_chart_key", "") and "cached_chart_html" in st.session_state:
            logger.debug(f"Using cached chart for key: {key}")
            # Use cached HTML to avoid recreation
            st.components.v1.html(st.session_state.cached_chart_html, height=height)
            return st.session_state.get("chart", None)
        
        logger.debug(f"Creating new chart for key: {key}")
        visualizer = Visualizer(theme=theme)
        chart = visualizer.create_chart(
            data=data,
            title=f"{symbol} {timeframe} Chart",
            chart_type="candlestick"
        )
        
        # Add volume as a separate panel
        if "volume" in data.columns:
            chart = visualizer.add_indicator_panel(
                chart=chart,
                data=data,
                column="volume",
                panel_type="histogram",
                height=150,
                color="#26A69A",
                title="Volume"
            )
        
        # Configure range slider
        chart = visualizer.configure_range_slider(chart, height=50, show=True)
        
        # Generate HTML and display
        html = visualizer.show(chart)
        st.components.v1.html(html, height=height)
        
        # Store in cache
        st.session_state.last_chart_key = key
        st.session_state.cached_chart_html = html
        st.session_state.chart = chart
        
        return chart
        
    except Exception as e:
        logger.error(f"Error creating price chart: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Could not create chart: {str(e)}")
        return None

@safe_render
def render_indicator_chart(data, symbol: str, indicators: Dict[str, Dict[str, Any]], 
                          theme: str, height: int = 1000, key: Optional[str] = None) -> None:
    """Render a chart with indicators.
    
    Args:
        data: DataFrame containing price and indicator data
        symbol: Symbol name for the chart title
        indicators: Dictionary of indicators configurations
        theme: Chart theme ('dark' or 'light')
        height: Height of the chart in pixels
        key: Optional cache key for chart persistence
    """
    try:
        # Create a cache key if not provided
        if key is None:
            import hashlib
            # Create a fingerprint of the indicators configuration
            indicators_str = str(sorted([(k, str(v)) for k, v in indicators.items()]))
            data_hash = hashlib.md5(str(data.index[-1]).encode()).hexdigest()[:8]
            indicators_hash = hashlib.md5(indicators_str.encode()).hexdigest()[:8]
            key = f"ind_chart_{symbol}_{theme}_{data_hash}_{indicators_hash}"
        
        # Check if we have a cached version of this chart
        if key == st.session_state.get("last_ind_chart_key", "") and "cached_ind_chart_html" in st.session_state:
            logger.debug(f"Using cached indicator chart for key: {key}")
            # Use cached HTML to avoid recreation
            st.components.v1.html(st.session_state.cached_ind_chart_html, height=height, scrolling=True)
            return st.session_state.get("ind_chart", None)
        
        logger.debug(f"Creating new indicator chart for key: {key}")
        visualizer = Visualizer(theme=theme)
        
        # Create the main price chart
        chart = visualizer.create_chart(
            data=data,
            title=f"{symbol} with Indicators",
            chart_type="candlestick"
        )
        
        # Add volume panel if available
        if "volume" in data.columns:
            chart = visualizer.add_indicator_panel(
                chart=chart,
                data=data,
                column="volume",
                panel_type="histogram",
                height=150,
                color="#26A69A",
                title="Volume"
            )
        
        # Add each indicator based on its configuration
        for indicator_name, indicator_config in indicators.items():
            # Skip indicators marked as not implemented
            if indicator_config.get("not_implemented", False):
                logger.debug(f"Skipping not implemented indicator: {indicator_name}")
                continue
            chart = add_indicator_to_chart(chart, visualizer, data, indicator_name, indicator_config)
        
        # Add range slider for better navigation
        chart = visualizer.configure_range_slider(chart, height=50, show=True)
        
        # Generate HTML and display
        html = visualizer.show(chart)
        st.components.v1.html(html, height=height, scrolling=True)
        
        # Store in cache
        st.session_state.last_ind_chart_key = key
        st.session_state.cached_ind_chart_html = html
        st.session_state.ind_chart = chart
        
        return chart
        
    except Exception as e:
        logger.error(f"Error rendering indicator chart: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Failed to render indicator chart: {str(e)}")
        return None

def add_indicator_to_chart(chart, visualizer, data, indicator_name, indicator_config):
    """Add a specific indicator to the chart based on its configuration."""
    if indicator_name == "RSI":
        period = indicator_config.get("period", 14)
        rsi_col = f"RSI_{period}"
        
        if rsi_col in data.columns:
            # RSI should be in a separate panel
            chart = visualizer.add_indicator_panel(
                chart=chart,
                data=data,
                column=rsi_col,
                panel_type="line",
                height=150,
                color="#2962FF",
                title=f"RSI ({period})"
            )
            
    elif indicator_name == "SMA":
        period = indicator_config.get("period", 20)
        sma_col = f"SMA_{period}"
        
        if sma_col in data.columns:
            # SMA should be an overlay on price
            chart = visualizer.add_indicator_overlay(
                chart=chart,
                data=data,
                column=sma_col,
                color="#2962FF",
                title=f"SMA ({period})"
            )
            
    elif indicator_name == "EMA":
        period = indicator_config.get("period", 20)
        ema_col = f"EMA_{period}"
        
        if ema_col in data.columns:
            # EMA should be an overlay on price
            chart = visualizer.add_indicator_overlay(
                chart=chart,
                data=data,
                column=ema_col,
                color="#FF6D00",
                title=f"EMA ({period})"
            )
        
    elif indicator_name == "MACD":
        fast = indicator_config.get("fast_period", 12)
        slow = indicator_config.get("slow_period", 26)
        signal = indicator_config.get("signal_period", 9)
        
        macd_line = f"MACD_{fast}_{slow}"
        signal_line = f"MACD_signal_{fast}_{slow}_{signal}"
        hist_col = f"MACD_hist_{fast}_{slow}_{signal}"
        
        # Check if MACD columns exist in the dataframe
        required_cols = [macd_line, signal_line, hist_col]
        if all(col in data.columns for col in required_cols):
            # Add MACD panel with all components
            chart = visualizer.add_indicator_panel(
                chart=chart,
                data=data,
                column=macd_line,
                panel_type="line",
                height=150,
                color="#2962FF",
                title=f"MACD ({fast},{slow},{signal})"
            )
            
            # Add signal line to the MACD panel
            chart = visualizer.add_indicator_overlay(
                chart=chart,
                data=data,
                column=signal_line,
                panel_id="MACD",
                color="#FF6D00",
                title="Signal"
            )
            
            # Add histogram to the MACD panel
            chart = visualizer.add_indicator_overlay(
                chart=chart,
                data=data,
                column=hist_col,
                panel_id="MACD",
                #panel_type="histogram",
                color="#26A69A",
                title="Histogram"
            )
            
    elif indicator_name == "Bollinger Bands":
        period = indicator_config.get("period", 20)
        std_dev = indicator_config.get("std_dev", 2.0)
        
        upper_col = f"BB_upper_{period}_{std_dev}"
        middle_col = f"BB_middle_{period}"
        lower_col = f"BB_lower_{period}_{std_dev}"
        
        required_cols = [upper_col, middle_col, lower_col]
        if all(col in data.columns for col in required_cols):
            # Bollinger Bands should typically overlay on price
            chart = visualizer.add_indicator_overlay(
                chart=chart,
                data=data,
                column=upper_col,
                color="#2962FF",
                title=f"BB Upper ({period}, {std_dev})"
            )
            chart = visualizer.add_indicator_overlay(
                chart=chart,
                data=data,
                column=middle_col,
                color="#FF6D00",
                title=f"BB Middle ({period})"
            )
            chart = visualizer.add_indicator_overlay(
                chart=chart,
                data=data,
                column=lower_col,
                color="#2962FF",
                title=f"BB Lower ({period}, {std_dev})"
            )
            
    elif indicator_name == "Stochastic":
        k_period = indicator_config.get("k_period", 14)
        d_period = indicator_config.get("d_period", 3)
        
        k_col = f"Stoch_K_{k_period}"
        d_col = f"Stoch_D_{k_period}_{d_period}"
        
        required_cols = [k_col, d_col]
        if all(col in data.columns for col in required_cols):
            # Stochastic oscillator should be in a separate panel
            chart = visualizer.add_indicator_panel(
                chart=chart,
                data=data,
                column=k_col,
                panel_type="line",
                height=150,
                color="#2962FF",
                title=f"Stochastic ({k_period}, {d_period})"
            )
            
            # Add D line to the same panel
            chart = visualizer.add_indicator_overlay(
                chart=chart,
                data=data,
                column=d_col,
                panel_id="Stochastic",
                color="#FF6D00",
                title="D"
            )
            
    elif indicator_name == "ATR":
        period = indicator_config.get("period", 14)
        atr_col = f"ATR_{period}"
        
        if atr_col in data.columns:
            # ATR should be in a separate panel
            chart = visualizer.add_indicator_panel(
                chart=chart,
                data=data,
                column=atr_col,
                panel_type="line",
                height=150,
                color="#9C27B0",
                title=f"ATR ({period})"
            )
            
    elif indicator_name == "OBV":
        obv_col = "OBV"
        
        if obv_col in data.columns:
            # OBV should be in a separate panel
            chart = visualizer.add_indicator_panel(
                chart=chart,
                data=data,
                column=obv_col,
                panel_type="line",
                height=150,
                color="#26A69A",
                title="OBV"
            )
    
    return chart