"""
Test suite for mode-aware gap analysis functionality in GapAnalyzer.

Tests the new mode-aware capabilities including:
- set_analysis_mode method
- classify_gap_type method with market calendar integration
- prioritize_gaps_by_mode method
- analyze_gaps_by_mode method with mode-specific strategies
- ProgressManager integration for analysis progress reporting

These tests follow TDD methodology - they define the expected behavior
and should initially FAIL until the implementation is complete.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from ktrdr.data.components.gap_analyzer import GapAnalyzer
from ktrdr.data.components.progress_manager import ProgressManager
from ktrdr.data.gap_classifier import GapClassification, GapClassifier, GapInfo
from ktrdr.data.loading_modes import DataLoadingMode


class TestGapInfo:
    """Simplified GapInfo for testing mode-aware functionality."""

    def __init__(
        self, start_time: datetime, end_time: datetime, gap_type: str, priority: int = 1
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.gap_type = gap_type
        self.priority = priority


class TestModeAwareGapAnalysis:
    """Test suite for mode-aware gap analysis functionality."""

    @pytest.fixture
    def gap_classifier(self):
        """Mock GapClassifier for testing."""
        classifier = Mock(spec=GapClassifier)
        classifier.analyze_gap.return_value = GapInfo(
            start_time=datetime(2023, 1, 1),
            end_time=datetime(2023, 1, 2),
            classification=GapClassification.UNEXPECTED,
            bars_missing=24,
            duration_hours=24.0,
            day_context="weekday",
            note="Mock gap",
        )
        return classifier

    @pytest.fixture
    def progress_manager(self):
        """Mock ProgressManager for testing."""
        return Mock(spec=ProgressManager)

    @pytest.fixture
    def gap_analyzer(self, gap_classifier, progress_manager):
        """Create GapAnalyzer instance for testing."""
        analyzer = GapAnalyzer(gap_classifier=gap_classifier)
        analyzer.progress_manager = progress_manager
        return analyzer

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLC data for testing."""
        dates = pd.date_range("2023-01-01", "2023-01-10", freq="1h", tz="UTC")
        return pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.5] * len(dates),
                "volume": [1000] * len(dates),
            },
            index=dates,
        )

    def test_set_analysis_mode(self, gap_analyzer):
        """Test: set_analysis_mode configures mode-specific behavior."""
        # Should fail initially - method doesn't exist yet

        # Test setting different modes
        for mode in DataLoadingMode:
            gap_analyzer.set_analysis_mode(mode)
            assert gap_analyzer.current_mode == mode

    def test_set_analysis_mode_invalid_mode(self, gap_analyzer):
        """Test: set_analysis_mode rejects invalid modes."""
        # Should fail initially - method doesn't exist yet

        with pytest.raises(ValueError, match="Invalid analysis mode"):
            gap_analyzer.set_analysis_mode("invalid_mode")

    def test_classify_gap_type_market_closure(self, gap_analyzer):
        """Test: classify_gap_type detects market closures correctly."""
        # Should fail initially - method doesn't exist yet

        # Weekend gap - should be classified as market closure
        weekend_start = datetime(2023, 1, 7, 16, 0, tzinfo=timezone.utc)  # Friday close
        weekend_end = datetime(2023, 1, 9, 9, 30, tzinfo=timezone.utc)  # Monday open

        gap_type = gap_analyzer.classify_gap_type(
            weekend_start,
            weekend_end,
            market_calendar=Mock(),
            symbol="AAPL",
            timeframe="1h",
        )

        assert gap_type == "market_closure"

    def test_classify_gap_type_missing_data(self, gap_analyzer):
        """Test: classify_gap_type detects missing data during trading hours."""
        # Should fail initially - method doesn't exist yet

        # Wednesday gap during trading hours - should be missing data
        trading_start = datetime(
            2023, 1, 11, 14, 0, tzinfo=timezone.utc
        )  # Wednesday 2pm
        trading_end = datetime(2023, 1, 11, 16, 0, tzinfo=timezone.utc)  # Wednesday 4pm

        gap_type = gap_analyzer.classify_gap_type(
            trading_start,
            trading_end,
            market_calendar=Mock(),
            symbol="AAPL",
            timeframe="1h",
        )

        assert gap_type == "missing_data"

    def test_classify_gap_type_holiday(self, gap_analyzer):
        """Test: classify_gap_type detects holidays."""
        # Should fail initially - method doesn't exist yet

        # New Year's Day gap
        holiday_start = datetime(
            2023, 12, 31, 16, 0, tzinfo=timezone.utc
        )  # Dec 31 close
        holiday_end = datetime(2023, 1, 2, 9, 30, tzinfo=timezone.utc)  # Jan 2 open

        with patch("pandas.tseries.holiday.USFederalHolidayCalendar") as mock_calendar:
            mock_calendar.return_value.holidays.return_value = pd.DatetimeIndex(
                ["2023-01-01"]
            )

            gap_type = gap_analyzer.classify_gap_type(
                holiday_start,
                holiday_end,
                market_calendar=mock_calendar,
                symbol="AAPL",
                timeframe="1h",
            )

            assert gap_type == "holiday"

    def test_prioritize_gaps_by_mode_local(self, gap_analyzer):
        """Test: prioritize_gaps_by_mode returns empty list for LOCAL mode."""
        # Should fail initially - method doesn't exist yet

        gaps = [
            TestGapInfo(datetime(2023, 1, 1), datetime(2023, 1, 2), "missing_data", 1),
            TestGapInfo(datetime(2023, 1, 5), datetime(2023, 1, 6), "missing_data", 1),
        ]

        prioritized = gap_analyzer.prioritize_gaps_by_mode(gaps, DataLoadingMode.LOCAL)

        # LOCAL mode should return no gaps
        assert prioritized == []

    def test_prioritize_gaps_by_mode_tail(self, gap_analyzer):
        """Test: prioritize_gaps_by_mode prioritizes recent gaps for TAIL mode."""
        # Should fail initially - method doesn't exist yet

        gaps = [
            TestGapInfo(
                datetime(2023, 1, 1), datetime(2023, 1, 2), "missing_data", 1
            ),  # Old
            TestGapInfo(
                datetime(2023, 1, 8), datetime(2023, 1, 9), "missing_data", 1
            ),  # Recent
            TestGapInfo(
                datetime(2023, 1, 5), datetime(2023, 1, 6), "missing_data", 1
            ),  # Middle
        ]

        prioritized = gap_analyzer.prioritize_gaps_by_mode(gaps, DataLoadingMode.TAIL)

        # Should prioritize more recent gaps first
        assert len(prioritized) == 3
        assert (
            prioritized[0].start_time
            > prioritized[1].start_time
            > prioritized[2].start_time
        )

    def test_prioritize_gaps_by_mode_backfill(self, gap_analyzer):
        """Test: prioritize_gaps_by_mode prioritizes historical gaps for BACKFILL mode."""
        # Should fail initially - method doesn't exist yet

        gaps = [
            TestGapInfo(
                datetime(2023, 1, 8), datetime(2023, 1, 9), "missing_data", 1
            ),  # Recent
            TestGapInfo(
                datetime(2023, 1, 1), datetime(2023, 1, 2), "missing_data", 1
            ),  # Old
            TestGapInfo(
                datetime(2023, 1, 5), datetime(2023, 1, 6), "missing_data", 1
            ),  # Middle
        ]

        prioritized = gap_analyzer.prioritize_gaps_by_mode(
            gaps, DataLoadingMode.BACKFILL
        )

        # Should prioritize older gaps first
        assert len(prioritized) == 3
        assert (
            prioritized[0].start_time
            < prioritized[1].start_time
            < prioritized[2].start_time
        )

    def test_prioritize_gaps_by_mode_full(self, gap_analyzer):
        """Test: prioritize_gaps_by_mode uses combined strategy for FULL mode."""
        # Should fail initially - method doesn't exist yet

        gaps = [
            TestGapInfo(
                datetime(2023, 1, 1), datetime(2023, 1, 2), "missing_data", 2
            ),  # Old, high priority
            TestGapInfo(
                datetime(2023, 1, 8), datetime(2023, 1, 9), "missing_data", 1
            ),  # Recent, low priority
            TestGapInfo(
                datetime(2023, 1, 5), datetime(2023, 1, 6), "market_closure", 1
            ),  # Middle, market closure
        ]

        prioritized = gap_analyzer.prioritize_gaps_by_mode(gaps, DataLoadingMode.FULL)

        # Should prioritize by gap importance first, then by strategic value
        assert len(prioritized) == 3
        # High priority missing data should come first
        assert (
            prioritized[0].gap_type == "missing_data" and prioritized[0].priority == 2
        )

    def test_analyze_gaps_by_mode_local(self, gap_analyzer, sample_data):
        """Test: analyze_gaps_by_mode returns no gaps for LOCAL mode."""
        # Should fail initially - method doesn't exist yet

        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)

        gaps = gap_analyzer.analyze_gaps_by_mode(
            mode=DataLoadingMode.LOCAL,
            existing_data=sample_data,
            requested_start=start,
            requested_end=end,
            timeframe="1h",
            symbol="AAPL",
        )

        # LOCAL mode should return no gaps
        assert gaps == []

    def test_analyze_gaps_by_mode_tail(self, gap_analyzer, sample_data):
        """Test: analyze_gaps_by_mode focuses on recent gaps for TAIL mode."""
        # Should fail initially - method doesn't exist yet

        start = datetime(2023, 1, 5, tzinfo=timezone.utc)  # Within existing
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)  # Beyond existing

        with patch.object(gap_analyzer, "_analyze_recent_gaps") as mock_recent:
            mock_recent.return_value = [(datetime(2023, 1, 11), datetime(2023, 1, 15))]

            gaps = gap_analyzer.analyze_gaps_by_mode(
                mode=DataLoadingMode.TAIL,
                existing_data=sample_data,
                requested_start=start,
                requested_end=end,
                timeframe="1h",
                symbol="AAPL",
            )

            # Should call _analyze_recent_gaps and return its result
            mock_recent.assert_called_once()
            assert len(gaps) == 1

    def test_analyze_gaps_by_mode_backfill(self, gap_analyzer, sample_data):
        """Test: analyze_gaps_by_mode focuses on historical gaps for BACKFILL mode."""
        # Should fail initially - method doesn't exist yet

        start = datetime(2022, 12, 20, tzinfo=timezone.utc)  # Before existing
        end = datetime(2023, 1, 5, tzinfo=timezone.utc)  # Within existing

        with patch.object(gap_analyzer, "_analyze_historical_gaps") as mock_historical:
            mock_historical.return_value = [
                (datetime(2022, 12, 20), datetime(2023, 1, 1))
            ]

            gaps = gap_analyzer.analyze_gaps_by_mode(
                mode=DataLoadingMode.BACKFILL,
                existing_data=sample_data,
                requested_start=start,
                requested_end=end,
                timeframe="1h",
                symbol="AAPL",
            )

            # Should call _analyze_historical_gaps and return its result
            mock_historical.assert_called_once()
            assert len(gaps) == 1

    def test_analyze_gaps_by_mode_full(self, gap_analyzer, sample_data):
        """Test: analyze_gaps_by_mode combines strategies for FULL mode."""
        # Should fail initially - method doesn't exist yet

        start = datetime(2022, 12, 20, tzinfo=timezone.utc)  # Before existing
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)  # After existing

        with patch.object(gap_analyzer, "_analyze_complete_range") as mock_complete:
            mock_complete.return_value = [
                (datetime(2022, 12, 20), datetime(2023, 1, 1)),
                (datetime(2023, 1, 11), datetime(2023, 1, 15)),
            ]

            gaps = gap_analyzer.analyze_gaps_by_mode(
                mode=DataLoadingMode.FULL,
                existing_data=sample_data,
                requested_start=start,
                requested_end=end,
                timeframe="1h",
                symbol="AAPL",
            )

            # Should call _analyze_complete_range and return its result
            mock_complete.assert_called_once()
            assert len(gaps) == 2

    def test_estimate_analysis_time(self, gap_analyzer):
        """Test: estimate_analysis_time provides time estimates for progress reporting."""
        # Should fail initially - method doesn't exist yet

        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 12, 31, tzinfo=timezone.utc)  # 1 year

        # Different modes should have different time estimates
        local_time = gap_analyzer.estimate_analysis_time(
            start, end, DataLoadingMode.LOCAL
        )
        tail_time = gap_analyzer.estimate_analysis_time(
            start, end, DataLoadingMode.TAIL
        )
        full_time = gap_analyzer.estimate_analysis_time(
            start, end, DataLoadingMode.FULL
        )

        # LOCAL should be fastest (no analysis), FULL should be slowest
        assert local_time < tail_time < full_time
        assert local_time == timedelta(0)  # No analysis needed
        assert full_time > timedelta(seconds=1)  # Some analysis needed

    def test_progress_manager_integration(
        self, gap_analyzer, progress_manager, sample_data
    ):
        """Test: ProgressManager integration reports analysis progress."""
        # Should fail initially - integration doesn't exist yet

        start = datetime(2022, 12, 20, tzinfo=timezone.utc)
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)

        # Set up the progress manager
        gap_analyzer.set_progress_manager(progress_manager)

        # Run analysis with progress reporting
        gap_analyzer.analyze_gaps_by_mode(
            mode=DataLoadingMode.FULL,
            existing_data=sample_data,
            requested_start=start,
            requested_end=end,
            timeframe="1h",
            symbol="AAPL",
        )

        # Verify progress manager was used
        progress_manager.start_operation.assert_called_once()
        progress_manager.start_step.assert_called()
        progress_manager.update_step_progress.assert_called()
        progress_manager.complete_operation.assert_called_once()

    def test_configuration_options(self, gap_analyzer):
        """Test: Configuration options for analysis strategies and thresholds."""
        # Should fail initially - configuration doesn't exist yet

        config = {
            "min_gap_threshold": timedelta(hours=2),
            "max_gaps_per_mode": 100,
            "prioritize_weekends": False,
            "skip_holiday_analysis": True,
        }

        gap_analyzer.set_configuration(config)

        # Verify configuration is applied
        assert gap_analyzer.config["min_gap_threshold"] == timedelta(hours=2)
        assert gap_analyzer.config["max_gaps_per_mode"] == 100

    def test_edge_cases_holidays_and_weekends(self, gap_analyzer):
        """Test: Edge case handling for holidays and market closures."""
        # Should fail initially - edge case handling doesn't exist yet

        # Test New Year's holiday period
        holiday_start = datetime(2023, 12, 29, tzinfo=timezone.utc)  # Friday
        holiday_end = datetime(2023, 1, 3, tzinfo=timezone.utc)  # Tuesday

        gaps = gap_analyzer.analyze_gaps_by_mode(
            mode=DataLoadingMode.FULL,
            existing_data=None,  # No existing data
            requested_start=holiday_start,
            requested_end=holiday_end,
            timeframe="1h",
            symbol="AAPL",
        )

        # Should handle holiday period intelligently
        assert isinstance(gaps, list)
        # Exact behavior depends on implementation, but should not crash

    def test_performance_optimization(self, gap_analyzer, sample_data):
        """Test: Performance optimization for large date ranges."""
        # Should fail initially - optimization doesn't exist yet

        # Test with very large date range
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 12, 31, tzinfo=timezone.utc)  # 4 years

        # Should complete in reasonable time (< 1 second for test)
        import time

        start_time = time.time()

        gaps = gap_analyzer.analyze_gaps_by_mode(
            mode=DataLoadingMode.FULL,
            existing_data=sample_data,
            requested_start=start,
            requested_end=end,
            timeframe="1d",
            symbol="AAPL",
        )

        elapsed = time.time() - start_time
        assert elapsed < 1.0  # Should be fast for large ranges
        assert isinstance(gaps, list)

    def test_mode_specific_step_descriptions(self, gap_analyzer, progress_manager):
        """Test: Mode-specific step descriptions for progress reporting."""
        # Should fail initially - mode-specific descriptions don't exist yet

        gap_analyzer.set_progress_manager(progress_manager)

        # Test different modes produce different step descriptions
        for mode in DataLoadingMode:
            gap_analyzer.set_analysis_mode(mode)

            expected_descriptions = {
                DataLoadingMode.LOCAL: ["Skipping analysis (local mode)"],
                DataLoadingMode.TAIL: [
                    "Analyzing recent gaps",
                    "Prioritizing tail data",
                ],
                DataLoadingMode.BACKFILL: [
                    "Analyzing historical gaps",
                    "Prioritizing backfill data",
                ],
                DataLoadingMode.FULL: [
                    "Analyzing complete range",
                    "Combining strategies",
                    "Prioritizing all gaps",
                ],
            }

            descriptions = gap_analyzer.get_mode_step_descriptions(mode)
            assert descriptions == expected_descriptions[mode]


