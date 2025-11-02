"""
Tests for DataService using DataRepository (Task 2.4).

This test file verifies that DataService correctly uses DataRepository
for cache read operations instead of DataManager.

TDD Phase: RED - These tests are written BEFORE implementation
and should FAIL initially, proving they test the correct behavior.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ktrdr.api.services.data_service import DataService
from ktrdr.errors import DataNotFoundError


@pytest.fixture
def sample_dataframe():
    """Create a sample OHLCV DataFrame for testing."""
    dates = pd.date_range("2024-01-01", periods=10, freq="1D", tz="UTC")
    return pd.DataFrame(
        {
            "open": range(100, 110),
            "high": range(105, 115),
            "low": range(95, 105),
            "close": range(102, 112),
            "volume": range(1000, 1010),
        },
        index=dates,
    )


@pytest.fixture
def mock_repository():
    """Create a mock DataRepository for testing."""
    mock = MagicMock()
    mock.load_from_cache = MagicMock()
    mock.get_data_range = MagicMock()
    mock.get_available_symbols = MagicMock()
    return mock


@pytest.mark.api
class TestDataServiceUsesRepository:
    """Test that DataService uses DataRepository for cache operations."""

    def test_data_service_has_repository_attribute(self):
        """Test that DataService initializes with a repository attribute."""
        with patch("ktrdr.api.services.data_service.DataRepository") as MockRepo:
            service = DataService()

            # Service should have repository attribute
            assert hasattr(service, "repository")
            # Repository should be initialized
            assert service.repository is not None
            # DataRepository should have been called
            MockRepo.assert_called_once()

    def test_load_cached_data_uses_repository(self, sample_dataframe):
        """Test that load_cached_data delegates to repository.load_from_cache."""
        with patch("ktrdr.api.services.data_service.DataRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.load_from_cache.return_value = sample_dataframe
            MockRepo.return_value = mock_repo

            service = DataService()
            result = service.load_cached_data(
                symbol="AAPL",
                timeframe="1d",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 10, tzinfo=timezone.utc),
            )

            # Verify repository.load_from_cache was called
            mock_repo.load_from_cache.assert_called_once()
            call_args = mock_repo.load_from_cache.call_args

            # Verify correct parameters
            assert call_args[1]["symbol"] == "AAPL"
            assert call_args[1]["timeframe"] == "1d"
            assert call_args[1]["start_date"] == datetime(
                2024, 1, 1, tzinfo=timezone.utc
            )
            assert call_args[1]["end_date"] == datetime(
                2024, 1, 10, tzinfo=timezone.utc
            )

            # Verify result is returned
            assert result is not None
            assert not result.empty
            assert len(result) == 10

    def test_load_cached_data_without_dates(self, sample_dataframe):
        """Test load_cached_data without date filters."""
        with patch("ktrdr.api.services.data_service.DataRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.load_from_cache.return_value = sample_dataframe
            MockRepo.return_value = mock_repo

            service = DataService()
            result = service.load_cached_data(symbol="AAPL", timeframe="1d")

            # Verify repository called with None for dates
            mock_repo.load_from_cache.assert_called_once_with(
                symbol="AAPL",
                timeframe="1d",
                start_date=None,
                end_date=None,
            )

            assert result is not None

    def test_load_cached_data_handles_not_found(self):
        """Test that load_cached_data properly handles DataNotFoundError."""
        with patch("ktrdr.api.services.data_service.DataRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.load_from_cache.side_effect = DataNotFoundError(
                message="Data not found",
                error_code="DATA-NotFound",
                details={"symbol": "INVALID", "timeframe": "1d"},
            )
            MockRepo.return_value = mock_repo

            service = DataService()

            # Should raise DataNotFoundError
            with pytest.raises(DataNotFoundError):
                service.load_cached_data(symbol="INVALID", timeframe="1d")

    @pytest.mark.asyncio
    async def test_get_available_symbols_uses_repository(self):
        """Test that get_available_symbols delegates to repository."""
        with patch("ktrdr.api.services.data_service.DataRepository") as MockRepo:
            mock_repo = MagicMock()
            expected_symbols = ["AAPL", "MSFT", "GOOGL"]
            mock_repo.get_available_symbols.return_value = expected_symbols
            MockRepo.return_value = mock_repo

            service = DataService()
            result = await service.get_available_symbols()

            # Verify repository.get_available_symbols was called
            mock_repo.get_available_symbols.assert_called_once()

            # Result should contain the symbols
            # Note: get_available_symbols may enrich with metadata
            assert len(result) >= len(expected_symbols)

    @pytest.mark.asyncio
    async def test_get_data_range_uses_repository(self):
        """Test that get_data_range delegates to repository."""
        with patch("ktrdr.api.services.data_service.DataRepository") as MockRepo:
            mock_repo = MagicMock()
            expected_range = {
                "symbol": "AAPL",
                "timeframe": "1d",
                "start_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "end_date": datetime(2024, 1, 10, tzinfo=timezone.utc),
                "rows": 10,
                "exists": True,
            }
            mock_repo.get_data_range.return_value = expected_range
            MockRepo.return_value = mock_repo

            service = DataService()
            result = await service.get_data_range(symbol="AAPL", timeframe="1d")

            # Verify repository.get_data_range was called
            mock_repo.get_data_range.assert_called_once_with("AAPL", "1d")

            # Verify result structure
            assert result["symbol"] == "AAPL"
            assert result["timeframe"] == "1d"

    @pytest.mark.asyncio
    async def test_get_data_range_handles_not_found(self):
        """Test get_data_range when data doesn't exist."""
        with patch("ktrdr.api.services.data_service.DataRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.get_data_range.side_effect = DataNotFoundError(
                message="Data not found",
                error_code="DATA-NotFound",
                details={"symbol": "INVALID", "timeframe": "1d"},
            )
            MockRepo.return_value = mock_repo

            service = DataService()

            # Should raise DataNotFoundError
            with pytest.raises(DataNotFoundError):
                await service.get_data_range(symbol="INVALID", timeframe="1d")


@pytest.mark.api
class TestDataServiceBackwardsCompatibility:
    """Test that async operations still use DataManager (unchanged)."""

    @pytest.mark.asyncio
    async def test_load_data_async_still_uses_data_manager(self):
        """Test that load_data_async continues to use DataManager (not changed in this task)."""
        with (
            patch("ktrdr.api.services.data_service.DataManager") as MockManager,
            patch("ktrdr.api.services.data_service.DataRepository"),
        ):

            from unittest.mock import AsyncMock

            mock_manager = MagicMock()
            mock_manager.load_data_async = AsyncMock(
                return_value={
                    "operation_id": "op_test_123",
                    "status": "started",
                }
            )
            MockManager.return_value = mock_manager

            service = DataService()
            result = await service.load_data_async(
                symbol="AAPL",
                timeframe="1d",
                mode="tail",
            )

            # Verify DataManager.load_data_async was called (POST operations unchanged)
            mock_manager.load_data_async.assert_called_once()

            # Verify result structure
            assert "operation_id" in result
            assert result["status"] == "started"
