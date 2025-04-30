"""
Sidebar component for the KTRDR Streamlit UI.

This module handles rendering and configuration of the sidebar elements.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional

import streamlit as st

from ktrdr import get_logger
from ktrdr.config import ConfigLoader
from ktrdr.ui.utils.ui_helpers import safe_render

# Create module-level logger
logger = get_logger(__name__)

@safe_render
def render_sidebar() -> Dict[str, Any]:
    """Render sidebar elements and return the selected configuration.
    
    Returns:
        Dict[str, Any]: Dictionary containing the selected configuration.
    """
    config = {}
    
    st.sidebar.title("KTRDR Configuration")
    
    # Data Selection
    st.sidebar.header("Data")
    
    # Get available symbols from data directory
    data_path = Path("data")
    available_symbols = []
    
    if data_path.exists():
        files = list(data_path.glob("*.csv"))
        for file in files:
            # Extract symbol and timeframe from filename
            # Format is typically SYMBOL_TIMEFRAME.csv (e.g., AAPL_1d.csv)
            parts = file.stem.split('_')
            if len(parts) >= 2:
                symbol = parts[0]
                if symbol not in available_symbols:
                    available_symbols.append(symbol)
    
    if not available_symbols:
        available_symbols = ["AAPL", "MSFT"]  # Default examples
    
    config["symbol"] = st.sidebar.selectbox(
        "Symbol", 
        available_symbols,
        index=0,
        help="Select the trading symbol to analyze",
        key="sidebar_symbol"
    )
    
    config["timeframe"] = st.sidebar.selectbox(
        "Timeframe", 
        ["1m", "5m", "15m", "30m", "1h", "4h", "1d"], 
        index=6,  # Default to daily
        help="Select the data timeframe",
        key="sidebar_timeframe"
    )
    
    date_options = ["Last 30 days", "Last 90 days", "Last 180 days", "Last year", "All available"]
    date_selection = st.sidebar.selectbox(
        "Date Range",
        date_options,
        index=0,
        help="Select the date range to analyze",
        key="sidebar_date_range"
    )
    
    # Map selection to actual date range
    date_ranges = {
        "Last 30 days": 30,
        "Last 90 days": 90,
        "Last 180 days": 180,
        "Last year": 365,
        "All available": None
    }
    config["date_days"] = date_ranges[date_selection]
    
    # Visualization Settings
    st.sidebar.header("Visualization")
    
    # Update theme selection to properly update session state
    selected_theme = st.sidebar.selectbox(
        "Theme",
        ["dark", "light"],
        index=0 if st.session_state.theme == "dark" else 1,
        help="Select the chart theme",
        key="sidebar_theme"
    )
    
    # Explicitly update theme in session state if changed
    if selected_theme != st.session_state.theme:
        st.session_state.theme = selected_theme
        config["theme_changed"] = True
    else:
        config["theme_changed"] = False
    
    config["theme"] = selected_theme
    
    # Always show Indicator settings for better visibility
    st.sidebar.header("Indicator Settings")
    
    indicator_types = [
        "RSI", "SMA", "EMA", "MACD", "Bollinger Bands", 
        "Stochastic", "OBV", "ATR"
    ]
    
    # Get previously selected indicators or default to empty list
    default_indicators = st.session_state.get("selected_indicators", [])
    
    selected_indicators = st.sidebar.multiselect(
        "Select Indicators", 
        indicator_types,
        default=default_indicators,
        help="Choose technical indicators to display on chart",
        key="sidebar_indicators"
    )
    
    # Store selected indicators in session state for persistence
    st.session_state["selected_indicators"] = selected_indicators
    config["selected_indicators"] = selected_indicators
    
    # Dynamic indicator parameters based on selection
    if "RSI" in selected_indicators:
        config["rsi_period"] = st.sidebar.slider(
            "RSI Period", 
            min_value=2, 
            max_value=50, 
            value=st.session_state.get("rsi_period", 14),
            key="sidebar_rsi_period"
        )
        st.session_state["rsi_period"] = config["rsi_period"]
    
    if "SMA" in selected_indicators:
        config["sma_period"] = st.sidebar.slider(
            "SMA Period", 
            min_value=2, 
            max_value=200, 
            value=st.session_state.get("sma_period", 20),
            key="sidebar_sma_period"
        )
        st.session_state["sma_period"] = config["sma_period"]
    
    if "EMA" in selected_indicators:
        config["ema_period"] = st.sidebar.slider(
            "EMA Period", 
            min_value=2, 
            max_value=200, 
            value=st.session_state.get("ema_period", 20),
            key="sidebar_ema_period"
        )
        st.session_state["ema_period"] = config["ema_period"]
    
    # Settings specific to the current tab
    active_tab = st.session_state.get("active_tab", "Data")
    
    # Only show fuzzy settings when on Fuzzy Logic tab for cleaner UI
    if active_tab == "Fuzzy Logic":
        render_fuzzy_settings(config)
    
    # Add Load Data button at the bottom of the sidebar
    if st.sidebar.button("Load Data", key="load_data_button"):
        config["load_data"] = True
    else:
        config["load_data"] = False

    # Add Apply Indicators button when indicators are selected
    if selected_indicators and st.session_state.data is not None:
        if st.sidebar.button("Apply Indicators", key="apply_indicators_button"):
            config["apply_indicators"] = True
        else:
            config["apply_indicators"] = False
    
    return config

@safe_render
def render_indicator_settings(config: Dict[str, Any]):
    """Render indicator-specific settings in the sidebar.
    
    Args:
        config: Configuration dictionary to update with indicator settings
    """
    st.sidebar.header("Indicator Settings")
    
    indicator_types = [
        "RSI", "SMA", "EMA", "MACD", "Bollinger Bands", 
        "Stochastic", "OBV", "ATR"
    ]
    
    selected_indicators = st.sidebar.multiselect(
        "Select Indicators", 
        indicator_types,
        default=["RSI", "SMA"],
        key="sidebar_indicators"
    )
    
    config["selected_indicators"] = selected_indicators
    
    # Dynamic indicator parameters
    if "RSI" in selected_indicators:
        config["rsi_period"] = st.sidebar.slider(
            "RSI Period", 
            min_value=2, 
            max_value=50, 
            value=14,
            key="sidebar_rsi_period"
        )
    
    if "SMA" in selected_indicators:
        config["sma_period"] = st.sidebar.slider(
            "SMA Period", 
            min_value=2, 
            max_value=200, 
            value=20,
            key="sidebar_sma_period"
        )
    
    if "EMA" in selected_indicators:
        config["ema_period"] = st.sidebar.slider(
            "EMA Period", 
            min_value=2, 
            max_value=200, 
            value=20,
            key="sidebar_ema_period"
        )
        
    if "MACD" in selected_indicators:
        st.sidebar.subheader("MACD Parameters")
        config["macd_fast_period"] = st.sidebar.slider(
            "Fast Period", 
            min_value=5, 
            max_value=30, 
            value=12,
            key="sidebar_macd_fast"
        )
        config["macd_slow_period"] = st.sidebar.slider(
            "Slow Period", 
            min_value=10, 
            max_value=50, 
            value=26,
            key="sidebar_macd_slow"
        )
        config["macd_signal_period"] = st.sidebar.slider(
            "Signal Period", 
            min_value=3, 
            max_value=20, 
            value=9,
            key="sidebar_macd_signal"
        )
    
    if "Bollinger Bands" in selected_indicators:
        st.sidebar.subheader("Bollinger Bands Parameters")
        config["bb_period"] = st.sidebar.slider(
            "Period", 
            min_value=5, 
            max_value=50, 
            value=20,
            key="sidebar_bb_period"
        )
        config["bb_std_dev"] = st.sidebar.slider(
            "Standard Deviation", 
            min_value=1.0, 
            max_value=4.0, 
            value=2.0,
            step=0.1,
            key="sidebar_bb_std_dev"
        )
        
    if "Stochastic" in selected_indicators:
        st.sidebar.subheader("Stochastic Parameters")
        config["stoch_k_period"] = st.sidebar.slider(
            "K Period", 
            min_value=5, 
            max_value=30, 
            value=14,
            key="sidebar_stoch_k"
        )
        config["stoch_d_period"] = st.sidebar.slider(
            "D Period", 
            min_value=1, 
            max_value=10, 
            value=3,
            key="sidebar_stoch_d"
        )
        
    if "ATR" in selected_indicators:
        config["atr_period"] = st.sidebar.slider(
            "ATR Period", 
            min_value=5, 
            max_value=30, 
            value=14,
            key="sidebar_atr_period"
        )

@safe_render
def render_fuzzy_settings(config: Dict[str, Any]):
    """Render fuzzy logic settings in the sidebar.
    
    Args:
        config: Configuration dictionary to update with fuzzy logic settings
    """
    st.sidebar.header("Fuzzy Settings")
    
    # Load available fuzzy configurations
    config_path = Path("config/fuzzy.yaml")
    if config_path.exists():
        config["fuzzy_file"] = config_path
        
        # Load configuration options
        try:
            config_loader = ConfigLoader()
            fuzzy_config = config_loader.load_fuzzy_defaults()
            available_strategies = list(fuzzy_config.keys()) if fuzzy_config else []
            
            if available_strategies:
                config["fuzzy_strategy"] = st.sidebar.selectbox(
                    "Fuzzy Strategy",
                    available_strategies,
                    index=0,
                    help="Select the fuzzy logic strategy to use",
                    key="sidebar_fuzzy_strategy"
                )
        except Exception as e:
            logger.error(f"Error loading fuzzy configurations: {str(e)}")
            st.sidebar.error("Failed to load fuzzy configurations")