"""
Test suite for DataFetcher component.

Tests the extracted async fetching logic to ensure enhanced HTTP session management,
connection pooling, progress tracking, and graceful cancellation.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import aiohttp
import pandas as pd
import pytest

from ktrdr.data.components.data_fetcher import DataFetcher
from ktrdr.data.components.progress_manager import ProgressManager


class TestDataFetcher:
    """Test suite for DataFetcher component."""

    @pytest.fixture
    def progress_manager(self):
        """Create mock progress manager for testing."""
        return Mock(spec=ProgressManager)

    @pytest.fixture
    def data_fetcher(self):
        """Create DataFetcher instance for testing."""
        return DataFetcher()

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
    def sample_segments(self):
        """Create sample segments for testing."""
        return [
            (
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 1, 2, tzinfo=timezone.utc),
            ),
            (
                datetime(2023, 1, 3, tzinfo=timezone.utc),
                datetime(2023, 1, 4, tzinfo=timezone.utc),
            ),
        ]

    def test_initialization(self):
        """Test DataFetcher initialization."""
        # Act
        fetcher = DataFetcher()

        # Assert
        assert fetcher._session is None

    @pytest.mark.asyncio
    async def test_setup_http_session_creates_persistent_session(self, data_fetcher):
        """Test HTTP session setup with connection pooling."""
        # Act
        await data_fetcher._setup_http_session()

        # Assert
        assert data_fetcher._session is not None
        assert isinstance(data_fetcher._session, aiohttp.ClientSession)

        # Cleanup
        await data_fetcher.cleanup()

    @pytest.mark.asyncio
    async def test_fetch_single_segment_success(
        self, data_fetcher, mock_external_provider
    ):
        """Test successful single segment fetching."""
        # Arrange
        segment = (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        )

        # Act
        result = await data_fetcher.fetch_single_segment(
            segment, "AAPL", "1h", mock_external_provider
        )

        # Assert
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        mock_external_provider.fetch_historical_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_segments_async_sequential_processing(
        self, data_fetcher, sample_segments, mock_external_provider
    ):
        """Test sequential batch fetching with HTTP session persistence."""
        # Act
        results = await data_fetcher.fetch_segments_async(
            sample_segments, "AAPL", "1h", mock_external_provider
        )

        # Assert
        assert len(results) == 2
        assert all(isinstance(df, pd.DataFrame) for df in results)

        # Verify provider was called for each segment
        assert mock_external_provider.fetch_historical_data.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_segments_async_concurrent_batching_small_segments(
        self, data_fetcher, mock_external_provider, progress_manager
    ):
        """Test concurrent batching for small segments."""
        # Arrange - create 5 small segments (< 1 day each)
        small_segments = [
            (
                datetime(2023, 1, i, tzinfo=timezone.utc),
                datetime(2023, 1, i, 12, tzinfo=timezone.utc),  # 12-hour segments
            )
            for i in range(1, 6)
        ]

        # Act
        results = await data_fetcher.fetch_segments_async(
            small_segments, "AAPL", "1h", mock_external_provider
        )

        # Assert
        assert len(results) == 5
        # Should have run concurrently (max 10 for small segments)
        assert mock_external_provider.fetch_historical_data.call_count == 5

    @pytest.mark.asyncio
    async def test_fetch_segments_async_sequential_batching_large_segments(
        self, data_fetcher, mock_external_provider, progress_manager
    ):
        """Test sequential processing for large segments."""
        # Arrange - create 3 large segments (> 7 days each)
        large_segments = [
            (
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 1, 10, tzinfo=timezone.utc),  # 9-day segment
            ),
            (
                datetime(2023, 2, 1, tzinfo=timezone.utc),
                datetime(2023, 2, 10, tzinfo=timezone.utc),  # 9-day segment
            ),
            (
                datetime(2023, 3, 1, tzinfo=timezone.utc),
                datetime(2023, 3, 10, tzinfo=timezone.utc),  # 9-day segment
            ),
        ]

        # Act
        results = await data_fetcher.fetch_segments_async(
            large_segments, "AAPL", "1d", mock_external_provider
        )

        # Assert
        assert len(results) == 3
        # Should have run sequentially for large segments
        assert mock_external_provider.fetch_historical_data.call_count == 3

    @pytest.mark.asyncio
    async def test_connection_reuse_performance_improvement(
        self, data_fetcher, sample_segments, mock_external_provider
    ):
        """Test connection reuse improves performance."""
        # Note: This is more of an integration test concept
        # For unit test, we verify session is reused

        # Act
        await data_fetcher.fetch_segments_async(
            sample_segments, "AAPL", "1h", mock_external_provider
        )

        first_session = data_fetcher._session

        await data_fetcher.fetch_segments_async(
            sample_segments, "AAPL", "1h", mock_external_provider
        )

        second_session = data_fetcher._session

        # Assert - same session instance should be reused
        assert first_session is second_session

        # Cleanup
        await data_fetcher.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_closes_session(self, data_fetcher):
        """Test cleanup properly closes HTTP session."""
        # Arrange
        await data_fetcher._setup_http_session()
        session = data_fetcher._session
        assert session is not None

        # Act
        await data_fetcher.cleanup()

        # Assert
        assert data_fetcher._session is None
        assert session.closed

    @pytest.mark.asyncio
    async def test_fetch_with_partial_failures(
        self, data_fetcher, sample_segments, mock_external_provider, progress_manager
    ):
        """Test handling partial failures in batch operations."""
        # Arrange - first segment succeeds, second fails
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
        results = await data_fetcher.fetch_segments_async(
            sample_segments, "AAPL", "1h", mock_external_provider
        )

        # Assert - should return successful results only
        assert len(results) == 1  # Only successful segment
        assert isinstance(results[0], pd.DataFrame)

    @pytest.mark.asyncio
    async def test_periodic_save_callback_time_based(
        self, data_fetcher, sample_segments, mock_external_provider
    ):
        """Test periodic save callback is called based on time interval."""
        # Arrange
        save_callback_calls = []

        def mock_save_callback(data_list):
            """Mock save callback that records calls."""
            save_callback_calls.append(len(data_list))
            return sum(len(df) for df in data_list)

        # Act - use very short save interval (0.001 minutes = 0.06 seconds)
        results = await data_fetcher.fetch_segments_async(
            sample_segments,
            "AAPL", 
            "1h", 
            mock_external_provider,
            periodic_save_callback=mock_save_callback,
            periodic_save_minutes=0.001  # Very short interval for testing
        )

        # Assert
        assert len(results) == 2
        # Should have called save callback at least once (final save always happens)
        assert len(save_callback_calls) >= 1
        
        # Cleanup
        await data_fetcher.cleanup()

    @pytest.mark.asyncio
    async def test_periodic_save_callback_final_save(
        self, data_fetcher, sample_segments, mock_external_provider
    ):
        """Test periodic save callback is always called at the end."""
        # Arrange
        save_callback_calls = []

        def mock_save_callback(data_list):
            """Mock save callback that records calls."""
            save_callback_calls.append(len(data_list))
            return sum(len(df) for df in data_list)

        # Act - use long save interval that won't trigger during test
        results = await data_fetcher.fetch_segments_async(
            sample_segments,
            "AAPL", 
            "1h", 
            mock_external_provider,
            periodic_save_callback=mock_save_callback,
            periodic_save_minutes=60.0  # Very long interval
        )

        # Assert
        assert len(results) == 2
        # Should have called save callback exactly once at the end
        assert len(save_callback_calls) == 1
        assert save_callback_calls[0] == 2  # Both segments
        
        # Cleanup
        await data_fetcher.cleanup()

    @pytest.mark.asyncio
    async def test_no_periodic_save_when_callback_none(
        self, data_fetcher, sample_segments, mock_external_provider
    ):
        """Test no periodic save when callback is None."""
        # Act
        results = await data_fetcher.fetch_segments_async(
            sample_segments,
            "AAPL", 
            "1h", 
            mock_external_provider,
            periodic_save_callback=None,
            periodic_save_minutes=0.001
        )

        # Assert - should work normally without saves
        assert len(results) == 2
        
        # Cleanup
        await data_fetcher.cleanup()
