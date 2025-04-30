"""
Session state management utilities for the KTRDR Streamlit UI.

This module provides functions to initialize, update, and manage Streamlit session state
in a more structured way.
"""
import streamlit as st
from typing import Any, Dict, Optional

def initialize_state():
    """Initialize all required session state variables if not already set."""
    # Basic application state
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Data"
    
    # State version to track changes and trigger refreshes when needed
    if "state_version" not in st.session_state:
        st.session_state.state_version = 0
        
    # Data state
    if "data" not in st.session_state:
        st.session_state.data = None
    if "symbol" not in st.session_state:
        st.session_state.symbol = None
    if "timeframe" not in st.session_state:
        st.session_state.timeframe = None
    
    # Indicators and visualization state
    if "indicators" not in st.session_state:
        st.session_state.indicators = {}
    if "fuzzy_sets" not in st.session_state:
        st.session_state.fuzzy_sets = {}
    if "chart" not in st.session_state:
        st.session_state.chart = None
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    
    # UI state flags
    if "indicators_first_load" not in st.session_state:
        st.session_state.indicators_first_load = True
    if "render_count" not in st.session_state:
        st.session_state.render_count = 0

def update_data(new_data):
    """Update data and increment state version to trigger refreshes.
    
    Args:
        new_data: DataFrame containing the price data
    """
    st.session_state.data = new_data
    st.session_state.state_version += 1

def force_rerun():
    """Force a rerun of the Streamlit app to refresh all components."""
    st.session_state.render_count += 1
    st.rerun()

def get_state_data() -> Dict[str, Any]:
    """Get a dictionary of all relevant state data for debugging.
    
    Returns:
        Dict containing state information
    """
    return {
        "active_tab": st.session_state.get("active_tab"),
        "symbol": st.session_state.get("symbol"),
        "timeframe": st.session_state.get("timeframe"),
        "theme": st.session_state.get("theme"),
        "has_data": st.session_state.get("data") is not None,
        "has_indicators": bool(st.session_state.get("indicators")),
        "has_fuzzy_sets": bool(st.session_state.get("fuzzy_sets")),
        "state_version": st.session_state.get("state_version", 0),
        "render_count": st.session_state.get("render_count", 0),
    }

def set_theme(theme: str):
    """Set the theme and manage related state updates.
    
    Args:
        theme: Name of the theme ("dark" or "light")
    """
    if theme != st.session_state.theme:
        st.session_state.theme = theme
        # This increases render count to trigger a rerun that will refresh charts
        st.session_state.render_count += 1

def update_state(key, value, trigger_rerender=False):
    """Update state with tracking for changes.
    
    Args:
        key: The key in session state to update
        value: The new value to set
        trigger_rerender: Whether to force a rerun after the update
        
    Returns:
        bool: True if state changed, False otherwise
    """
    from ktrdr import get_logger
    logger = get_logger(__name__)
    
    if key not in st.session_state or st.session_state[key] != value:
        old_value = st.session_state.get(key, None)
        st.session_state[key] = value
        
        # Log significant state changes
        logger.debug(f"State update: {key} changed from {old_value} to {value}")
        
        # Increment version
        st.session_state.state_version = st.session_state.get("state_version", 0) + 1
        
        if trigger_rerender:
            force_rerun()
        
        return True  # State changed
    return False  # No change

def handle_tab_switch(old_tab, new_tab):
    """Manage state persistence when switching tabs.
    
    Args:
        old_tab: The previously active tab
        new_tab: The newly selected tab
    """
    from ktrdr import get_logger
    logger = get_logger(__name__)
    
    logger.debug(f"Tab switch: {old_tab} -> {new_tab}")
    
    # Lock rendering during tab switch to prevent partial renders
    update_state("rendering_locked", True)
    
    # Store any tab-specific state from the old tab
    if old_tab == "Indicators" and st.session_state.get("selected_indicators"):
        # Make sure indicators state is preserved
        logger.debug("Preserving indicators state during tab switch")
        
    # Prepare new tab
    if new_tab == "Data":
        # Ensure data chart container exists
        if "data_chart_container" not in st.session_state:
            st.session_state.data_chart_container = None
    elif new_tab == "Indicators":
        # Ensure indicators chart container exists
        if "indicators_chart_container" not in st.session_state:
            st.session_state.indicators_chart_container = None
    
    # Update the active tab
    st.session_state.active_tab = new_tab
    
    # Unlock rendering
    update_state("rendering_locked", False)
    
    # Always increment render count to force proper redraw
    st.session_state.render_count = st.session_state.get("render_count", 0) + 1