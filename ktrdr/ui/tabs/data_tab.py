"""
Data tab for the KTRDR Streamlit UI.

This module provides the Data tab UI components and functionality.
"""
import streamlit as st
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import traceback

from ktrdr import get_logger
from ktrdr.data import DataManager
from ktrdr.errors import ConfigurationError, DataError
from ktrdr.ui.components.charts import render_price_chart
from ktrdr.ui.utils.ui_helpers import safe_render
from ktrdr.ui.utils.session import update_data

# Create module-level logger
logger = get_logger(__name__)

@safe_render
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
        
        # Create theme toggle buttons for immediate feedback
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("Dark Theme", key="data_dark_theme_button"):
                st.session_state.theme = "dark"
                st.rerun()
        with col2:
            if st.button("Light Theme", key="data_light_theme_button"):
                st.session_state.theme = "light"
                st.rerun()
        with col3:
            st.write(f"Current theme: {st.session_state.theme.capitalize()}")
        
        # Create a persistent chart container - initialize it properly as an empty container
        if "data_chart_container" not in st.session_state:
            st.session_state.data_chart_container = st.empty()
        elif st.session_state.data_chart_container is None:
            # Re-initialize if it somehow became None
            st.session_state.data_chart_container = st.empty()
            
        # Generate a unique key for this chart instance - helps with consistent rendering
        chart_key = f"chart_{st.session_state.symbol}_{st.session_state.timeframe}_{st.session_state.theme}_{st.session_state.get('render_count', 0)}"
        
        # Use the persistent container to render the chart
        with st.session_state.data_chart_container:
            render_price_chart(
                data=st.session_state.data,
                symbol=st.session_state.symbol,
                timeframe=st.session_state.timeframe,
                theme=st.session_state.theme,
                key=chart_key
            )
    else:
        st.info("No data loaded. Please select a symbol and timeframe from the sidebar and click 'Load Data'.")

def load_data(symbol: str, timeframe: str, date_days: int = 30) -> None:
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
                        # Convert date column to datetime if needed
                        direct_df['date'] = pd.to_datetime(direct_df['date'])
                        direct_df.set_index('date', inplace=True)
                    
                    if not direct_df.empty:
                        df = direct_df
                        logger.info(f"Successfully loaded data directly: {len(df)} rows")
                except Exception as csv_err:
                    logger.error(f"Direct CSV loading also failed: {str(csv_err)}")
                
                # If we're still here, show the error and offer demo data
                if df is None or df.empty:
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
                        sample_df['volume'] = sample_df['volume'].abs()
                        
                        df = sample_df
                        logger.info("Created example data for demonstration")
                    return
            
            # Store in session state
            update_data(df)
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
        logger.error(traceback.format_exc())
        st.error(f"An unexpected error occurred: {str(e)}")
        st.session_state.data = None