class TestModeAwareEdgeCases:
    """Test edge cases and error scenarios for mode-aware functionality."""

    @pytest.fixture
    def gap_analyzer(self):
        """Create GapAnalyzer instance for edge case testing."""
        return GapAnalyzer()

    def test_invalid_date_ranges(self, gap_analyzer):
        """Test: Invalid date ranges are handled gracefully."""
        # Should fail initially - validation doesn't exist yet

        # Start after end
        start = datetime(2023, 1, 15, tzinfo=timezone.utc)
        end = datetime(2023, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="Start date must be before end date"):
            gap_analyzer.analyze_gaps_by_mode(
                mode=DataLoadingMode.FULL,
                existing_data=None,
                requested_start=start,
                requested_end=end,
                timeframe="1h",
                symbol="AAPL",
            )

    def test_unsupported_timeframes(self, gap_analyzer):
        """Test: Unsupported timeframes are handled gracefully."""
        # Should fail initially - timeframe validation doesn't exist yet

        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="Unsupported timeframe"):
            gap_analyzer.analyze_gaps_by_mode(
                mode=DataLoadingMode.FULL,
                existing_data=None,
                requested_start=start,
                requested_end=end,
                timeframe="13s",  # Invalid timeframe
                symbol="AAPL",
            )

    def test_memory_efficient_large_ranges(self, gap_analyzer):
        """Test: Memory-efficient processing for very large date ranges."""
        # Should fail initially - memory optimization doesn't exist yet

        # 10 year range - should not consume excessive memory
        start = datetime(2014, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 12, 31, tzinfo=timezone.utc)

        # Mock memory usage tracking
        import tracemalloc

        tracemalloc.start()

        gaps = gap_analyzer.analyze_gaps_by_mode(
            mode=DataLoadingMode.FULL,
            existing_data=None,
            requested_start=start,
            requested_end=end,
            timeframe="1d",
            symbol="AAPL",
        )

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Should not use more than 50MB for analysis
        assert peak < 50 * 1024 * 1024  # 50MB in bytes
        assert isinstance(gaps, list)


if __name__ == "__main__":
    pytest.main([__file__])
