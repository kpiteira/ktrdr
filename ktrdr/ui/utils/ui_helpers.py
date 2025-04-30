"""
UI helper utilities for the KTRDR Streamlit UI.

This module provides utility functions for common UI operations and error handling.
"""
import streamlit as st
import traceback
import functools
from typing import Any, Callable, TypeVar, cast

from ktrdr import get_logger

# Create module-level logger
logger = get_logger(__name__)

# Function type for decorators
F = TypeVar('F', bound=Callable[..., Any])

def safe_render(func: F) -> F:
    """Decorator for safely rendering UI components with proper error handling.
    
    Args:
        func: The function to wrap with error handling
        
    Returns:
        Wrapped function that catches and displays errors appropriately
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log the full error with traceback
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Display a user-friendly error
            st.error(f"Error rendering component: {str(e)}")
            
            # Show more details if debug mode is enabled
            if st.session_state.get("debug_mode", False):
                with st.expander("Error Details"):
                    st.exception(e)
    
    return cast(F, wrapper)

def toggle_debug_mode():
    """Toggle debug mode state."""
    current = st.session_state.get("debug_mode", False)
    st.session_state.debug_mode = not current
    if not current:
        st.info("Debug mode enabled. Additional error information will be shown.")

def create_debug_section():
    """Create a collapsible debug section with state information."""
    import pandas as pd
    from ktrdr.ui.utils.session import get_state_data
    
    with st.expander("🛠️ Debug Information", expanded=False):
        # Add a debug mode toggle
        if st.toggle("Debug Mode", value=st.session_state.get("debug_mode", False), key="debug_toggle"):
            if not st.session_state.get("debug_mode", False):
                st.session_state.debug_mode = True
                st.info("Debug mode enabled")
        else:
            if st.session_state.get("debug_mode", True):
                st.session_state.debug_mode = False
        
        # Display current state information
        st.subheader("Session State")
        state_data = get_state_data()
        st.dataframe(pd.DataFrame([state_data]).T.rename(columns={0: "Value"}))

        # Add indicator info if available
        if st.session_state.get("indicators"):
            st.subheader("Indicators")
            indicators = st.session_state.indicators
            st.write(indicators)
            
        # Data shape info
        if st.session_state.get("data") is not None:
            data = st.session_state.data
            st.subheader("Data Info")
            st.write(f"Shape: {data.shape}, Columns: {list(data.columns)}")