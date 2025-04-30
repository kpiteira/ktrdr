"""
Main entry point for the KTRDR Streamlit UI.

This module provides the main Streamlit application entry point and UI layout.
"""
import streamlit as st
import pandas as pd
import traceback
from pathlib import Path

from ktrdr import get_logger
from ktrdr.ui.components.sidebar import render_sidebar
from ktrdr.ui.tabs.data_tab import render_data_tab, load_data
from ktrdr.ui.tabs.indicators_tab import render_indicators_tab, compute_indicators
from ktrdr.ui.tabs.fuzzy_tab import render_fuzzy_tab, apply_fuzzy_logic
from ktrdr.ui.utils.session import initialize_state, force_rerun, set_theme
from ktrdr.ui.utils.ui_helpers import create_debug_section

# Create module-level logger
logger = get_logger(__name__)

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
    initialize_state()
    
    # Render sidebar and get configuration
    config = render_sidebar()
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Data", "Indicators", "Fuzzy Logic"])
    
    # Track the active tab
    tab_names = ["Data", "Indicators", "Fuzzy Logic"]
    old_tab = st.session_state.get("active_tab", "Data")
    
    # Handle theme changes from the sidebar
    if config.get("theme_changed", False):
        set_theme(config["theme"])
        force_rerun()
    
    # Handle load data button click
    if config.get("load_data"):
        load_data(config["symbol"], config["timeframe"], config["date_days"])
        
    # Handle indicators computation when data is available
    if st.session_state.data is not None:
        # Check for indicators - process either with the Apply Indicators button or when indicators are selected
        if (config.get("apply_indicators", False) or "selected_indicators" in config) and config["selected_indicators"]:
            compute_indicators(st.session_state.data, config["selected_indicators"], config)
        
        # Handle fuzzy logic configuration
        if "fuzzy_strategy" in config and config["fuzzy_strategy"]:
            apply_fuzzy_logic(st.session_state.data, config["fuzzy_strategy"])
    
    # Render content for each tab with proper tab switching handling
    with tab1:
        new_tab = "Data"
        if st.session_state.get("active_tab") != new_tab:
            from ktrdr.ui.utils.session import handle_tab_switch
            handle_tab_switch(old_tab, new_tab)
        render_data_tab()
    
    with tab2:
        new_tab = "Indicators"
        if st.session_state.get("active_tab") != new_tab:
            from ktrdr.ui.utils.session import handle_tab_switch
            handle_tab_switch(old_tab, new_tab)
        render_indicators_tab()
    
    with tab3:
        new_tab = "Fuzzy Logic"
        if st.session_state.get("active_tab") != new_tab:
            from ktrdr.ui.utils.session import handle_tab_switch
            handle_tab_switch(old_tab, new_tab)
        render_fuzzy_tab()
    
    # Add a debug expander at the bottom for easier troubleshooting
    with st.expander("Debug Tools", expanded=False):
        if st.button("Force Refresh Charts"):
            # Clear any cached charts
            keys_to_clear = [k for k in st.session_state.keys() 
                             if k.startswith("chart_") or k.startswith("cached_") or k.endswith("_container")]
            for k in keys_to_clear:
                del st.session_state[k]
            st.success("Chart cache cleared! Refreshing...")
            force_rerun()
            
        st.write("Active Tab:", st.session_state.get("active_tab"))
        st.write("State Version:", st.session_state.get("state_version", 0))
        st.write("Render Count:", st.session_state.get("render_count", 0))
    
    # Add debug section at the bottom of the page when in debug mode
    if st.session_state.get("debug_mode", False):
        create_debug_section()


if __name__ == "__main__":
    run_app()