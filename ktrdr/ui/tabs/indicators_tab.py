"""
Indicators tab for the KTRDR Streamlit UI.

This module provides the Indicators tab UI components and functionality.
"""
import streamlit as st
import traceback
from typing import Dict, List, Any, Optional

from ktrdr import get_logger
from ktrdr.indicators import IndicatorEngine
from ktrdr.ui.components.charts import render_indicator_chart
from ktrdr.ui.utils.session import set_theme, force_rerun, update_data
from ktrdr.ui.utils.ui_helpers import safe_render

# Create module-level logger
logger = get_logger(__name__)

@safe_render
def render_indicators_tab():
    """Render the Indicators tab content."""
    st.header("Indicator Analysis")
    
    if st.session_state.data is None:
        st.info("No data loaded. Please load data from the Data tab first.")
        return
    
    # Check for selected indicators
    selected_indicators = st.session_state.get("selected_indicators", [])
    
    if not selected_indicators:
        # Show clearer instructions for indicator selection
        st.info("No indicators selected. Please select indicators from the 'Indicator Settings' section in the sidebar.")
        
        # Add a quick selection option right in the tab
        st.subheader("Quick Indicator Selection")
        
        # Create columns for indicator selection
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Add RSI"):
                if "selected_indicators" not in st.session_state:
                    st.session_state.selected_indicators = []
                if "RSI" not in st.session_state.selected_indicators:
                    st.session_state.selected_indicators.append("RSI")
                    st.rerun()
                    
            if st.button("Add MACD"):
                if "selected_indicators" not in st.session_state:
                    st.session_state.selected_indicators = []
                if "MACD" not in st.session_state.selected_indicators:
                    st.session_state.selected_indicators.append("MACD")
                    st.rerun()
                
        with col2:
            if st.button("Add SMA"):
                if "selected_indicators" not in st.session_state:
                    st.session_state.selected_indicators = []
                if "SMA" not in st.session_state.selected_indicators:
                    st.session_state.selected_indicators.append("SMA")
                    st.rerun()
                
            if st.button("Add Bollinger Bands"):
                if "selected_indicators" not in st.session_state:
                    st.session_state.selected_indicators = []
                if "Bollinger Bands" not in st.session_state.selected_indicators:
                    st.session_state.selected_indicators.append("Bollinger Bands")
                    st.rerun()
        
        return
    
    # Display selected indicators
    st.subheader(f"Selected Indicators for {st.session_state.symbol}")
    
    # Show which indicators are currently displayed
    st.write("**Current Indicators:**")
    for indicator in selected_indicators:
        st.write(f"- {indicator}")
    
    # Create theme toggle buttons
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("Dark Theme", key="dark_theme_button"):
            st.session_state.theme = "dark"
            st.rerun()
    with col2:
        if st.button("Light Theme", key="light_theme_button"):
            st.session_state.theme = "light"
            st.rerun()
    with col3:
        st.write(f"Current theme: {st.session_state.theme.capitalize()}")
    
    # Render indicators chart
    try:
        # Check if indicators are computed
        if not st.session_state.indicators:
            with st.spinner("Computing indicators..."):
                # If selected indicators are present but not computed, compute them now
                if "selected_indicators" in st.session_state and st.session_state.selected_indicators:
                    params = {}
                    # Get any saved parameter values from session state
                    for ind in st.session_state.selected_indicators:
                        if ind == "RSI" and "rsi_period" in st.session_state:
                            params["rsi_period"] = st.session_state.rsi_period
                        elif ind == "SMA" and "sma_period" in st.session_state:
                            params["sma_period"] = st.session_state.sma_period
                        elif ind == "EMA" and "ema_period" in st.session_state:
                            params["ema_period"] = st.session_state.ema_period
                            
                    # Compute the indicators
                    compute_indicators(st.session_state.data, st.session_state.selected_indicators, params)
                    st.success("Indicators computed successfully")
                else:
                    st.warning("Selected indicators not found in session state")
                    return
        
        # Create a persistent chart container
        if "indicators_chart_container" not in st.session_state:
            st.session_state.indicators_chart_container = st.empty()
        elif st.session_state.indicators_chart_container is None:
            # Re-initialize if it somehow became None
            st.session_state.indicators_chart_container = st.empty()
            
        # Generate a unique key for this chart instance
        import hashlib
        indicators_str = str(sorted([(k, str(v)) for k, v in st.session_state.indicators.items()]))
        indicators_hash = hashlib.md5(indicators_str.encode()).hexdigest()[:8]
        chart_key = f"ind_chart_{st.session_state.symbol}_{st.session_state.theme}_{indicators_hash}"
        
        # Use the persistent container to render the chart
        with st.session_state.indicators_chart_container:
            render_indicator_chart(
                data=st.session_state.data,
                symbol=st.session_state.symbol,
                indicators=st.session_state.indicators,
                theme=st.session_state.theme,
                height=1000,
                key=chart_key
            )
    
    except Exception as e:
        logger.error(f"Error rendering indicators: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Failed to render indicators: {str(e)}")
        
        # Show more details in an expander
        with st.expander("Error details"):
            st.exception(e)

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
            
            # Initialize indicator state dictionary if not already present
            if "indicators" not in st.session_state:
                st.session_state.indicators = {}
            
            for indicator in selected_indicators:
                if indicator == "RSI":
                    period = params.get("rsi_period", 14)
                    result_df = engine.compute_rsi(
                        data=result_df,
                        period=period,
                        source="close"
                    )
                    # Store indicator config in state
                    st.session_state.indicators["RSI"] = {
                        "period": period,
                        "display_as_overlay": False
                    }
                
                elif indicator == "SMA":
                    period = params.get("sma_period", 20)
                    result_df = engine.compute_sma(
                        data=result_df,
                        period=period,
                        source="close"
                    )
                    st.session_state.indicators["SMA"] = {
                        "period": period,
                        "display_as_overlay": True
                    }
                
                elif indicator == "EMA":
                    period = params.get("ema_period", 20)
                    result_df = engine.compute_ema(
                        data=result_df,
                        period=period,
                        source="close"
                    )
                    st.session_state.indicators["EMA"] = {
                        "period": period,
                        "display_as_overlay": True
                    }
                    
                elif indicator == "MACD":
                    fast_period = params.get("macd_fast_period", 12)
                    slow_period = params.get("macd_slow_period", 26)
                    signal_period = params.get("macd_signal_period", 9)
                    
                    result_df = engine.compute_macd(
                        data=result_df,
                        fast_period=fast_period,
                        slow_period=slow_period,
                        signal_period=signal_period,
                        source="close"
                    )
                    st.session_state.indicators["MACD"] = {
                        "fast_period": fast_period,
                        "slow_period": slow_period,
                        "signal_period": signal_period,
                        "display_as_overlay": False
                    }
                    
                elif indicator == "Bollinger Bands":
                    # Note: If Bollinger Bands computation is not implemented in IndicatorEngine,
                    # this will still fail. You may need to implement it or remove this option.
                    period = params.get("bb_period", 20)
                    std_dev = params.get("bb_std_dev", 2.0)
                    
                    # Since there's no compute_bollinger_bands method in IndicatorEngine yet,
                    # log a warning and skip this indicator
                    logger.warning(f"Bollinger Bands computation not implemented yet")
                    st.warning(f"Bollinger Bands computation not available yet")
                    
                    st.session_state.indicators["Bollinger Bands"] = {
                        "period": period,
                        "std_dev": std_dev,
                        "display_as_overlay": True,
                        "not_implemented": True
                    }
                    
                elif indicator == "Stochastic":
                    # Skip if not implemented
                    logger.warning(f"Stochastic computation not implemented yet")
                    st.warning(f"Stochastic computation not available yet")
                    
                    k_period = params.get("stoch_k_period", 14)
                    d_period = params.get("stoch_d_period", 3)
                    
                    st.session_state.indicators["Stochastic"] = {
                        "k_period": k_period,
                        "d_period": d_period,
                        "display_as_overlay": False,
                        "not_implemented": True
                    }
                    
                elif indicator == "ATR":
                    # Skip if not implemented
                    logger.warning(f"ATR computation not implemented yet")
                    st.warning(f"ATR computation not available yet")
                    
                    period = params.get("atr_period", 14)
                    
                    st.session_state.indicators["ATR"] = {
                        "period": period,
                        "display_as_overlay": False,
                        "not_implemented": True
                    }
                    
                elif indicator == "OBV":
                    # Skip if not implemented
                    logger.warning(f"OBV computation not implemented yet")
                    st.warning(f"OBV computation not available yet")
                    
                    st.session_state.indicators["OBV"] = {
                        "display_as_overlay": False,
                        "not_implemented": True
                    }
            
            # Update the data in session state with indicator values
            update_data(result_df)
            
            logger.info(f"Computed {len(selected_indicators)} indicators: {', '.join(selected_indicators)}")
            return result_df
    
    except Exception as e:
        logger.error(f"Error computing indicators: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Failed to compute indicators: {str(e)}")
        return data