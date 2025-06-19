"""
Unit tests for IB trading hours parser.
"""

import unittest
from datetime import time
from unittest.mock import Mock

from ktrdr.ib.trading_hours_parser import IBTradingHoursParser, IBTradingHoursInfo


class TestIBTradingHoursParser(unittest.TestCase):
    """Test IB trading hours parsing functionality."""

    def test_parse_time_string(self):
        """Test parsing HHMM time strings."""
        # Valid times
        self.assertEqual(IBTradingHoursParser._parse_time_string("0930"), time(9, 30))
        self.assertEqual(IBTradingHoursParser._parse_time_string("1600"), time(16, 0))
        self.assertEqual(IBTradingHoursParser._parse_time_string("0000"), time(0, 0))
        self.assertEqual(IBTradingHoursParser._parse_time_string("2359"), time(23, 59))

        # Invalid times
        self.assertIsNone(IBTradingHoursParser._parse_time_string("25:00"))
        self.assertIsNone(IBTradingHoursParser._parse_time_string("abc"))
        self.assertIsNone(IBTradingHoursParser._parse_time_string(""))
        self.assertIsNone(IBTradingHoursParser._parse_time_string("123"))  # Too short

    def test_parse_hours_string_single_session(self):
        """Test parsing single session hours string."""
        hours_str = "20161201:0930-20161201:1600"
        sessions = IBTradingHoursParser._parse_hours_string(hours_str)

        self.assertEqual(len(sessions), 1)
        start_time, end_time = sessions[0]
        self.assertEqual(start_time, time(9, 30))
        self.assertEqual(end_time, time(16, 0))

    def test_parse_hours_string_multiple_sessions(self):
        """Test parsing multiple session hours string."""
        hours_str = "20161201:0400-20161201:0930;20161201:0930-20161201:1600;20161201:1600-20161201:2000"
        sessions = IBTradingHoursParser._parse_hours_string(hours_str)

        self.assertEqual(len(sessions), 3)

        # Pre-market session
        self.assertEqual(sessions[0], (time(4, 0), time(9, 30)))

        # Regular session
        self.assertEqual(sessions[1], (time(9, 30), time(16, 0)))

        # After-hours session
        self.assertEqual(sessions[2], (time(16, 0), time(20, 0)))

    def test_parse_hours_string_closed(self):
        """Test parsing closed market hours."""
        sessions = IBTradingHoursParser._parse_hours_string("CLOSED")
        self.assertEqual(len(sessions), 0)

        sessions = IBTradingHoursParser._parse_hours_string("")
        self.assertEqual(len(sessions), 0)

    def test_map_timezone(self):
        """Test timezone mapping."""
        # Known mappings
        self.assertEqual(
            IBTradingHoursParser._map_timezone("US/Eastern"), "America/New_York"
        )
        self.assertEqual(IBTradingHoursParser._map_timezone("UTC"), "UTC")
        self.assertEqual(
            IBTradingHoursParser._map_timezone("Europe/London"), "Europe/London"
        )

        # Unknown timezone (should return as-is)
        self.assertEqual(
            IBTradingHoursParser._map_timezone("Unknown/Timezone"), "Unknown/Timezone"
        )

    def test_extract_regular_hours(self):
        """Test extracting regular hours from sessions."""
        sessions = [(time(9, 30), time(16, 0))]
        regular = IBTradingHoursParser._extract_regular_hours(sessions)

        self.assertEqual(regular.start, time(9, 30))
        self.assertEqual(regular.end, time(16, 0))
        self.assertEqual(regular.name, "Regular")

    def test_extract_extended_hours(self):
        """Test extracting extended hours."""
        # All sessions include pre-market and after-hours
        all_sessions = [
            (time(4, 0), time(9, 30)),  # Pre-market
            (time(9, 30), time(16, 0)),  # Regular
            (time(16, 0), time(20, 0)),  # After-hours
        ]

        # Regular sessions (liquid hours)
        regular_sessions = [(time(9, 30), time(16, 0))]

        extended = IBTradingHoursParser._extract_extended_hours(
            all_sessions, regular_sessions
        )

        # Should find pre-market and after-hours
        self.assertEqual(len(extended), 2)

        # Check pre-market
        pre_market = next((s for s in extended if s.name == "Pre-Market"), None)
        self.assertIsNotNone(pre_market)
        self.assertEqual(pre_market.start, time(4, 0))
        self.assertEqual(pre_market.end, time(9, 30))

        # Check after-hours
        after_hours = next((s for s in extended if s.name == "After-Hours"), None)
        self.assertIsNotNone(after_hours)
        self.assertEqual(after_hours.start, time(16, 0))
        self.assertEqual(after_hours.end, time(20, 0))

    def test_parse_ib_trading_hours_us_stocks(self):
        """Test parsing US stock trading hours."""
        ib_info = IBTradingHoursInfo(
            timezone_id="US/Eastern",
            trading_hours="20161201:0400-20161201:2000",
            liquid_hours="20161201:0930-20161201:1600",
        )

        trading_hours = IBTradingHoursParser.parse_ib_trading_hours(ib_info)

        self.assertIsNotNone(trading_hours)
        self.assertEqual(trading_hours.timezone, "America/New_York")

        # Regular hours should be from liquid hours
        self.assertEqual(trading_hours.regular_hours.start, time(9, 30))
        self.assertEqual(trading_hours.regular_hours.end, time(16, 0))

        # Should have trading days Monday-Friday
        self.assertEqual(trading_hours.trading_days, [0, 1, 2, 3, 4])

    def test_parse_ib_trading_hours_forex(self):
        """Test parsing FOREX trading hours."""
        ib_info = IBTradingHoursInfo(
            timezone_id="UTC",
            trading_hours="20161204:2200-20161209:2200",  # Sunday 22:00 to Friday 22:00
            liquid_hours="20161204:2200-20161209:2200",
        )

        trading_hours = IBTradingHoursParser.parse_ib_trading_hours(ib_info)

        self.assertIsNotNone(trading_hours)
        self.assertEqual(trading_hours.timezone, "UTC")

        # FOREX regular hours (24/5)
        self.assertEqual(trading_hours.regular_hours.start, time(22, 0))
        self.assertEqual(trading_hours.regular_hours.end, time(22, 0))

    def test_parse_ib_trading_hours_invalid_timezone(self):
        """Test parsing with invalid timezone."""
        ib_info = IBTradingHoursInfo(
            timezone_id="Invalid/Timezone",
            trading_hours="20161201:0930-20161201:1600",
            liquid_hours="20161201:0930-20161201:1600",
        )

        # Should still work, using the timezone as-is
        trading_hours = IBTradingHoursParser.parse_ib_trading_hours(ib_info)
        self.assertIsNotNone(trading_hours)
        self.assertEqual(trading_hours.timezone, "Invalid/Timezone")

    def test_parse_ib_trading_hours_closed_market(self):
        """Test parsing closed market."""
        ib_info = IBTradingHoursInfo(
            timezone_id="US/Eastern", trading_hours="CLOSED", liquid_hours="CLOSED"
        )

        trading_hours = IBTradingHoursParser.parse_ib_trading_hours(ib_info)

        # Should handle gracefully but may return None or default hours
        # Implementation can decide how to handle this
        if trading_hours:
            self.assertEqual(trading_hours.timezone, "America/New_York")

    def test_create_from_contract_details(self):
        """Test creating trading hours from contract details."""
        # Mock contract details
        contract_details = Mock()
        contract_details.timeZoneId = "US/Eastern"
        contract_details.tradingHours = "20161201:0400-20161201:2000"
        contract_details.liquidHours = "20161201:0930-20161201:1600"

        trading_hours = IBTradingHoursParser.create_from_contract_details(
            contract_details
        )

        self.assertIsNotNone(trading_hours)
        self.assertEqual(trading_hours.timezone, "America/New_York")
        self.assertEqual(trading_hours.regular_hours.start, time(9, 30))
        self.assertEqual(trading_hours.regular_hours.end, time(16, 0))

    def test_create_from_contract_details_missing_fields(self):
        """Test creating trading hours with missing fields."""
        # Mock contract details with missing fields
        contract_details = Mock()
        contract_details.timeZoneId = "US/Eastern"
        # Missing tradingHours and liquidHours

        trading_hours = IBTradingHoursParser.create_from_contract_details(
            contract_details
        )

        # Should handle gracefully
        # May return None or default depending on implementation
        if trading_hours is None:
            # This is acceptable behavior
            pass
        else:
            # If it returns something, it should be valid
            self.assertEqual(trading_hours.timezone, "America/New_York")


if __name__ == "__main__":
    unittest.main()
