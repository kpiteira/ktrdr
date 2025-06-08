"""
Unit tests for trading hours functionality.
"""

import unittest
from datetime import time
import pandas as pd

from ktrdr.data.trading_hours import TradingHoursManager, TradingHours, TradingSession


class TestTradingHours(unittest.TestCase):
    """Test trading hours management functionality."""
    
    def test_get_trading_hours_nasdaq(self):
        """Test getting NASDAQ trading hours."""
        hours = TradingHoursManager.get_trading_hours("NASDAQ", "STK")
        
        self.assertIsNotNone(hours)
        self.assertEqual(hours.timezone, "America/New_York")
        self.assertEqual(hours.regular_hours.start, time(9, 30))
        self.assertEqual(hours.regular_hours.end, time(16, 0))
        self.assertEqual(len(hours.extended_hours), 2)
        self.assertEqual(hours.trading_days, [0, 1, 2, 3, 4])  # Monday-Friday
    
    def test_get_trading_hours_forex(self):
        """Test getting FOREX trading hours."""
        hours = TradingHoursManager.get_trading_hours("IDEALPRO", "CASH")
        
        self.assertIsNotNone(hours)
        self.assertEqual(hours.timezone, "UTC")
        self.assertEqual(hours.regular_hours.name, "24H")
        self.assertEqual(hours.trading_days, [0, 1, 2, 3, 4, 6])  # Monday-Friday + Sunday
    
    def test_get_trading_hours_unknown(self):
        """Test getting trading hours for unknown exchange."""
        hours = TradingHoursManager.get_trading_hours("UNKNOWN", "STK")
        self.assertIsNone(hours)
    
    def test_is_market_open_us_stocks(self):
        """Test market open detection for US stocks."""
        # Friday 10:30 AM ET (14:30 UTC) - should be open
        timestamp = pd.Timestamp('2025-06-06T14:30:00Z')
        is_open = TradingHoursManager.is_market_open(timestamp, "NASDAQ", "STK")
        self.assertTrue(is_open)
        
        # Friday 5:30 PM ET (21:30 UTC) - should be closed
        timestamp = pd.Timestamp('2025-06-06T21:30:00Z')
        is_open = TradingHoursManager.is_market_open(timestamp, "NASDAQ", "STK")
        self.assertFalse(is_open)
        
        # Saturday - should be closed
        timestamp = pd.Timestamp('2025-06-07T14:30:00Z')
        is_open = TradingHoursManager.is_market_open(timestamp, "NASDAQ", "STK")
        self.assertFalse(is_open)
    
    def test_is_market_open_extended_hours(self):
        """Test market open detection including extended hours."""
        # Friday 5:30 PM ET (21:30 UTC) - after hours
        timestamp = pd.Timestamp('2025-06-06T21:30:00Z')
        
        # Should be closed for regular hours
        is_open_regular = TradingHoursManager.is_market_open(timestamp, "NASDAQ", "STK", include_extended=False)
        self.assertFalse(is_open_regular)
        
        # Should be open for extended hours
        is_open_extended = TradingHoursManager.is_market_open(timestamp, "NASDAQ", "STK", include_extended=True)
        self.assertTrue(is_open_extended)
    
    def test_is_market_open_forex(self):
        """Test market open detection for FOREX."""
        # Friday 2:30 AM UTC - should be open for FOREX
        timestamp = pd.Timestamp('2025-06-06T02:30:00Z')
        is_open = TradingHoursManager.is_market_open(timestamp, "IDEALPRO", "CASH")
        self.assertTrue(is_open)
        
        # Saturday - should be closed even for FOREX
        timestamp = pd.Timestamp('2025-06-07T14:30:00Z')
        is_open = TradingHoursManager.is_market_open(timestamp, "IDEALPRO", "CASH")
        self.assertFalse(is_open)
    
    def test_get_market_status(self):
        """Test market status detection."""
        # Friday 10:30 AM ET - market open
        timestamp = pd.Timestamp('2025-06-06T14:30:00Z')
        status = TradingHoursManager.get_market_status(timestamp, "NASDAQ", "STK")
        self.assertEqual(status, "Open")
        
        # Friday 5:30 PM ET - after hours
        timestamp = pd.Timestamp('2025-06-06T21:30:00Z')
        status = TradingHoursManager.get_market_status(timestamp, "NASDAQ", "STK")
        self.assertEqual(status, "After-Hours")
        
        # Saturday - closed
        timestamp = pd.Timestamp('2025-06-07T14:30:00Z')
        status = TradingHoursManager.get_market_status(timestamp, "NASDAQ", "STK")
        self.assertEqual(status, "Closed")
    
    def test_to_dict_serialization(self):
        """Test trading hours serialization to dictionary."""
        hours = TradingHoursManager.get_trading_hours("NASDAQ", "STK")
        hours_dict = TradingHoursManager.to_dict(hours)
        
        self.assertIsInstance(hours_dict, dict)
        self.assertIn("timezone", hours_dict)
        self.assertIn("regular_hours", hours_dict)
        self.assertIn("extended_hours", hours_dict)
        self.assertIn("trading_days", hours_dict)
        
        # Check regular hours format
        regular = hours_dict["regular_hours"]
        self.assertEqual(regular["start"], "09:30")
        self.assertEqual(regular["end"], "16:00")
        self.assertEqual(regular["name"], "Regular")
        
        # Check extended hours format
        extended = hours_dict["extended_hours"]
        self.assertEqual(len(extended), 2)
        self.assertEqual(extended[0]["name"], "Pre-Market")
        self.assertEqual(extended[1]["name"], "After-Hours")
    
    def test_time_session_crossing_midnight(self):
        """Test trading sessions that cross midnight."""
        # Create a test session that crosses midnight
        session = TradingSession(time(22, 0), time(6, 0), "Overnight")
        
        # Test time within session (11 PM)
        current_time = time(23, 0)
        is_in_session = TradingHoursManager._is_time_in_session(current_time, session)
        self.assertTrue(is_in_session)
        
        # Test time within session (3 AM)
        current_time = time(3, 0)
        is_in_session = TradingHoursManager._is_time_in_session(current_time, session)
        self.assertTrue(is_in_session)
        
        # Test time outside session (8 AM)
        current_time = time(8, 0)
        is_in_session = TradingHoursManager._is_time_in_session(current_time, session)
        self.assertFalse(is_in_session)


if __name__ == '__main__':
    unittest.main()