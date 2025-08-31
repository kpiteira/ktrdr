"""
Tests for the enhanced gap classification system.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from ktrdr.data.components.gap_classifier import (
    GapClassification,
    GapClassifier,
    GapInfo,
)


class TestGapClassifier:
    """Test suite for the GapClassifier."""

    @pytest.fixture
    def mock_symbol_cache(self, tmp_path):
        """Create a mock symbol cache file."""
        cache_data = {
            "cache": {
                "EURUSD": {
                    "symbol": "EURUSD",
                    "asset_type": "CASH",
                    "exchange": "IDEALPRO",
                    "trading_hours": {
                        "timezone": "UTC",
                        "regular_hours": {
                            "start": "22:00",
                            "end": "21:59",
                            "name": "24H",
                        },
                        "extended_hours": [],
                        "trading_days": [0, 1, 2, 3, 4, 6],  # Mon-Fri + Sunday
                    },
                },
                "AAPL": {
                    "symbol": "AAPL",
                    "asset_type": "STK",
                    "exchange": "NASDAQ",
                    "trading_hours": {
                        "timezone": "America/New_York",
                        "regular_hours": {
                            "start": "09:30",
                            "end": "16:00",
                            "name": "Regular",
                        },
                        "extended_hours": [
                            {"start": "04:00", "end": "09:30", "name": "Pre-Market"}
                        ],
                        "trading_days": [0, 1, 2, 3, 4],  # Mon-Fri
                    },
                },
            }
        }

        cache_file = tmp_path / "symbol_cache.json"
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        return str(cache_file)

    @pytest.fixture
    def gap_classifier(self, mock_symbol_cache):
        """Create a gap classifier with mock data."""
        return GapClassifier(symbol_cache_path=mock_symbol_cache)

    def test_weekend_gap_classification(self, gap_classifier):
        """Test classification of weekend gaps for daily data."""
        # Create a gap that spans Saturday-Sunday (weekend)
        start_time = datetime(2024, 1, 5, 16, 0, tzinfo=timezone.utc)  # Friday 4 PM UTC
        end_time = datetime(
            2024, 1, 8, 9, 30, tzinfo=timezone.utc
        )  # Monday 9:30 AM UTC

        classification = gap_classifier.classify_gap(
            start_time=start_time, end_time=end_time, symbol="AAPL", timeframe="1d"
        )

        assert classification == GapClassification.EXPECTED_WEEKEND

    def test_trading_hours_gap_classification(self, gap_classifier):
        """Test classification of gaps outside trading hours for intraday data."""
        # Create a gap during non-trading hours (after market close but not into weekend)
        start_time = datetime(
            2024, 1, 11, 22, 0, tzinfo=timezone.utc
        )  # Thursday 10 PM UTC (5 PM EST)
        end_time = datetime(
            2024, 1, 12, 2, 0, tzinfo=timezone.utc
        )  # Friday 2 AM UTC (9 PM EST Thursday)

        classification = gap_classifier.classify_gap(
            start_time=start_time, end_time=end_time, symbol="AAPL", timeframe="1h"
        )

        assert classification == GapClassification.EXPECTED_TRADING_HOURS

    def test_holiday_gap_classification(self, gap_classifier):
        """Test classification of holiday gaps (adjacent to weekends)."""
        # Create a gap on Monday (potential holiday after weekend)
        start_time = datetime(
            2024, 1, 15, 9, 30, tzinfo=timezone.utc
        )  # Monday 9:30 AM UTC
        end_time = datetime(2024, 1, 15, 21, 0, tzinfo=timezone.utc)  # Monday 9 PM UTC

        classification = gap_classifier.classify_gap(
            start_time=start_time, end_time=end_time, symbol="AAPL", timeframe="1d"
        )

        assert classification == GapClassification.EXPECTED_HOLIDAY

    def test_unexpected_gap_classification(self, gap_classifier):
        """Test classification of unexpected gaps during trading hours."""
        # Create a gap during regular trading hours on Wednesday
        start_time = datetime(
            2024, 1, 10, 14, 0, tzinfo=timezone.utc
        )  # Wednesday 2 PM UTC (9 AM EST)
        end_time = datetime(
            2024, 1, 10, 16, 0, tzinfo=timezone.utc
        )  # Wednesday 4 PM UTC (11 AM EST)

        classification = gap_classifier.classify_gap(
            start_time=start_time, end_time=end_time, symbol="AAPL", timeframe="1h"
        )

        assert classification == GapClassification.UNEXPECTED

    def test_market_closure_classification(self, gap_classifier):
        """Test classification of extended market closures."""
        # Create a gap longer than 3 days during a non-holiday period
        start_time = datetime(
            2024, 6, 10, 9, 30, tzinfo=timezone.utc
        )  # Monday in June (no holidays)
        end_time = datetime(
            2024, 6, 14, 9, 30, tzinfo=timezone.utc
        )  # Friday - 4 days later

        classification = gap_classifier.classify_gap(
            start_time=start_time, end_time=end_time, symbol="AAPL", timeframe="1d"
        )

        assert classification == GapClassification.MARKET_CLOSURE

    def test_forex_24_5_classification(self, gap_classifier):
        """Test classification for forex markets with 24/5 trading."""
        # Create a gap during the weekend for forex
        start_time = datetime(
            2024, 1, 5, 22, 0, tzinfo=timezone.utc
        )  # Friday 10 PM UTC
        end_time = datetime(2024, 1, 7, 22, 0, tzinfo=timezone.utc)  # Sunday 10 PM UTC

        classification = gap_classifier.classify_gap(
            start_time=start_time, end_time=end_time, symbol="EURUSD", timeframe="1d"
        )

        assert classification == GapClassification.EXPECTED_WEEKEND

    def test_analyze_gap_comprehensive(self, gap_classifier):
        """Test comprehensive gap analysis."""
        start_time = datetime(2024, 1, 6, 10, 0, tzinfo=timezone.utc)  # Saturday
        end_time = datetime(2024, 1, 7, 10, 0, tzinfo=timezone.utc)  # Sunday

        gap_info = gap_classifier.analyze_gap(
            start_time=start_time, end_time=end_time, symbol="AAPL", timeframe="1d"
        )

        assert isinstance(gap_info, GapInfo)
        assert gap_info.classification == GapClassification.EXPECTED_WEEKEND
        assert gap_info.bars_missing >= 1
        assert gap_info.duration_hours == 24.0
        assert "Saturday" in gap_info.day_context
        assert gap_info.symbol == "AAPL"
        assert gap_info.timeframe == "1d"
        assert "Weekend gap" in gap_info.note

    def test_is_gap_worth_filling(self, gap_classifier):
        """Test gap filling priority logic."""
        # Create different types of gaps
        unexpected_gap = GapInfo(
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=2),
            classification=GapClassification.UNEXPECTED,
            bars_missing=2,
            duration_hours=2.0,
            day_context="Wednesday",
            symbol="AAPL",
            timeframe="1h",
        )

        weekend_gap = GapInfo(
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(days=2),
            classification=GapClassification.EXPECTED_WEEKEND,
            bars_missing=1,
            duration_hours=48.0,
            day_context="Saturday-Sunday",
            symbol="AAPL",
            timeframe="1d",
        )

        # Unexpected gaps should be filled
        assert gap_classifier.is_gap_worth_filling(unexpected_gap)

        # Weekend gaps should not be filled by default
        assert not gap_classifier.is_gap_worth_filling(weekend_gap)

        # Weekend gaps should be filled if threshold is lowered
        assert gap_classifier.is_gap_worth_filling(
            weekend_gap, priority_threshold=GapClassification.EXPECTED_WEEKEND
        )

    def test_missing_symbol_metadata(self, gap_classifier):
        """Test behavior when symbol metadata is missing."""
        start_time = datetime(2024, 1, 6, 10, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 7, 10, 0, tzinfo=timezone.utc)

        # Test with unknown symbol
        classification = gap_classifier.classify_gap(
            start_time=start_time, end_time=end_time, symbol="UNKNOWN", timeframe="1d"
        )

        # Should fall back to weekend detection with default logic
        assert classification == GapClassification.EXPECTED_WEEKEND

    def test_get_symbol_trading_hours(self, gap_classifier):
        """Test retrieval of symbol trading hours."""
        aapl_hours = gap_classifier.get_symbol_trading_hours("AAPL")
        assert aapl_hours is not None
        assert aapl_hours["timezone"] == "America/New_York"
        assert aapl_hours["regular_hours"]["start"] == "09:30"

        unknown_hours = gap_classifier.get_symbol_trading_hours("UNKNOWN")
        assert unknown_hours is None

    def test_bar_calculation(self, gap_classifier):
        """Test calculation of missing bars."""
        start_time = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)  # 2 hours

        # Test 1-hour timeframe
        bars = gap_classifier._calculate_bars_missing(start_time, end_time, "1h")
        assert bars == 2

        # Test 5-minute timeframe
        bars = gap_classifier._calculate_bars_missing(start_time, end_time, "5m")
        assert bars == 24  # 120 minutes / 5 minutes per bar

    def test_day_context_generation(self, gap_classifier):
        """Test generation of human-readable day context."""
        # Same day
        start = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)  # Monday
        end = datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc)
        context = gap_classifier._generate_day_context(start, end)
        assert "Monday" in context

        # Multi-day
        start = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)  # Monday
        end = datetime(2024, 1, 16, 14, 0, tzinfo=timezone.utc)  # Tuesday
        context = gap_classifier._generate_day_context(start, end)
        assert "Monday-Tuesday" in context

        # Friday (pre-weekend)
        start = datetime(2024, 1, 19, 10, 0, tzinfo=timezone.utc)  # Friday
        end = datetime(2024, 1, 19, 14, 0, tzinfo=timezone.utc)
        context = gap_classifier._generate_day_context(start, end)
        assert "Friday (pre-weekend)" in context
