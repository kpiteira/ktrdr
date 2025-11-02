"""
Test suite for SegmentManager component.

Tests the extracted segmentation logic to ensure optimal segment creation
and fetching behavior across all modes with proper error handling.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest

from ktrdr.async_infrastructure.progress import GenericProgressManager
from ktrdr.data.acquisition.segment_manager import SegmentManager
from ktrdr.data.loading_modes import DataLoadingMode


class TestSegmentManager:
    """Test suite for SegmentManager component."""

    @pytest.fixture
    def segment_manager(self):
        """Create SegmentManager instance for testing."""
        return SegmentManager()

    @pytest.fixture
    def sample_gaps(self):
        """Create sample gaps for testing."""
        return [
            (
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 1, 3, tzinfo=timezone.utc),
            ),
            (
                datetime(2023, 1, 5, tzinfo=timezone.utc),
                datetime(2023, 1, 7, tzinfo=timezone.utc),
            ),
        ]

    @pytest.fixture
    def large_gap(self):
        """Create a large gap that needs splitting."""
        return [
            (
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 2, 1, tzinfo=timezone.utc),
            )
        ]

    @pytest.fixture
    def mock_external_provider(self):
        """Mock external data provider."""
        provider = AsyncMock()
        provider.fetch_historical_data.return_value = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [1000, 1100],
            },
            index=pd.date_range("2023-01-01", periods=2, freq="1h", tz="UTC"),
        )
        return provider

    @pytest.fixture
    def mock_progress_manager(self):
        """Mock progress manager."""
        return Mock(spec=GenericProgressManager)

    def test_create_segments_from_small_gaps(self, segment_manager, sample_gaps):
        """Test creating segments from gaps that don't need splitting."""
        # Act
        segments = segment_manager.create_segments(
            sample_gaps, DataLoadingMode.TAIL, "1h"
        )

        # Assert
        assert len(segments) == 2  # Each gap becomes one segment
        assert segments[0] == (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 3, tzinfo=timezone.utc),
        )
        assert segments[1] == (
            datetime(2023, 1, 5, tzinfo=timezone.utc),
            datetime(2023, 1, 7, tzinfo=timezone.utc),
        )

    @patch("ktrdr.config.ib_limits.IbLimitsRegistry.get_duration_limit")
    def test_create_segments_splits_large_gaps(
        self, mock_duration_limit, segment_manager, large_gap
    ):
        """Test splitting large gaps into IB-compliant segments."""
        # Arrange
        mock_duration_limit.return_value = timedelta(days=7)  # 7-day limit

        # Act
        segments = segment_manager.create_segments(
            large_gap, DataLoadingMode.BACKFILL, "1d"
        )

        # Assert
        assert len(segments) > 1  # Should be split

        # Verify all segments are within the limit
        for start, end in segments:
            assert (end - start) <= timedelta(days=7)

        # Verify segments cover the entire gap
        assert segments[0][0] == large_gap[0][0]  # First segment starts at gap start
        assert segments[-1][1] == large_gap[0][1]  # Last segment ends at gap end

    def test_prioritize_segments_tail_mode(self, segment_manager, sample_gaps):
        """Test segment prioritization for tail mode (most recent first)."""
        # Arrange
        segments = segment_manager.create_segments(
            sample_gaps, DataLoadingMode.TAIL, "1h"
        )

        # Act
        prioritized = segment_manager.prioritize_segments(
            segments, DataLoadingMode.TAIL
        )

        # Assert
        # Tail mode should prioritize most recent first
        assert prioritized[0][0] >= prioritized[1][0]  # First segment is most recent

    def test_prioritize_segments_backfill_mode(self, segment_manager, sample_gaps):
        """Test segment prioritization for backfill mode (oldest first)."""
        # Arrange
        segments = segment_manager.create_segments(
            sample_gaps, DataLoadingMode.BACKFILL, "1h"
        )

        # Act
        prioritized = segment_manager.prioritize_segments(
            segments, DataLoadingMode.BACKFILL
        )

        # Assert
        # Backfill mode should prioritize oldest first
        assert prioritized[0][0] <= prioritized[1][0]  # First segment is oldest

    def test_estimate_segment_time_different_timeframes(self, segment_manager):
        """Test segment time estimation for different timeframes."""
        # Arrange
        segment = (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        )

        # Act & Assert
        time_1min = segment_manager.estimate_segment_time(segment, "1m")
        time_1hour = segment_manager.estimate_segment_time(segment, "1h")
        time_1day = segment_manager.estimate_segment_time(segment, "1d")

        # Higher frequency should take longer to fetch
        assert time_1min > time_1hour > time_1day

    @pytest.mark.asyncio
    async def test_handle_segment_retry_success(
        self, segment_manager, mock_external_provider
    ):
        """Test successful segment retry after initial failure."""
        # Arrange
        segment = (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        )

        # Act
        result = await segment_manager.handle_segment_retry(
            failed_segment=segment,
            retry_count=1,
            symbol="AAPL",
            timeframe="1h",
            external_provider=mock_external_provider,
        )

        # Assert
        assert result is not None
        mock_external_provider.fetch_historical_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_segment_retry_max_retries(
        self, segment_manager, mock_external_provider
    ):
        """Test segment retry stops after max retries."""
        # Arrange
        segment = (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        )
        mock_external_provider.fetch_historical_data.side_effect = Exception(
            "Fetch failed"
        )

        # Act
        result = await segment_manager.handle_segment_retry(
            failed_segment=segment,
            retry_count=3,  # Max retries
            symbol="AAPL",
            timeframe="1h",
            external_provider=mock_external_provider,
        )

        # Assert
        assert result is None  # Should give up after max retries

    @pytest.mark.asyncio
    async def test_fetch_segments_with_resilience_success(
        self,
        segment_manager,
        sample_gaps,
        mock_external_provider,
        mock_progress_manager,
    ):
        """Test successful fetching of multiple segments."""
        # Arrange
        segments = segment_manager.create_segments(
            sample_gaps, DataLoadingMode.TAIL, "1h"
        )

        # Act
        (
            successful_data,
            successful_count,
            failed_count,
        ) = await segment_manager.fetch_segments_with_resilience(
            symbol="AAPL",
            timeframe="1h",
            segments=segments,
            external_provider=mock_external_provider,
            progress_manager=mock_progress_manager,
        )

        # Assert
        assert successful_count == len(segments)
        assert failed_count == 0
        assert len(successful_data) == len(segments)
        assert mock_external_provider.fetch_historical_data.call_count == len(segments)

    @pytest.mark.asyncio
    async def test_fetch_segments_with_resilience_partial_failure(
        self,
        segment_manager,
        sample_gaps,
        mock_external_provider,
        mock_progress_manager,
    ):
        """Test fetching with some segment failures."""
        # Arrange
        segments = segment_manager.create_segments(
            sample_gaps, DataLoadingMode.TAIL, "1h"
        )

        # Make first fetch succeed, second fail
        mock_external_provider.fetch_historical_data.side_effect = [
            pd.DataFrame(
                {
                    "open": [100.0],
                    "high": [102.0],
                    "low": [99.0],
                    "close": [101.0],
                    "volume": [1000],
                },
                index=pd.date_range("2023-01-01", periods=1, freq="1h", tz="UTC"),
            ),
            Exception("Network error"),
        ]

        # Act
        (
            successful_data,
            successful_count,
            failed_count,
        ) = await segment_manager.fetch_segments_with_resilience(
            symbol="AAPL",
            timeframe="1h",
            segments=segments,
            external_provider=mock_external_provider,
            progress_manager=mock_progress_manager,
        )

        # Assert
        assert successful_count == 1
        assert failed_count == 1
        assert len(successful_data) == 1

    @pytest.mark.asyncio
    async def test_fetch_segments_cancellation(
        self, segment_manager, sample_gaps, mock_external_provider
    ):
        """Test segment fetching respects cancellation."""
        # Arrange
        segments = segment_manager.create_segments(
            sample_gaps, DataLoadingMode.TAIL, "1h"
        )
        cancellation_token = Mock()
        cancellation_token.is_set.return_value = True  # Simulate cancellation

        # Act & Assert
        with pytest.raises(asyncio.CancelledError):
            await segment_manager.fetch_segments_with_resilience(
                symbol="AAPL",
                timeframe="1h",
                segments=segments,
                external_provider=mock_external_provider,
                cancellation_token=cancellation_token,
            )

    def test_empty_gaps_returns_empty_segments(self, segment_manager):
        """Test that empty gaps list returns empty segments."""
        # Act
        segments = segment_manager.create_segments([], DataLoadingMode.TAIL, "1h")

        # Assert
        assert segments == []

    @patch("ktrdr.config.ib_limits.IbLimitsRegistry.get_duration_limit")
    def test_consistent_segment_sizing_across_modes(
        self, mock_duration_limit, segment_manager
    ):
        """Test that all modes create identical segments using only IB limits."""
        # Arrange
        mock_duration_limit.return_value = timedelta(days=30)  # 30-day IB limit
        large_gap = [
            (
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 3, 1, tzinfo=timezone.utc),
            )
        ]

        # Act - test different modes
        tail_segments = segment_manager.create_segments(
            large_gap, DataLoadingMode.TAIL, "1d"
        )
        backfill_segments = segment_manager.create_segments(
            large_gap, DataLoadingMode.BACKFILL, "1d"
        )
        full_segments = segment_manager.create_segments(
            large_gap, DataLoadingMode.FULL, "1d"
        )

        # Assert - all modes should create identical segments using IB limit (30 days)
        expected_segments = 2  # 59 days / 30 days = 2 segments
        assert len(tail_segments) == expected_segments
        assert len(backfill_segments) == expected_segments
        assert len(full_segments) == expected_segments

        # All segments should be limited by IB duration limit (30 days)
        for segments in [tail_segments, backfill_segments, full_segments]:
            for start, end in segments:
                assert (end - start) <= timedelta(days=30)

        # All modes should produce identical results
        assert tail_segments == backfill_segments == full_segments
