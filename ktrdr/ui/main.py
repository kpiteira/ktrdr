"""
Main entry point for the KTRDR Streamlit UI.

This module provides the main Streamlit application entry point and UI layout.
"""

import os
import streamlit as st
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from datetime import datetime
import numpy as np

from ktrdr import get_logger
from ktrdr.config import ConfigLoader
from ktrdr.data import DataManager
from ktrdr.errors import ConfigurationError, DataError
from ktrdr.indicators import IndicatorEngine
from ktrdr.fuzzy import FuzzyEngine
from ktrdr.visualization import Visualizer

# Create module-level logger
logger = get_logger(__name__)


def initialize_session_state():
    """Initialize Streamlit session state with default values if not already set."""
    if "data" not in st.session_state:
        st.session_state.data = None
    if "symbol" not in st.session_state:
        st.session_state.symbol = None
    if "timeframe" not in st.session_state:
        st.session_state.timeframe = None
    if "indicators" not in st.session_state:
        st.session_state.indicators = {}
    if "fuzzy_sets" not in st.session_state:
        st.session_state.fuzzy_sets = {}
    if "chart" not in st.session_state:
        st.session_state.chart = None
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"


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
    
    config["theme"] = st.sidebar.selectbox(
        "Theme",
        ["dark", "light"],
        index=0 if st.session_state.theme == "dark" else 1,
        help="Select the chart theme",
        key="sidebar_theme"
    )
    
    # Settings specific to the current tab
    active_tab = st.session_state.get("active_tab", "Data")
    
    if active_tab == "Indicators":
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
    
    elif active_tab == "Fuzzy Logic":
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
    
    # Add Load Data button at the bottom of the sidebar
    if st.sidebar.button("Load Data", key="load_data_button"):
        config["load_data"] = True
    else:
        config["load_data"] = False
    
    return config


def render_data_tab():
    """Render the Data tab content."""
    st.header("Data View")
    
    if st.session_state.data is not None:
        st.write(f"Symbol: {st.session_state.symbol}")
        st.write(f"Timeframe: {st.session_state.timeframe}")
        st.write(f"Rows: {len(st.session_state.data)}")
        
        # Display data preview in an expander
        with st.expander("Data Preview"):
            st.dataframe(st.session_state.data.head(10))
        
        # Display data statistics
        with st.expander("Data Statistics"):
            st.write(st.session_state.data.describe())
        
        # Create a candlestick chart
        st.subheader("Price Chart")
        try:
            visualizer = Visualizer(theme=st.session_state.theme)
            chart = visualizer.create_chart(
                data=st.session_state.data,
                title=f"{st.session_state.symbol} {st.session_state.timeframe} Chart",
                chart_type="candlestick"
            )
            
            # Add volume as a separate panel
            if "volume" in st.session_state.data.columns:
                chart = visualizer.add_indicator_panel(
                    chart=chart,
                    data=st.session_state.data,
                    column="volume",
                    panel_type="histogram",
                    height=150,
                    color="#26A69A",
                    title="Volume"
                )
            
            # Configure range slider
            chart = visualizer.configure_range_slider(chart, height=50, show=True)
            
            # Store chart in session state for reuse in other tabs
            st.session_state.chart = chart
            
            # Generate HTML and display
            html = visualizer.show(chart)
            st.components.v1.html(html, height=600)
        except Exception as e:
            logger.error(f"Error creating chart: {str(e)}")
            st.error(f"Could not create chart: {str(e)}")
    else:
        st.info("No data loaded. Please select a symbol and timeframe from the sidebar and click 'Load Data'.")


