"""
Fuzzy Logic tab for the KTRDR Streamlit UI.

This module provides the Fuzzy Logic tab UI components and functionality.
"""
import streamlit as st
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

from ktrdr import get_logger
from ktrdr.fuzzy import FuzzyConfigLoader, FuzzyEngine
from ktrdr.ui.utils.ui_helpers import safe_render
from ktrdr.ui.utils.session import update_data

# Create module-level logger
logger = get_logger(__name__)

@safe_render
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
    
    # Display the current fuzzy strategy
    fuzzy_strategy = st.session_state.get("fuzzy_strategy")
    if fuzzy_strategy:
        st.write(f"Current Fuzzy Strategy: **{fuzzy_strategy}**")
    
        # Display fuzzy sets information
        with st.expander("Fuzzy Sets Configuration", expanded=True):
            for indicator, fuzzy_sets in st.session_state.fuzzy_sets.items():
                st.subheader(f"Indicator: {indicator}")
                
                # Display each fuzzy set
                for set_name, set_info in fuzzy_sets.items():
                    st.write(f"**{set_name}**: {set_info}")
    
    # Placeholder for future visualization of fuzzy sets
    st.info("Enhanced fuzzy visualization components will be implemented in Task 5.3.")

def apply_fuzzy_logic(data, strategy):
    """Apply fuzzy logic strategy to the data.
    
    Args:
        data: The price data DataFrame.
        strategy: The fuzzy logic strategy to apply.
    """
    try:
        with st.spinner(f"Applying fuzzy logic strategy: {strategy}..."):
            # Create a proper FuzzyConfigLoader instance
            config_loader = FuzzyConfigLoader(config_dir=Path("config"))
            
            # Load the fuzzy configuration for the selected strategy
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
                indicator_cols = [col for col in data.columns if col.lower().startswith(indicator.lower())]
                
                if not indicator_cols:
                    logger.warning(f"No columns found for indicator {indicator}")
                    continue
                
                if indicator_cols:
                    try:
                        # Get the first matching column for now
                        indicator_col = indicator_cols[0]
                        
                        # Apply fuzzy membership functions
                        fuzzy_membership = engine.apply_fuzzy_membership(
                            data=data,
                            indicator=indicator,
                            strategy=strategy,
                            column=indicator_col
                        )
                        
                        if fuzzy_membership is not None:
                            # Store fuzzy membership results
                            fuzzy_results[indicator] = fuzzy_membership
                            
                            # Add fuzzy membership columns to dataframe
                            for set_name, membership_values in fuzzy_membership.items():
                                col_name = f"{indicator}_{set_name}_membership"
                                data[col_name] = membership_values
                    except Exception as ind_err:
                        logger.error(f"Error applying fuzzy logic to {indicator}: {str(ind_err)}")
            
            # Store fuzzy sets in session state
            st.session_state.fuzzy_sets = fuzzy_results
            st.session_state.fuzzy_strategy = strategy
            
            # Store updated data in session state
            update_data(data)
            
            logger.info(f"Applied fuzzy strategy with {len(fuzzy_results)} indicators")
            
            # Update success message
            st.success(f"Successfully applied fuzzy strategy: {strategy}")
            
    except Exception as e:
        logger.error(f"Error applying fuzzy logic: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Failed to apply fuzzy logic: {str(e)}")
        st.session_state.fuzzy_sets = {}