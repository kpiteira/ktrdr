"""
Unit tests for DataAcquisitionService download operations.

Tests the basic download flow: cache-check → download → save.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest

from ktrdr.data.acquisition.acquisition_service import DataAcquisitionService
from ktrdr.errors.exceptions import DataNotFoundError


class TestDownloadDataBasicFlow:
    """Test suite for basic download_data flow."""

    @pytest.mark.asyncio
    async def test_download_data_method_exists(self):
        """DataAcquisitionService should have download_data method."""
        service = DataAcquisitionService()
        assert hasattr(service, "download_data")
        assert callable(service.download_data)

    @pytest.mark.asyncio
    async def test_download_data_returns_operation_id(self):
        """download_data should return operation ID string."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        # Mock repository to raise not found (no cache)
        mock_repo.load_from_cache.side_effect = DataNotFoundError(
            "Not in cache", "DATA-NotFound", {}
        )

        # Mock provider to return data
        test_df = pd.DataFrame(
            {
                "open": [1.0, 2.0],
                "high": [1.5, 2.5],
                "low": [0.9, 1.9],
                "close": [1.2, 2.2],
                "volume": [100, 200],
            }
        )
        mock_provider.fetch_historical_data.return_value = test_df

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        result = await service.download_data("AAPL", "1d")

        assert isinstance(result, dict)
        assert "operation_id" in result
        assert result["operation_id"].startswith("op_")

    @pytest.mark.asyncio
    async def test_download_data_checks_cache_first(self):
        """download_data should check cache before downloading."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        # Mock repository to return cached data
        cached_df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.5],
                "low": [0.9],
                "close": [1.2],
                "volume": [100],
            }
        )
        mock_repo.load_from_cache.return_value = cached_df

        # Mock provider to return data
        test_df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.5],
                "low": [0.9],
                "close": [1.2],
                "volume": [100],
            }
        )
        mock_provider.fetch_historical_data.return_value = test_df

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        # Mock start_managed_operation to execute the operation function directly
        with patch.object(service, "start_managed_operation") as mock_managed:
            # Define a side effect that executes the operation_func
            async def execute_operation(*args, **kwargs):
                operation_func = kwargs.get("operation_func")
                if operation_func:
                    await operation_func()
                return {"operation_id": "op_test", "status": "started"}

            mock_managed.side_effect = execute_operation

            await service.download_data("AAPL", "1d")

            # Should check cache (called multiple times: initial check + periodic save merges)
            # With SegmentManager integration, load_from_cache is called for periodic saves too
            assert (
                mock_repo.load_from_cache.call_count >= 1
            ), "Should check cache at least once"

    @pytest.mark.asyncio
    async def test_download_data_downloads_when_cache_empty(self):
        """download_data should download from provider when cache is empty."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        # Mock repository to raise not found
        mock_repo.load_from_cache.side_effect = DataNotFoundError(
            "Not in cache", "DATA-NotFound", {}
        )

        # Mock provider to return data
        test_df = pd.DataFrame(
            {
                "open": [1.0, 2.0],
                "high": [1.5, 2.5],
                "low": [0.9, 1.9],
                "close": [1.2, 2.2],
                "volume": [100, 200],
            }
        )
        mock_provider.fetch_historical_data.return_value = test_df

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        # Mock start_managed_operation to execute the operation function directly
        with patch.object(service, "start_managed_operation") as mock_managed:

            async def execute_operation(*args, **kwargs):
                operation_func = kwargs.get("operation_func")
                if operation_func:
                    await operation_func()
                return {"operation_id": "op_test", "status": "started"}

            mock_managed.side_effect = execute_operation

            await service.download_data("AAPL", "1d")

            # Should call provider to fetch data
            mock_provider.fetch_historical_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_data_saves_to_cache(self):
        """download_data should save downloaded data to cache."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        # Mock repository to raise not found
        mock_repo.load_from_cache.side_effect = DataNotFoundError(
            "Not in cache", "DATA-NotFound", {}
        )

        # Mock provider to return data
        test_df = pd.DataFrame(
            {
                "open": [1.0, 2.0],
                "high": [1.5, 2.5],
                "low": [0.9, 1.9],
                "close": [1.2, 2.2],
                "volume": [100, 200],
            }
        )
        mock_provider.fetch_historical_data.return_value = test_df

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        # Mock start_managed_operation to execute the operation function directly
        with patch.object(service, "start_managed_operation") as mock_managed:

            async def execute_operation(*args, **kwargs):
                operation_func = kwargs.get("operation_func")
                if operation_func:
                    await operation_func()
                return {"operation_id": "op_test", "status": "started"}

            mock_managed.side_effect = execute_operation

            await service.download_data("AAPL", "1d")

            # Should save to cache (may be called multiple times: periodic save + final save)
            # With SegmentManager integration, save_to_cache is called for periodic saves too
            assert (
                mock_repo.save_to_cache.call_count >= 1
            ), "Should save to cache at least once"
            # Verify it was called with correct symbol and timeframe
            calls = mock_repo.save_to_cache.call_args_list
            assert any(
                call[0][0] == "AAPL" and call[0][1] == "1d" for call in calls
            ), "Should save with correct symbol and timeframe"

    @pytest.mark.asyncio
    async def test_download_data_accepts_date_parameters(self):
        """download_data should accept start_date and end_date parameters."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        mock_repo.load_from_cache.side_effect = DataNotFoundError(
            "Not in cache", "DATA-NotFound", {}
        )

        test_df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.5],
                "low": [0.9],
                "close": [1.2],
                "volume": [100],
            }
        )
        mock_provider.fetch_historical_data.return_value = test_df

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        # Use timezone-aware datetimes (implementation ensures timezone awareness)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)

        # Mock start_managed_operation to execute the operation function directly
        with patch.object(service, "start_managed_operation") as mock_managed:

            async def execute_operation(*args, **kwargs):
                operation_func = kwargs.get("operation_func")
                if operation_func:
                    await operation_func()
                return {"operation_id": "op_test", "status": "started"}

            mock_managed.side_effect = execute_operation

            await service.download_data("AAPL", "1d", start_date=start, end_date=end)

            # Should pass dates to provider (provider uses 'start' and 'end', not 'start_date' and 'end_date')
            # Note: Implementation ensures timezone awareness, so dates will be timezone-aware
            assert (
                mock_provider.fetch_historical_data.called
            ), "Provider should be called"
            call_args = mock_provider.fetch_historical_data.call_args
            # Compare date/time values (implementation may add timezone if not present)
            assert call_args[1]["start"].replace(tzinfo=None) == start.replace(
                tzinfo=None
            )
            assert call_args[1]["end"].replace(tzinfo=None) == end.replace(tzinfo=None)

    @pytest.mark.asyncio
    async def test_download_data_uses_managed_operation(self):
        """download_data should use ServiceOrchestrator's start_managed_operation."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        mock_repo.load_from_cache.side_effect = DataNotFoundError(
            "Not in cache", "DATA-NotFound", {}
        )

        test_df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.5],
                "low": [0.9],
                "close": [1.2],
                "volume": [100],
            }
        )
        mock_provider.fetch_historical_data.return_value = test_df

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        # Patch start_managed_operation
        with patch.object(
            service, "start_managed_operation", new=AsyncMock()
        ) as mock_managed:
            mock_managed.return_value = {
                "operation_id": "op_test_123",
                "status": "started",
            }

            result = await service.download_data("AAPL", "1d")

            # Should use managed operation
            mock_managed.assert_called_once()
            assert result["operation_id"] == "op_test_123"


class TestDownloadDataErrorHandling:
    """Test suite for error handling in download_data."""

    @pytest.mark.asyncio
    async def test_download_data_handles_provider_error(self):
        """download_data should handle provider errors gracefully."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        mock_repo.load_from_cache.side_effect = DataNotFoundError(
            "Not in cache", "DATA-NotFound", {}
        )

        # Mock provider to raise error
        mock_provider.fetch_historical_data.side_effect = Exception("Provider error")

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        # Should raise or return error in operation
        result = await service.download_data("AAPL", "1d")

        # Operation should be created even if it fails
        assert "operation_id" in result

    @pytest.mark.asyncio
    async def test_download_data_handles_save_error(self):
        """download_data should handle save errors gracefully."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        mock_repo.load_from_cache.side_effect = DataNotFoundError(
            "Not in cache", "DATA-NotFound", {}
        )

        test_df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.5],
                "low": [0.9],
                "close": [1.2],
                "volume": [100],
            }
        )
        mock_provider.fetch_historical_data.return_value = test_df

        # Mock save to raise error
        mock_repo.save_to_cache.side_effect = Exception("Save error")

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        # Should create operation even if save fails
        result = await service.download_data("AAPL", "1d")
        assert "operation_id" in result


class TestDownloadDataIntegration:
    """Integration-style tests for download_data flow."""

    @pytest.mark.asyncio
    async def test_download_data_full_flow(self):
        """Test complete download flow: cache miss → download → save."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        # Setup: cache miss
        mock_repo.load_from_cache.side_effect = DataNotFoundError(
            "Not in cache", "DATA-NotFound", {}
        )

        # Setup: provider returns data
        test_df = pd.DataFrame(
            {
                "open": [1.0, 2.0, 3.0],
                "high": [1.5, 2.5, 3.5],
                "low": [0.9, 1.9, 2.9],
                "close": [1.2, 2.2, 3.2],
                "volume": [100, 200, 300],
            }
        )
        mock_provider.fetch_historical_data.return_value = test_df

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        # Mock start_managed_operation to execute the operation function directly
        with patch.object(service, "start_managed_operation") as mock_managed:

            async def execute_operation(*args, **kwargs):
                operation_func = kwargs.get("operation_func")
                if operation_func:
                    await operation_func()
                return {"operation_id": "op_test", "status": "started"}

            mock_managed.side_effect = execute_operation

            result = await service.download_data("AAPL", "1d")

            # Verify flow (with SegmentManager integration, calls may be multiple due to periodic saves)
            assert result["operation_id"].startswith("op_")
            assert mock_repo.load_from_cache.call_count >= 1, "Should check cache"
            assert (
                mock_provider.fetch_historical_data.call_count >= 1
            ), "Should fetch data"
            assert mock_repo.save_to_cache.call_count >= 1, "Should save to cache"

    @pytest.mark.asyncio
    async def test_download_data_with_cache_hit(self):
        """Test download flow when data exists in cache."""
        mock_repo = Mock()
        mock_provider = AsyncMock()

        # Setup: cache hit
        cached_df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.5],
                "low": [0.9],
                "close": [1.2],
                "volume": [100],
            }
        )
        mock_repo.load_from_cache.return_value = cached_df

        # Mock provider to return data
        test_df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.5],
                "low": [0.9],
                "close": [1.2],
                "volume": [100],
            }
        )
        mock_provider.fetch_historical_data.return_value = test_df

        service = DataAcquisitionService(repository=mock_repo, provider=mock_provider)

        # Mock start_managed_operation to execute the operation function directly
        with patch.object(service, "start_managed_operation") as mock_managed:

            async def execute_operation(*args, **kwargs):
                operation_func = kwargs.get("operation_func")
                if operation_func:
                    await operation_func()
                return {"operation_id": "op_test", "status": "started"}

            mock_managed.side_effect = execute_operation

            result = await service.download_data("AAPL", "1d")

            # Should check cache (may be called multiple times due to periodic saves)
            assert mock_repo.load_from_cache.call_count >= 1, "Should check cache"

            # Test verifies operation is created
            assert result["operation_id"].startswith("op_")
