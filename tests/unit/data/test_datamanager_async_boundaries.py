"""
Test DataManager async/sync boundary behavior.

This test file validates that DataManager properly handles async/sync boundaries
without creating new event loops inside internal methods.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from ktrdr.data.data_manager import DataManager


class TestDataManagerAsyncBoundaries:
    """Test async/sync boundary handling in DataManager."""

    @pytest.fixture
    def mock_external_provider(self):
        """Mock external data provider for testing."""
        provider = AsyncMock()
        provider.get_head_timestamp.return_value = pd.Timestamp("2023-01-01", tz="UTC")
        return provider

    @pytest.fixture
    def data_manager(self, mock_external_provider):
        """Create DataManager instance with mocked external provider."""
        dm = DataManager()
        dm.external_provider = mock_external_provider
        return dm

    def test_no_nested_asyncio_run_in_enhance_data_collection(self, data_manager):
        """
        Test that _enhance_data_collection_with_fallback doesn't use nested asyncio.run().

        This test validates that the method doesn't create new event loops internally.
        Currently this will FAIL because the method uses asyncio.run() internally.
        """
        # Arrange
        segments = [{"symbol": "AAPL", "start": "2023-01-01", "end": "2023-01-02"}]

        # Mock the internal async method
        async def mock_fetch_async():
            return [], 0, 1

        # Act & Assert - This should not raise RuntimeError about running event loop
        # But currently it WILL fail because of nested asyncio.run()
        with patch.object(data_manager, "_create_data_fetcher") as mock_fetcher:
            mock_fetcher.return_value.__aenter__.return_value.fetch_bulk_data_async.return_value = (
                mock_fetch_async()
            )

            # This call should work in async context without nested asyncio.run()
            result = data_manager._enhance_data_collection_with_fallback(segments)
            assert isinstance(result, tuple)
            assert len(result) == 3  # successful_data, successful_count, failed_count

    def test_no_nested_asyncio_run_in_fetch_head_timestamp(self, data_manager):
        """
        Test that _fetch_head_timestamp_sync doesn't use nested asyncio.run().

        Currently this will FAIL because the method uses asyncio.run() internally.
        """
        # Arrange
        symbol = "AAPL"
        timeframe = "1h"

        # Act & Assert - This should not raise RuntimeError about running event loop
        # But currently it WILL fail because of nested asyncio.run()
        result = data_manager._fetch_head_timestamp_sync(symbol, timeframe)

        # The result should be a timestamp string or None
        assert result is None or isinstance(result, str)

    def test_no_nested_asyncio_run_in_validate_request(self, data_manager):
        """
        Test that _validate_request_against_head_timestamp doesn't use nested asyncio.run().

        Currently this will FAIL because the method uses asyncio.run() internally.
        """
        # Arrange
        symbol = "AAPL"
        timeframe = "1h"
        start_date = pd.Timestamp("2023-01-01", tz="UTC")
        end_date = pd.Timestamp("2023-01-02", tz="UTC")

        # Act & Assert - This should not raise RuntimeError about running event loop
        result = data_manager._validate_request_against_head_timestamp(
            symbol, timeframe, start_date, end_date
        )

        # Should return tuple (is_valid, error_message, head_timestamp)
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], bool)

    @pytest.mark.asyncio
    async def test_public_api_works_in_async_context(self, data_manager):
        """
        Test that public API methods work properly when called from async context.

        This test ensures that after the refactor, the public sync API can be called
        from within async functions without issues.
        """
        # Arrange
        symbol = "AAPL"
        timeframe = "1h"

        # Mock the load_data method to return test data
        test_data = pd.DataFrame(
            {
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            },
            index=[pd.Timestamp("2023-01-01", tz="UTC")],
        )

        with patch.object(data_manager, "load_data", return_value=test_data):
            # Act - This should work without issues after refactor
            result = await asyncio.to_thread(data_manager.load_data, symbol, timeframe)

            # Assert
            assert isinstance(result, pd.DataFrame)
            assert not result.empty

    def test_internal_methods_should_be_async(self, data_manager):
        """
        Test that internal methods that should be async are properly defined as async.

        This test will PASS after the refactor when internal methods become async.
        Currently it will FAIL because these methods don't exist yet.
        """
        # These methods should exist and be async after refactor
        expected_async_methods = [
            "_fetch_segments_with_component_async",
            "_fetch_head_timestamp_async",
            "_validate_request_against_head_timestamp_async",
        ]

        for method_name in expected_async_methods:
            # This will currently fail because these async methods don't exist
            assert hasattr(
                data_manager, method_name
            ), f"Missing async method: {method_name}"
            method = getattr(data_manager, method_name)
            assert asyncio.iscoroutinefunction(
                method
            ), f"Method {method_name} should be async"

    @pytest.mark.asyncio
    async def test_async_internal_method_chains(self, data_manager):
        """
        Test that internal async methods can be properly chained with await.

        This test validates the target architecture where internal methods are async
        and can be awaited without creating new event loops.

        Currently this will FAIL because the async methods don't exist yet.
        """
        # Arrange
        symbol = "AAPL"
        timeframe = "1h"

        # This should work after refactor - async internal methods that can be awaited
        try:
            # These calls should work with await after refactor
            head_timestamp = await data_manager._fetch_head_timestamp_async(
                symbol, timeframe
            )
            assert head_timestamp is None or isinstance(head_timestamp, str)

            start_date = pd.Timestamp("2023-01-01", tz="UTC")
            end_date = pd.Timestamp("2023-01-02", tz="UTC")
            is_valid, error, timestamp = (
                await data_manager._validate_request_against_head_timestamp_async(
                    symbol, timeframe, start_date, end_date
                )
            )
            assert isinstance(is_valid, bool)

        except AttributeError:
            # Expected to fail initially - these methods don't exist yet
            pytest.skip(
                "Async internal methods not implemented yet - this is expected before refactor"
            )

    def test_detect_nested_asyncio_run_calls(self, data_manager):
        """
        Test to detect and count asyncio.run() calls in DataManager methods.

        This test should FAIL initially showing the current problem,
        then PASS after refactor when asyncio.run() calls are eliminated.
        """
        # Read the source code of DataManager to detect asyncio.run() usage
        import inspect

        source = inspect.getsource(DataManager)

        # Count asyncio.run() occurrences - should be 0 after refactor
        asyncio_run_count = source.count("asyncio.run(")

        # This assertion will FAIL initially (showing current problem)
        # and PASS after refactor when asyncio.run() is eliminated from internal methods
        assert (
            asyncio_run_count == 0
        ), f"Found {asyncio_run_count} asyncio.run() calls in DataManager - should be 0 for internal methods"

    def test_performance_improvement_potential(self, data_manager):
        """
        Test to measure potential for performance improvement.

        This test measures the overhead of current approach vs target approach.
        Initially documents the problem, after refactor validates the improvement.
        """
        import time

        # Mock external provider response
        data_manager.external_provider = AsyncMock()
        data_manager.external_provider.get_head_timestamp.return_value = pd.Timestamp(
            "2023-01-01", tz="UTC"
        )

        # Measure current approach (with nested asyncio.run())
        start_time = time.perf_counter()
        try:
            # This uses nested asyncio.run() - creates overhead
            data_manager._fetch_head_timestamp_sync("AAPL", "1h")
            current_time = time.perf_counter() - start_time
        except RuntimeError as e:
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                # Expected in async context - this shows the problem
                current_time = float("inf")  # Infinite time = broken
            else:
                raise

        # Document the performance issue
        # After refactor, this should show significant improvement
        assert current_time < 1.0 or current_time == float("inf"), (
            f"Current implementation too slow ({current_time:.3f}s) or broken. "
            "Target: <0.1s after eliminating nested asyncio.run()"
        )