def render_indicators_tab():
    """Render the Indicators tab content."""
    st.header("Indicator Analysis")
    
    if st.session_state.data is None:
        st.info("No data loaded. Please load data from the Data tab first.")
        return
    
    if not st.session_state.indicators:
        st.info("No indicators selected. Please select indicators from the sidebar.")
        return
    
    # Display selected indicators
    st.subheader(f"Selected Indicators for {st.session_state.symbol}")
    
    # Create theme toggle buttons
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("Dark Theme", key="dark_theme_button"):
            st.session_state.theme = "dark"
    with col2:
        if st.button("Light Theme", key="light_theme_button"):
            st.session_state.theme = "light"
    with col3:
        st.write(f"Current theme: {st.session_state.theme.capitalize()}")
    
    # Create visualization options - only keep Price Chart option
    selected_display = "Price Chart with Indicators"
    
    try:
        visualizer = Visualizer(theme=st.session_state.theme)
        
        # Create a new chart for the price view
        chart = visualizer.create_chart(
            data=st.session_state.data,
            title=f"{st.session_state.symbol} with Indicators",
            chart_type="candlestick"
        )
        
        # Add volume panel if available
        if "volume" in st.session_state.data.columns:
            chart = visualizer.add_indicator_panel(
                chart=chart,
                data=st.session_state.data,
                column="volume",
                panel_type="histogram",
                height=150,
                color="#26A69A",
                title="Volume"
            )
        
        # Add selected indicators based on their 'display_as_overlay' property
        for indicator_name, indicator_config in st.session_state.indicators.items():
            if indicator_name == "RSI" and "RSI" in st.session_state.indicators:
                rsi_period = indicator_config.get("period", 14)
                rsi_col = f"RSI_{rsi_period}"
                display_as_overlay = indicator_config.get("display_as_overlay", False)
                
                if rsi_col in st.session_state.data.columns:
                    if display_as_overlay:
                        chart = visualizer.add_indicator_overlay(
                            chart=chart,
                            data=st.session_state.data,
                            column=rsi_col,
                            color="#9C27B0",
                            title=f"RSI ({rsi_period})"
                        )
                    else:
                        chart = visualizer.add_indicator_panel(
                            chart=chart,
                            data=st.session_state.data,
                            column=rsi_col,
                            panel_type="line",
                            height=150,
                            color="#9C27B0",
                            title=f"RSI ({rsi_period})"
                        )
            
            elif indicator_name == "SMA":
                sma_period = indicator_config.get("period", 20)
                sma_col = f"SMA_{sma_period}"
                display_as_overlay = indicator_config.get("display_as_overlay", True)
                
                if sma_col in st.session_state.data.columns:
                    if display_as_overlay:
                        chart = visualizer.add_indicator_overlay(
                            chart=chart,
                            data=st.session_state.data,
                            column=sma_col,
                            color="#2962FF",
                            title=f"SMA ({sma_period})"
                        )
                    else:
                        chart = visualizer.add_indicator_panel(
                            chart=chart,
                            data=st.session_state.data,
                            column=sma_col,
                            panel_type="line",
                            height=150,
                            color="#2962FF",
                            title=f"SMA ({sma_period})"
                        )
                
            elif indicator_name == "EMA":
                ema_period = indicator_config.get("period", 20)
                ema_col = f"EMA_{ema_period}"
                display_as_overlay = indicator_config.get("display_as_overlay", True)
                
                if ema_col in st.session_state.data.columns:
                    if display_as_overlay:
                        chart = visualizer.add_indicator_overlay(
                            chart=chart,
                            data=st.session_state.data,
                            column=ema_col,
                            color="#FF6D00",
                            title=f"EMA ({ema_period})"
                        )
                    else:
                        chart = visualizer.add_indicator_panel(
                            chart=chart,
                            data=st.session_state.data,
                            column=ema_col,
                            panel_type="line",
                            height=150,
                            color="#FF6D00",
                            title=f"EMA ({ema_period})"
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
                if all(col in st.session_state.data.columns for col in required_cols):
                    # Add MACD panel with all components
                    chart = visualizer.add_indicator_panel(
                        chart=chart,
                        data=st.session_state.data,
                        column=macd_line,
                        panel_type="line",
                        height=150,
                        color="#2962FF",
                        title=f"MACD ({fast},{slow},{signal})"
                    )
                    
                    # Add signal line to the MACD panel
                    chart = visualizer.add_indicator_overlay(
                        chart=chart,
                        data=st.session_state.data,
                        column=signal_line,
                        panel_id="MACD",  # Use panel_id parameter instead of chart
                        color="#FF6D00",
                        title="Signal"
                    )
                    
                    # Add histogram to the MACD panel
                    chart = visualizer.add_indicator_overlay(
                        chart=chart,
                        data=st.session_state.data,
                        column=hist_col,
                        panel_id="MACD",  # Use panel_id parameter instead of chart
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
                if all(col in st.session_state.data.columns for col in required_cols):
                    # Bollinger Bands should typically overlay on price
                    chart = visualizer.add_indicator_overlay(
                        chart=chart,
                        data=st.session_state.data,
                        column=upper_col,
                        color="#2962FF",
                        title=f"BB Upper ({period}, {std_dev})"
                    )
                    chart = visualizer.add_indicator_overlay(
                        chart=chart,
                        data=st.session_state.data,
                        column=middle_col,
                        color="#FF6D00",
                        title=f"BB Middle ({period})"
                    )
                    chart = visualizer.add_indicator_overlay(
                        chart=chart,
                        data=st.session_state.data,
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
                if all(col in st.session_state.data.columns for col in required_cols):
                    # Stochastic oscillator should be in a separate panel
                    chart = visualizer.add_indicator_panel(
                        chart=chart,
                        data=st.session_state.data,
                        column=k_col,
                        panel_type="line",
                        height=150,
                        color="#2962FF",
                        title=f"Stochastic ({k_period}, {d_period})"
                    )
                    
                    # Add D line to the same panel
                    chart = visualizer.add_indicator_overlay(
                        chart=chart,
                        data=st.session_state.data,
                        column=d_col,
                        color="#FF6D00",
                        title="D"
                    )
                    
            elif indicator_name == "ATR":
                period = indicator_config.get("period", 14)
                atr_col = f"ATR_{period}"
                
                if atr_col in st.session_state.data.columns:
                    # ATR should be in a separate panel
                    chart = visualizer.add_indicator_panel(
                        chart=chart,
                        data=st.session_state.data,
                        column=atr_col,
                        panel_type="line",
                        height=150,
                        color="#9C27B0",
                        title=f"ATR ({period})"
                    )
                    
            elif indicator_name == "OBV":
                obv_col = "OBV"
                
                if obv_col in st.session_state.data.columns:
                    # OBV should be in a separate panel
                    chart = visualizer.add_indicator_panel(
                        chart=chart,
                        data=st.session_state.data,
                        column=obv_col,
                        panel_type="line",
                        height=150,
                        color="#26A69A",
                        title="OBV"
                    )
        
        # Add range slider for better navigation
        chart = visualizer.configure_range_slider(chart, height=50, show=True)
        
        # Generate HTML and display - increase height to make all panels visible
        html = visualizer.show(chart)
        st.components.v1.html(html, height=1000, scrolling=True)
    
    except Exception as e:
        logger.error(f"Error rendering indicators: {str(e)}")
        st.error(f"Failed to render indicators: {str(e)}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")


def render_fuzzy_tab():
    """Render the Fuzzy Logic tab content."""
    st.header("Fuzzy Logic Analysis")
    
    if st.session_state.data is None:
        st.info("No data loaded. Please load data from the Data tab first.")
        return
    
    if not st.session_state.fuzzy_sets:
        st.info("No fuzzy sets configured. Please select a fuzzy strategy from the sidebar.")
        return
    
    st.subheader(f"Fuzzy Logic Analysis for {st.session_state.symbol}")
    
    # Add placeholder for the visualization of fuzzy sets
    # This will be implemented in Task 5.3
    st.info("Fuzzy visualization components will be implemented in Task 5.3.")
    

def load_data(symbol: str, timeframe: str, date_days: Optional[int] = 30) -> None:
    """Load data for the specified symbol and timeframe.
    
    Args:
        symbol: The trading symbol to load.
        timeframe: The data timeframe.
        date_days: Number of days to load, or None for all available data.
    """
    try:
        with st.spinner(f"Loading {symbol} {timeframe} data..."):
            # Add debug log before calling data_manager.load
            logger.debug(f"Attempting to load {symbol} {timeframe} data with days={date_days}")
            
            data_manager = DataManager()
            
            # Check if the file exists first
            file_path = Path("data") / f"{symbol}_{timeframe}.csv"
            if not file_path.exists():
                st.error(f"No data file found at {file_path}. Please ensure you have data files in the 'data' directory.")
                st.session_state.data = None
                return
                
            # Load data directly
            logger.debug(f"Loading data from {file_path}")
            df = data_manager.load(
                symbol=symbol,
                interval=timeframe,
                days=date_days
            )
            
            # Add more detailed debug after loading
            if df is not None:
                logger.debug(f"Data loaded successfully: {len(df)} rows, columns: {list(df.columns)}")
            else:
                logger.warning(f"Data loaded is None for {symbol} {timeframe}")
            
            # Check if DataFrame is empty
            if df is None or df.empty:
                # Try direct loading as a last resort
                logger.debug("DataManager returned empty data, trying direct pandas loading")
                try:
                    direct_df = pd.read_csv(file_path)
                    if 'date' in direct_df.columns:
                        direct_df['date'] = pd.to_datetime(direct_df['date'])
                        direct_df.set_index('date', inplace=True)
                    
                    if not direct_df.empty:
                        logger.info(f"Successfully loaded {len(direct_df)} rows directly from CSV")
                        st.session_state.data = direct_df
                        st.session_state.symbol = symbol
                        st.session_state.timeframe = timeframe
                        st.success(f"Successfully loaded {symbol} {timeframe} data with {len(direct_df)} rows (direct load)")
                        return
                except Exception as csv_err:
                    logger.error(f"Direct CSV loading also failed: {str(csv_err)}")
                
                # If we're still here, show the error and offer demo data
                st.warning(f"No data found for {symbol} ({timeframe}). Please check that the data file exists and contains data.")
                if file_path.exists():
                    st.info(f"Found data file at {file_path} but it appears to be empty or improperly formatted.")
                    
                    # Create example data for demonstration purposes
                    st.info("Creating example data for demonstration purposes...")
                    
                    today = datetime.now()
                    dates = pd.date_range(end=today, periods=100, freq='D')
                    
                    # Create a sample DataFrame with simulated price data
                    sample_df = pd.DataFrame({
                        'open': [100 + i/10 + np.random.normal(0, 1) for i in range(len(dates))],
                        'high': [102 + i/10 + np.random.normal(0, 1) for i in range(len(dates))],
                        'low': [99 + i/10 + np.random.normal(0, 1) for i in range(len(dates))],
                        'close': [101 + i/10 + np.random.normal(0, 1) for i in range(len(dates))],
                        'volume': [1000000 + np.random.normal(0, 100000) for i in range(len(dates))]
                    }, index=dates)
                    
                    # Make sure high is highest and low is lowest
                    sample_df['high'] = sample_df[['open', 'high', 'close']].max(axis=1) + 0.5
                    sample_df['low'] = sample_df[['open', 'low', 'close']].min(axis=1) - 0.5
                    
                    # Store in session state
                    st.session_state.data = sample_df
                    st.session_state.symbol = symbol
                    st.session_state.timeframe = timeframe
                    
                    logger.info(f"Created example data with {len(sample_df)} rows")
                    st.success(f"Created example data for {symbol} {timeframe} with {len(sample_df)} rows")
                else:
                    st.error(f"No data file found at {file_path}. Please ensure you have data files in the 'data' directory.")
                    st.session_state.data = None
                return
            
            # Store in session state
            st.session_state.data = df
            st.session_state.symbol = symbol
            st.session_state.timeframe = timeframe
            
            logger.info(f"Loaded {len(df)} rows of {symbol} {timeframe} data")
            st.success(f"Successfully loaded {symbol} {timeframe} data with {len(df)} rows")
    except (ConfigurationError, DataError) as e:
        logger.error(f"Error loading data: {str(e)}")
        st.error(f"Failed to load data: {str(e)}")
        st.session_state.data = None
    except Exception as e:
        logger.error(f"Unexpected error loading data: {str(e)}")
        st.error(f"An unexpected error occurred: {str(e)}")
        st.session_state.data = None


def compute_indicators(data, selected_indicators, params):
    """Compute selected indicators on the data.
    
    Args:
        data: The price data DataFrame.
        selected_indicators: List of selected indicator names.
        params: Dictionary of indicator parameters.
    
    Returns:
        DataFrame with indicators added.
    """
    try:
        with st.spinner("Computing indicators..."):
            engine = IndicatorEngine()
            result_df = data.copy()
            
            # We won't clear the indicators dictionary anymore - we want to preserve indicators
            # that may have been added by other functions (like apply_fuzzy_logic)
            # Instead, we'll update the dictionary with the new indicators
            if "indicators" not in st.session_state:
                st.session_state.indicators = {}
            
            for indicator in selected_indicators:
                if indicator == "RSI":
                    period = params.get("rsi_period", 14)
                    result_df = engine.compute_rsi(result_df, period=period)
                    # Store display_as_overlay property (RSI should be false - separate panel)
                    st.session_state.indicators["RSI"] = {
                        "period": period,
                        "display_as_overlay": False  # RSI uses a different scale (0-100)
                    }
                    logger.info(f"Added RSI indicator with period {period}")
                
                elif indicator == "SMA":
                    period = params.get("sma_period", 20)
                    result_df = engine.compute_sma(result_df, period=period)
                    st.session_state.indicators["SMA"] = {
                        "period": period,
                        "display_as_overlay": True  # SMA uses the same scale as price
                    }
                    logger.info(f"Added SMA indicator with period {period}")
                
                elif indicator == "EMA":
                    period = params.get("ema_period", 20)
                    result_df = engine.compute_ema(result_df, period=period)
                    st.session_state.indicators["EMA"] = {
                        "period": period,
                        "display_as_overlay": True  # EMA uses the same scale as price
                    }
                    logger.info(f"Added EMA indicator with period {period}")
                    
                elif indicator == "MACD":
                    fast_period = params.get("macd_fast_period", 12)
                    slow_period = params.get("macd_slow_period", 26)
                    signal_period = params.get("macd_signal_period", 9)
                    result_df = engine.compute_macd(result_df, 
                                                  fast_period=fast_period, 
                                                  slow_period=slow_period, 
                                                  signal_period=signal_period)
                    st.session_state.indicators["MACD"] = {
                        "fast_period": fast_period,
                        "slow_period": slow_period,
                        "signal_period": signal_period,
                        "display_as_overlay": False  # MACD uses a different scale than price
                    }
                    logger.info(f"Added MACD indicator with parameters: fast={fast_period}, slow={slow_period}, signal={signal_period}")
                    
                elif indicator == "Bollinger Bands":
                    period = params.get("bb_period", 20)
                    std_dev = params.get("bb_std_dev", 2)
                    result_df = engine.compute_bollinger_bands(result_df, period=period, std_dev=std_dev)
                    st.session_state.indicators["Bollinger Bands"] = {
                        "period": period,
                        "std_dev": std_dev,
                        "display_as_overlay": True  # Bollinger Bands use same scale as price
                    }
                    logger.info(f"Added Bollinger Bands with period {period} and std_dev {std_dev}")
                    
                elif indicator == "Stochastic":
                    k_period = params.get("stoch_k_period", 14)
                    d_period = params.get("stoch_d_period", 3)
                    result_df = engine.compute_stochastic(result_df, k_period=k_period, d_period=d_period)
                    st.session_state.indicators["Stochastic"] = {
                        "k_period": k_period,
                        "d_period": d_period,
                        "display_as_overlay": False  # Stochastic uses a different scale (0-100)
                    }
                    logger.info(f"Added Stochastic with k_period {k_period} and d_period {d_period}")
                    
                elif indicator == "ATR":
                    period = params.get("atr_period", 14)
                    result_df = engine.compute_atr(result_df, period=period)
                    st.session_state.indicators["ATR"] = {
                        "period": period,
                        "display_as_overlay": False  # ATR uses a different scale than price
                    }
                    logger.info(f"Added ATR with period {period}")
                    
                elif indicator == "OBV":
                    result_df = engine.compute_obv(result_df)
                    st.session_state.indicators["OBV"] = {
                        "display_as_overlay": False  # OBV uses a much different scale than price
                    }
                    logger.info("Added OBV indicator")
            
            st.session_state.data = result_df
            logger.info(f"Computed {len(selected_indicators)} indicators: {', '.join(selected_indicators)}")
            return result_df
    
    except Exception as e:
        logger.error(f"Error computing indicators: {str(e)}")
        st.error(f"Failed to compute indicators: {str(e)}")
        return data


def apply_fuzzy_logic(data, strategy):
    """Apply fuzzy logic strategy to the data.
    
    Args:
        data: The price data DataFrame.
        strategy: The fuzzy logic strategy to apply.
    """
    try:
        with st.spinner(f"Applying fuzzy logic strategy: {strategy}..."):
            # Import FuzzyConfigLoader from the fuzzy package
            from ktrdr.fuzzy import FuzzyConfigLoader, FuzzyEngine
            
            # Create a proper FuzzyConfigLoader instance
            config_loader = FuzzyConfigLoader(config_dir=Path("config"))
            
            # Load the fuzzy configuration for the selected strategy
            # This will return a proper FuzzyConfig object that the FuzzyEngine expects
            fuzzy_config = config_loader.load_from_yaml("fuzzy.yaml")
            
            logger.info(f"Applying fuzzy strategy: {strategy}")
            
            # Create a fuzzy engine with the properly loaded config
            engine = FuzzyEngine(config=fuzzy_config)
            
            # Process each indicator in the data
            fuzzy_results = {}
            available_indicators = engine.get_available_indicators()
            
            # Initialize indicators dictionary if it doesn't exist
            if "indicators" not in st.session_state:
                st.session_state.indicators = {}
            
            for indicator in available_indicators:
                # Check if indicator data is available
                # For RSI, the column would be named "RSI_14" for period 14
                indicator_cols = [col for col in data.columns if col.lower().startswith(indicator.lower())]
                
                if not indicator_cols:
                    logger.warning(f"Indicator {indicator} not found in data. Available columns: {list(data.columns)}")
                    # If indicator not in data, compute it first
                    indicator_engine = IndicatorEngine()
                    
                    if indicator.lower() == "rsi":
                        period = 14
                        data = indicator_engine.compute_rsi(data, period=period)
                        indicator_cols = [col for col in data.columns if col.lower().startswith(indicator.lower())]
                        # Register RSI in the session state indicators with display_as_overlay parameter
                        st.session_state.indicators["RSI"] = {
                            "period": period,
                            "display_as_overlay": False  # RSI should be in a separate panel
                        }
                        logger.info(f"Added RSI indicator with period {period} from fuzzy logic")
                    
                    elif indicator.lower() == "macd":
                        fast_period = 12
                        slow_period = 26
                        signal_period = 9
                        data = indicator_engine.compute_macd(
                            data, 
                            fast_period=fast_period, 
                            slow_period=slow_period, 
                            signal_period=signal_period
                        )
                        indicator_cols = [col for col in data.columns if col.lower().startswith(indicator.lower())]
                        # Register MACD in the session state indicators with display_as_overlay parameter
                        st.session_state.indicators["MACD"] = {
                            "fast_period": fast_period,
                            "slow_period": slow_period,
                            "signal_period": signal_period,
                            "display_as_overlay": False  # MACD should be in a separate panel
                        }
                        logger.info(f"Added MACD indicator with fast={fast_period}, slow={slow_period}, signal={signal_period} from fuzzy logic")
                    
                    elif indicator.lower() == "ema":
                        period = 20
                        data = indicator_engine.compute_ema(data, period=period)
                        indicator_cols = [col for col in data.columns if col.lower().startswith(indicator.lower())]
                        # Register EMA in the session state indicators with display_as_overlay parameter
                        st.session_state.indicators["EMA"] = {
                            "period": period,
                            "display_as_overlay": True  # EMA should overlay on price chart
                        }
                        logger.info(f"Added EMA indicator with period {period} from fuzzy logic")
                
                if indicator_cols:
                    # Use the first matching column
                    indicator_col = indicator_cols[0]
                    logger.info(f"Processing fuzzy sets for {indicator_col}")
                    
                    # Get indicator values
                    indicator_values = data[indicator_col]
                    
                    # Get fuzzy membership for this indicator
                    fuzzy_memberships = engine.fuzzify(indicator, indicator_values)
                    
                    # Store the results
                    fuzzy_results[indicator] = fuzzy_memberships
            
            # Store fuzzy sets in session state
            st.session_state.fuzzy_sets = fuzzy_results
            # Store updated data in session state
            st.session_state.data = data
            logger.info(f"Applied fuzzy strategy with {len(fuzzy_results)} indicators")
            
            # Update success message
            st.success(f"Successfully applied fuzzy strategy: {strategy}")
            
    except Exception as e:
        logger.error(f"Error applying fuzzy logic: {str(e)}")
        st.error(f"Failed to apply fuzzy logic: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        st.session_state.fuzzy_sets = {}


def run_app():
    """Main entry point for the Streamlit app."""
    # Set page configuration
    st.set_page_config(
        page_title="KTRDR Trading System",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Display title
    st.title("KTRDR Trading System")
    
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar and get configuration
    config = render_sidebar()
    
    # Update theme in session state if changed
    if config["theme"] != st.session_state.theme:
        st.session_state.theme = config["theme"]
    
    # Create tabs
    tabs = st.tabs(["Data", "Indicators", "Fuzzy Logic"])
    
    # Track the active tab
    tab_names = ["Data", "Indicators", "Fuzzy Logic"]
    
    # Handle load data button click
    if config["load_data"]:
        load_data(config["symbol"], config["timeframe"], config["date_days"])
        
    # Handle indicators computation
    if st.session_state.data is not None:
        # Always check for indicators when data is available
        if "selected_indicators" in config and config["selected_indicators"]:
            compute_indicators(st.session_state.data, config["selected_indicators"], config)
        
        # Handle fuzzy logic configuration
        if "fuzzy_strategy" in config and config["fuzzy_strategy"]:
            apply_fuzzy_logic(st.session_state.data, config["fuzzy_strategy"])
    
    # Render content for the active tab
    with tabs[0]:
        st.session_state.active_tab = "Data"
        render_data_tab()
    
    with tabs[1]:
        st.session_state.active_tab = "Indicators"
        render_indicators_tab()
    
    with tabs[2]:
        st.session_state.active_tab = "Fuzzy Logic"
        render_fuzzy_tab()


if __name__ == "__main__":
    run_app()