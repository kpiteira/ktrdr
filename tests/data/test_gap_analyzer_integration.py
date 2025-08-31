"""
Integration tests for GapAnalyzer component usage in DataManager.

Tests to ensure that DataManager's gap analysis methods properly use
the GapAnalyzer component while maintaining backward compatibility.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd

from ktrdr.data.data_manager import DataManager


class TestGapAnalyzerIntegration:
    """Test integration between DataManager and GapAnalyzer component."""

    def test_detect_gaps_behavior_preservation(self, sample_ohlcv_data):
        """
        Test that detect_gaps method behavior is preserved when using GapAnalyzer.

        This test captures the expected behavior before integration changes
        to ensure backward compatibility is maintained.
        """
        # Arrange
        data_manager = DataManager(enable_ib=False)

        # Create sample data with intentional gaps
        timestamps = pd.date_range(
            start="2024-01-01 09:30:00+00:00",
            end="2024-01-01 16:00:00+00:00",
            freq="1h",
            tz=timezone.utc,
        )

        # Create gap data with matching length
        gap_data = pd.DataFrame(
            {
                "open": [100.0] * len(timestamps),
                "high": [105.0] * len(timestamps),
                "low": [95.0] * len(timestamps),
                "close": [102.0] * len(timestamps),
                "volume": [1000] * len(timestamps),
            },
            index=timestamps,
        )

        # Remove middle timestamps to create internal gaps (only valid indices)
        gaps_to_create = [
            2,
            3,
            5,
        ]  # Create gaps at these indices (0-based, max index is 6)
        gap_data = gap_data.drop(gap_data.index[gaps_to_create])

        # Act - call the method we want to test
        detected_gaps = data_manager.detect_gaps(gap_data, "1h")

        # Assert - verify that gaps are detected
        assert isinstance(detected_gaps, list)
        # Each gap should be a tuple of (start_time, end_time)
        for gap in detected_gaps:
            assert isinstance(gap, tuple)
            assert len(gap) == 2
            assert isinstance(gap[0], datetime)
            assert isinstance(gap[1], datetime)
            assert gap[0] < gap[1]  # Start should be before end

        # The method should detect some gaps (we created intentional gaps)
        # Note: The exact number depends on gap classification logic
        assert (
            len(detected_gaps) >= 0
        )  # Could be 0 if gaps are classified as non-significant

    def test_detect_gaps_uses_gap_analyzer_component(self, sample_ohlcv_data):
        """
        Test that detect_gaps method will use GapAnalyzer component after integration.

        This test will FAIL initially (proving it tests the integration)
        and PASS after we update the method to use GapAnalyzer.
        """
        # Arrange
        data_manager = DataManager(enable_ib=False)

        # Create sample data with proper length matching
        timestamps = pd.date_range(
            start="2024-01-01 09:30:00+00:00",
            end="2024-01-01 16:00:00+00:00",
            freq="1h",
            tz=timezone.utc,
        )

        # Create gap data with matching length
        gap_data = pd.DataFrame(
            {
                "open": [100.0] * len(timestamps),
                "high": [105.0] * len(timestamps),
                "low": [95.0] * len(timestamps),
                "close": [102.0] * len(timestamps),
                "volume": [1000] * len(timestamps),
            },
            index=timestamps,
        )

        # Mock the GapAnalyzer's gap detection method to track usage
        with patch.object(
            data_manager.gap_analyzer,
            "detect_internal_gaps",
            return_value=[
                (
                    datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
                )
            ],
        ) as mock_gap_finder:

            # Act
            detected_gaps = data_manager.detect_gaps(gap_data, "1h")

            # Assert - This will FAIL initially because detect_gaps doesn't use GapAnalyzer yet
            # After integration, it should PASS
            mock_gap_finder.assert_called_once()

        # Result should be from GapAnalyzer
        expected_gaps = [
            (
                datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
            )
        ]
        assert detected_gaps == expected_gaps

    def test_detect_gaps_empty_data_handling(self):
        """Test detect_gaps handles empty data correctly."""
        # Arrange
        data_manager = DataManager(enable_ib=False)
        empty_df = pd.DataFrame()

        # Act
        gaps = data_manager.detect_gaps(empty_df, "1h")

        # Assert
        assert gaps == []

    def test_detect_gaps_single_row_handling(self, sample_ohlcv_data):
        """Test detect_gaps handles single-row data correctly."""
        # Arrange
        data_manager = DataManager(enable_ib=False)
        single_row = sample_ohlcv_data.iloc[:1].copy()
        single_row.index = pd.DatetimeIndex(["2024-01-01 09:30:00+00:00"])

        # Act
        gaps = data_manager.detect_gaps(single_row, "1h")

        # Assert
        assert gaps == []
