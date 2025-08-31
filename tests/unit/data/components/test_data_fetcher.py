"""
Test suite for DataFetcher component.

Tests the extracted async fetching logic to ensure enhanced HTTP session management,
connection pooling, progress tracking, and graceful cancellation.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pandas as pd
import pytest

from ktrdr.data.components.data_fetcher import DataFetcher
from ktrdr.data.components.progress_manager import ProgressManager
from ktrdr.errors import DataError


class TestDataFetcher:
    """Test suite for DataFetcher component."""

    @pytest.fixture
    def progress_manager(self):
        """Create mock progress manager for testing."""
        return Mock(spec=ProgressManager)

    @pytest.fixture
    def data_fetcher(self, progress_manager):
        """Create DataFetcher instance for testing."""
        return DataFetcher(progress_manager)

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

    def test_initialization(self, progress_manager):
        """Test DataFetcher initialization."""
        # Act
        fetcher = DataFetcher(progress_manager)

        # Assert
        assert fetcher.progress_manager is progress_manager
        assert fetcher._session is None
        assert fetcher._active_tasks == set()
        assert fetcher._cancelled is False

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
    async def test_fetch_single_segment_success(self, data_fetcher, mock_external_provider):
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
    async def test_fetch_single_segment_retry_logic(self, data_fetcher, mock_external_provider):
        """Test retry logic with exponential backoff."""
        # Arrange
        segment = (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        )
        
        # Simulate failure then success
        mock_external_provider.fetch_historical_data.side_effect = [
            Exception("Network error"),
            pd.DataFrame(
                {"open": [100.0], "high": [102.0], "low": [99.0], "close": [101.0], "volume": [1000]},
                index=pd.date_range("2023-01-01", periods=1, freq="1h", tz="UTC"),
            ),
        ]

        # Act
        result = await data_fetcher.fetch_single_segment(
            segment, "AAPL", "1h", mock_external_provider
        )

        # Assert
        assert result is not None
        assert mock_external_provider.fetch_historical_data.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_single_segment_max_retries_exceeded(
        self, data_fetcher, mock_external_provider
    ):
        """Test behavior when max retries are exceeded."""
        # Arrange
        segment = (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        )
        mock_external_provider.fetch_historical_data.side_effect = Exception("Persistent error")

        # Act
        result = await data_fetcher.fetch_single_segment(
            segment, "AAPL", "1h", mock_external_provider
        )

        # Assert
        assert result is None
        assert mock_external_provider.fetch_historical_data.call_count == 3  # Default max retries

    @pytest.mark.asyncio
    async def test_fetch_segments_async_with_progress_updates(
        self, data_fetcher, sample_segments, mock_external_provider, progress_manager
    ):
        """Test batch fetching with progress updates."""
        # Act
        results = await data_fetcher.fetch_segments_async(
            sample_segments, "AAPL", "1h", mock_external_provider
        )

        # Assert
        assert len(results) == 2
        assert all(isinstance(df, pd.DataFrame) for df in results)
        
        # Check progress updates were called
        assert progress_manager.update_progress_with_context.call_count >= 2

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
                datetime(2023, 1, i*10, tzinfo=timezone.utc),
                datetime(2023, 1, i*10 + 8, tzinfo=timezone.utc),  # 8-day segments
            )
            for i in range(1, 4)
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
    async def test_cancel_operations_cancels_active_tasks(
        self, data_fetcher, sample_segments, mock_external_provider
    ):
        """Test operation cancellation."""
        # Arrange - make external provider hang
        mock_external_provider.fetch_historical_data.side_effect = lambda *args, **kwargs: asyncio.sleep(10)

        # Act - start fetching and immediately cancel
        fetch_task = asyncio.create_task(
            data_fetcher.fetch_segments_async(
                sample_segments, "AAPL", "1h", mock_external_provider
            )
        )
        
        # Give it a moment to start
        await asyncio.sleep(0.01)
        
        cancel_result = await data_fetcher.cancel_operations()
        
        # Assert
        assert cancel_result is True  # Cancellation successful
        with pytest.raises(asyncio.CancelledError):
            await fetch_task

    @pytest.mark.asyncio
    async def test_cancel_operations_within_time_limit(self, data_fetcher):
        """Test cancellation completes within 1 second."""
        # Arrange - no active operations
        
        # Act
        start_time = asyncio.get_event_loop().time()
        result = await data_fetcher.cancel_operations()
        end_time = asyncio.get_event_loop().time()

        # Assert
        assert result is True
        assert (end_time - start_time) < 1.0  # Within 1 second requirement

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
    async def test_progress_updates_every_2_seconds(
        self, data_fetcher, mock_external_provider, progress_manager
    ):
        """Test progress updates occur at least every 2 seconds."""
        # Arrange - create segments that will take time to process
        segments = [
            (
                datetime(2023, 1, i, tzinfo=timezone.utc),
                datetime(2023, 1, i + 1, tzinfo=timezone.utc),
            )
            for i in range(1, 10)  # 9 segments
        ]
        
        # Simulate each fetch taking 0.3 seconds
        async def slow_fetch(*args, **kwargs):
            await asyncio.sleep(0.3)
            return pd.DataFrame(
                {"open": [100.0], "high": [102.0], "low": [99.0], "close": [101.0], "volume": [1000]},
                index=pd.date_range("2023-01-01", periods=1, freq="1h", tz="UTC"),
            )
        
        mock_external_provider.fetch_historical_data.side_effect = slow_fetch

        # Act
        await data_fetcher.fetch_segments_async(
            segments, "AAPL", "1h", mock_external_provider
        )

        # Assert - should have multiple progress updates for 9 * 0.3s = 2.7s operation
        assert progress_manager.update_progress_with_context.call_count >= 2

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
                {"open": [100.0], "high": [102.0], "low": [99.0], "close": [101.0], "volume": [1000]},
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

    def test_determine_batch_strategy_small_segments(self, data_fetcher):
        """Test batch strategy determination for small segments."""
        # Arrange - segments < 1 day
        small_segments = [
            (
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 1, 1, 12, tzinfo=timezone.utc),
            ),
            (
                datetime(2023, 1, 2, tzinfo=timezone.utc),
                datetime(2023, 1, 2, 12, tzinfo=timezone.utc),
            ),
        ]

        # Act
        max_concurrent, use_sequential = data_fetcher._determine_batch_strategy(small_segments)

        # Assert
        assert max_concurrent == 10  # Up to 10 concurrent for small segments
        assert use_sequential is False

    def test_determine_batch_strategy_large_segments(self, data_fetcher):
        """Test batch strategy determination for large segments."""
        # Arrange - segments > 7 days
        large_segments = [
            (
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 1, 8, tzinfo=timezone.utc),
            ),
            (
                datetime(2023, 1, 9, tzinfo=timezone.utc),
                datetime(2023, 1, 16, tzinfo=timezone.utc),
            ),
        ]

        # Act
        max_concurrent, use_sequential = data_fetcher._determine_batch_strategy(large_segments)

        # Assert
        assert max_concurrent == 1  # Sequential processing for large segments
        assert use_sequential is True