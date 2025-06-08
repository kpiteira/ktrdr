"""
Unit tests for enhanced timezone utilities with trading hours integration.
"""

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pandas as pd

from ktrdr.utils.timezone_utils import TimestampManager


class TestTimestampManagerEnhanced(unittest.TestCase):
    """Test enhanced TimestampManager functionality with trading hours."""
    
    def setUp(self):
        """Set up test data."""
        self.mock_cache_data = {
            "cache": {
                "MSFT": {
                    "symbol": "MSFT",
                    "asset_type": "STK",
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "description": "MICROSOFT CORP",
                    "validated_at": 1633024800.0,
                    "trading_hours": {
                        "timezone": "America/New_York",
                        "regular_hours": {
                            "start": "09:30",
                            "end": "16:00",
                            "name": "Regular"
                        },
                        "extended_hours": [
                            {
                                "start": "04:00",
                                "end": "09:30",
                                "name": "Pre-Market"
                            },
                            {
                                "start": "16:00",
                                "end": "20:00",
                                "name": "After-Hours"
                            }
                        ],
                        "trading_days": [0, 1, 2, 3, 4],
                        "holidays": []
                    }
                },
                "EURUSD": {
                    "symbol": "EURUSD",
                    "asset_type": "CASH",
                    "exchange": "IDEALPRO",
                    "currency": "USD",
                    "description": "European Monetary Union Euro",
                    "validated_at": 1633024800.0,
                    "trading_hours": {
                        "timezone": "UTC",
                        "regular_hours": {
                            "start": "22:00",
                            "end": "21:59",
                            "name": "24H"
                        },
                        "extended_hours": [],
                        "trading_days": [0, 1, 2, 3, 4, 6],
                        "holidays": []
                    }
                }
            },
            "failed_symbols": [],
            "validated_symbols": ["MSFT", "EURUSD"],
            "last_updated": 1633024800.0
        }
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_get_symbol_trading_hours_success(self, mock_exists, mock_file):
        """Test successful retrieval of symbol trading hours."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.mock_cache_data)
        
        # Test MSFT
        result = TimestampManager._get_symbol_trading_hours("MSFT")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["exchange"], "NASDAQ")
        self.assertEqual(result["asset_type"], "STK")
        self.assertIsNotNone(result["trading_hours"])
        self.assertEqual(result["trading_hours"]["timezone"], "America/New_York")
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_get_symbol_trading_hours_not_found(self, mock_exists, mock_file):
        """Test retrieval when symbol not found."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.mock_cache_data)
        
        result = TimestampManager._get_symbol_trading_hours("UNKNOWN")
        self.assertIsNone(result)
    
    @patch('pathlib.Path.exists')
    def test_get_symbol_trading_hours_no_cache(self, mock_exists):
        """Test retrieval when cache file doesn't exist."""
        mock_exists.return_value = False
        
        result = TimestampManager._get_symbol_trading_hours("MSFT")
        self.assertIsNone(result)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_is_market_hours_enhanced_with_symbol(self, mock_exists, mock_file):
        """Test enhanced market hours check with symbol-specific hours."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.mock_cache_data)
        
        # Friday 10:30 AM ET (14:30 UTC) - should be open for MSFT
        timestamp = pd.Timestamp('2025-06-06T14:30:00Z')
        
        with patch('ktrdr.data.trading_hours.TradingHoursManager.is_market_open') as mock_is_open:
            mock_is_open.return_value = True
            
            result = TimestampManager.is_market_hours_enhanced(timestamp, "MSFT")
            
            self.assertTrue(result)
            mock_is_open.assert_called_once_with(timestamp, "NASDAQ", "STK")
    
    def test_is_market_hours_enhanced_fallback(self):
        """Test enhanced market hours check falls back to basic method."""
        # Friday 10:30 AM ET (14:30 UTC)
        timestamp = pd.Timestamp('2025-06-06T14:30:00Z')
        
        # Should fall back to basic method when no symbol provided
        with patch.object(TimestampManager, 'is_market_hours') as mock_basic:
            mock_basic.return_value = True
            
            result = TimestampManager.is_market_hours_enhanced(timestamp)
            
            self.assertTrue(result)
            mock_basic.assert_called_once_with(timestamp, 'America/New_York')
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_get_market_status_enhanced_with_symbol(self, mock_exists, mock_file):
        """Test enhanced market status check with symbol-specific hours."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.mock_cache_data)
        
        timestamp = pd.Timestamp('2025-06-06T14:30:00Z')
        
        with patch('ktrdr.data.trading_hours.TradingHoursManager.get_market_status') as mock_status:
            mock_status.return_value = "Open"
            
            result = TimestampManager.get_market_status_enhanced(timestamp, "MSFT")
            
            self.assertEqual(result, "Open")
            mock_status.assert_called_once_with(timestamp, "NASDAQ", "STK")
    
    def test_get_market_status_enhanced_fallback(self):
        """Test enhanced market status check falls back to basic method."""
        timestamp = pd.Timestamp('2025-06-06T14:30:00Z')
        
        with patch.object(TimestampManager, 'get_trading_session') as mock_session:
            mock_session.return_value = "regular"
            
            result = TimestampManager.get_market_status_enhanced(timestamp)
            
            self.assertEqual(result, "regular")
            mock_session.assert_called_once_with(timestamp)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_forex_trading_hours_integration(self, mock_exists, mock_file):
        """Test FOREX trading hours integration."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.mock_cache_data)
        
        # Friday 2:30 AM UTC - should be open for FOREX
        timestamp = pd.Timestamp('2025-06-06T02:30:00Z')
        
        with patch('ktrdr.data.trading_hours.TradingHoursManager.is_market_open') as mock_is_open:
            mock_is_open.return_value = True
            
            result = TimestampManager.is_market_hours_enhanced(timestamp, "EURUSD")
            
            self.assertTrue(result)
            mock_is_open.assert_called_once_with(timestamp, "IDEALPRO", "CASH")
    
    def test_error_handling_in_enhanced_methods(self):
        """Test error handling in enhanced methods."""
        timestamp = pd.Timestamp('2025-06-06T14:30:00Z')
        
        # Test when symbol lookup raises exception
        with patch.object(TimestampManager, '_get_symbol_trading_hours') as mock_get:
            mock_get.side_effect = Exception("Test error")
            
            # Should fall back gracefully
            result = TimestampManager.is_market_hours_enhanced(timestamp, "MSFT")
            
            # Should use fallback method
            self.assertIsInstance(result, bool)
    
    def test_backwards_compatibility(self):
        """Test that enhanced methods don't break existing functionality."""
        timestamp = pd.Timestamp('2025-06-06T14:30:00Z')
        
        # Basic methods should still work
        basic_result = TimestampManager.is_market_hours(timestamp)
        enhanced_result = TimestampManager.is_market_hours_enhanced(timestamp)
        
        # Should give same result when no symbol provided
        self.assertEqual(basic_result, enhanced_result)


if __name__ == '__main__':
    unittest.main()