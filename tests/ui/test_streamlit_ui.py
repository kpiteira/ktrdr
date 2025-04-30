"""
Tests for the Streamlit UI scaffold.

This module contains basic unit tests for the Streamlit UI module.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import pandas as pd
from pathlib import Path

# Make sure the project root is in the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import streamlit as st
from ktrdr.ui.main import (
    initialize_session_state,
    render_sidebar,
    load_data,
    compute_indicators,
    run_app
)


class TestStreamlitUI(unittest.TestCase):
    """Tests for the Streamlit UI scaffold."""

    @patch('ktrdr.ui.main.st')
    def test_initialize_session_state(self, mock_st):
        """Test session state initialization."""
        # Setup mock session state
        mock_st.session_state = {}
        
        # Call the function
        initialize_session_state()
        
        # Verify that all required keys were added
        self.assertIn('data', mock_st.session_state)
        self.assertIn('symbol', mock_st.session_state)
        self.assertIn('timeframe', mock_st.session_state)
        self.assertIn('indicators', mock_st.session_state)
        self.assertIn('fuzzy_sets', mock_st.session_state)
        self.assertIn('chart', mock_st.session_state)
        self.assertIn('theme', mock_st.session_state)
        self.assertEqual(mock_st.session_state.theme, 'dark')
    
    @patch('ktrdr.ui.main.st')
    @patch('ktrdr.ui.main.Path')
    def test_render_sidebar(self, mock_path, mock_st):
        """Test sidebar rendering."""
        # Setup mocks
        mock_st.sidebar = MagicMock()
        mock_st.session_state = {'theme': 'dark', 'active_tab': 'Data'}
        mock_sidebar_selectbox = mock_st.sidebar.selectbox
        mock_sidebar_selectbox.return_value = "AAPL"
        
        # Setup mock path for data files
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True
        mock_path_instance.glob.return_value = [Path("data/AAPL_1d.csv"), Path("data/MSFT_1h.csv")]
        
        # Call the function
        config = render_sidebar()
        
        # Verify that sidebar elements were created
        mock_st.sidebar.title.assert_called_with("KTRDR Configuration")
        mock_st.sidebar.header.assert_called()
        mock_sidebar_selectbox.assert_called()
        
        # Verify config contains expected keys
        self.assertIn('symbol', config)
        self.assertIn('timeframe', config)
        self.assertIn('theme', config)
    
    @patch('ktrdr.ui.main.st')
    @patch('ktrdr.ui.main.DataManager')
    def test_load_data(self, mock_data_manager, mock_st):
        """Test data loading function."""
        # Setup mocks
        mock_st.session_state = {}
        mock_st.spinner = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        
        mock_data_manager_instance = MagicMock()
        mock_data_manager.return_value = mock_data_manager_instance
        
        # Create a sample DataFrame
        df = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=10),
            'open': [100.0] * 10,
            'high': [105.0] * 10,
            'low': [95.0] * 10,
            'close': [102.0] * 10,
            'volume': [1000] * 10
        })
        mock_data_manager_instance.load.return_value = df
        
        # Call the function
        load_data('AAPL', '1d', 30)
        
        # Verify DataManager.load was called with correct parameters
        mock_data_manager_instance.load.assert_called_once_with(
            symbol='AAPL',
            interval='1d',
            days=30
        )
        
        # Verify the data was stored in session state
        self.assertEqual(mock_st.session_state.data.equals(df), True)
        self.assertEqual(mock_st.session_state.symbol, 'AAPL')
        self.assertEqual(mock_st.session_state.timeframe, '1d')
        
        # Verify success message was displayed
        mock_st.success.assert_called()
    
    @patch('ktrdr.ui.main.st')
    @patch('ktrdr.ui.main.IndicatorEngine')
    def test_compute_indicators(self, mock_indicator_engine, mock_st):
        """Test indicator computation function."""
        # Setup mocks
        mock_st.session_state = {'indicators': {}}
        mock_st.spinner = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
        
        mock_engine_instance = MagicMock()
        mock_indicator_engine.return_value = mock_engine_instance
        
        # Create sample input and output DataFrames
        df_input = pd.DataFrame({
            'date': pd.date_range(start='2023-01-01', periods=10),
            'close': [100.0] * 10
        })
        
        df_output = df_input.copy()
        df_output['RSI_14'] = [50.0] * 10
        
        mock_engine_instance.compute_rsi.return_value = df_output
        
        # Call the function
        result = compute_indicators(df_input, ['RSI'], {'rsi_period': 14})
        
        # Verify indicator engine methods were called correctly
        mock_engine_instance.compute_rsi.assert_called_once()
        
        # Verify the indicators were stored in session state
        self.assertIn('RSI', mock_st.session_state.indicators)
        self.assertEqual(mock_st.session_state.indicators['RSI']['period'], 14)
        
        # Verify the function returned the transformed DataFrame
        self.assertEqual(result.equals(df_output), True)
    
    @patch('ktrdr.ui.main.st')
    def test_run_app(self, mock_st):
        """Test the main app entry point."""
        # Setup mocks
        mock_st.set_page_config = MagicMock()
        mock_st.title = MagicMock()
        mock_st.tabs = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
        mock_st.session_state = {}
        
        # Call the function with mocked methods
        with patch('ktrdr.ui.main.initialize_session_state') as mock_init:
            with patch('ktrdr.ui.main.render_sidebar') as mock_sidebar:
                with patch('ktrdr.ui.main.render_data_tab') as mock_data_tab:
                    with patch('ktrdr.ui.main.render_indicators_tab') as mock_indicators_tab:
                        with patch('ktrdr.ui.main.render_fuzzy_tab') as mock_fuzzy_tab:
                            # Configure mock_sidebar to return empty config
                            mock_sidebar.return_value = {'theme': 'dark', 'load_data': False}
                            
                            # Call run_app
                            run_app()
                            
                            # Verify the page was configured
                            mock_st.set_page_config.assert_called_once()
                            mock_st.title.assert_called_once()
                            
                            # Verify tab rendering functions were called
                            mock_init.assert_called_once()
                            mock_sidebar.assert_called_once()
                            mock_data_tab.assert_called_once()
                            mock_indicators_tab.assert_called_once()
                            mock_fuzzy_tab.assert_called_once()


if __name__ == '__main__':
    unittest.main()