"""
Unit tests for DataService migration to Repository-Only.

Tests that DataService uses DataRepository instead of DataManager,
and that dead code methods have been removed.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ktrdr.api.services.data_service import DataService
from ktrdr.errors import DataNotFoundError


@pytest.fixture
def mock_repository():
    """Create a mock DataRepository for testing."""
    with patch("ktrdr.api.services.data_service.DataRepository") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


class TestDataServiceMigration:
    """Test suite for DataService migration to Repository-Only."""

    def test_no_data_manager_import(self):
        """Verify that DataManager is not imported."""
        import ktrdr.api.services.data_service as module

        # DataManager should not be in the module
        assert not hasattr(module, "DataManager")

    def test_init_uses_repository_only(self, mock_repository):
        """Verify DataService initialization uses only DataRepository."""
        service = DataService()

        # Repository should be initialized
        assert hasattr(service, "repository")

        # DataManager should NOT be initialized
        assert not hasattr(service, "data_manager")

    def test_load_data_async_method_removed(self):
        """Verify load_data_async() method has been deleted (dead code)."""
        service = DataService()

        # Method should not exist
        assert not hasattr(service, "load_data_async")

    def test_start_data_loading_operation_method_removed(self):
        """Verify start_data_loading_operation() method has been deleted (dead code)."""
        service = DataService()

        # Method should not exist
        assert not hasattr(service, "start_data_loading_operation")

    @pytest.mark.asyncio
    async def test_get_available_symbols_uses_repository(self, mock_repository):
        """
        Verify get_available_symbols uses repository.get_available_data_files().

        Should NOT use data_manager.data_loader.get_available_data_files().
        """
        # Setup repository mock
        mock_repository.get_available_symbols.return_value = ["AAPL", "MSFT"]
        mock_repository.get_available_data_files.return_value = [
            ("AAPL", "1d"),
            ("AAPL", "1h"),
            ("MSFT", "1d"),
        ]
        mock_repository.get_data_range.return_value = {
            "exists": True,
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "rows": 365,
        }

        service = DataService()
        result = await service.get_available_symbols()

        # Verify repository methods were called
        mock_repository.get_available_symbols.assert_called_once()
        mock_repository.get_available_data_files.assert_called_once()

        # Verify result structure
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_available_timeframes_for_symbol_uses_repository(
        self, mock_repository
    ):
        """
        Verify get_available_timeframes_for_symbol uses repository.

        Should NOT use data_manager.data_loader.get_available_data_files().
        """
        # Setup repository mock
        mock_repository.get_available_data_files.return_value = [
            ("AAPL", "1d"),
            ("AAPL", "1h"),
            ("AAPL", "5m"),
            ("MSFT", "1d"),
        ]

        service = DataService()
        result = await service.get_available_timeframes_for_symbol("AAPL")

        # Verify repository method was called
        mock_repository.get_available_data_files.assert_called_once()

        # Verify result
        assert isinstance(result, list)
        assert "1d" in result
        assert "1h" in result
        assert "5m" in result

    @pytest.mark.asyncio
    async def test_health_check_uses_repository_data_dir(self, mock_repository):
        """
        Verify health_check uses repository.data_dir.

        Should NOT use data_manager.data_loader.data_dir.
        """
        # Setup repository mock
        mock_repository.data_dir = "/path/to/data"
        mock_repository.get_available_data_files.return_value = [
            ("AAPL", "1d"),
            ("MSFT", "1h"),
        ]

        service = DataService()
        result = await service.health_check()

        # Verify repository properties/methods were accessed
        _ = mock_repository.data_dir  # Accessed
        mock_repository.get_available_data_files.assert_called_once()

        # Verify result structure
        assert result["status"] == "healthy"
        assert result["data_directory"] == "/path/to/data"
        assert result["available_files"] == 2

    @pytest.mark.asyncio
    async def test_get_data_range_uses_repository(self, mock_repository):
        """Verify get_data_range uses DataRepository."""
        # Setup repository mock
        mock_repository.get_data_range.return_value = {
            "exists": True,
            "start_date": datetime(2023, 1, 1),
            "end_date": datetime(2023, 12, 31),
            "rows": 365,
        }

        service = DataService()
        result = await service.get_data_range("AAPL", "1d")

        # Verify repository method was called
        mock_repository.get_data_range.assert_called_once_with("AAPL", "1d")

        # Verify result
        assert result["symbol"] == "AAPL"
        assert result["timeframe"] == "1d"
        assert result["point_count"] == 365

    @pytest.mark.asyncio
    async def test_get_data_range_not_found_uses_repository(self, mock_repository):
        """Verify get_data_range properly handles DataNotFoundError from repository."""
        # Setup repository mock to return non-existent data
        mock_repository.get_data_range.return_value = {"exists": False}

        service = DataService()

        with pytest.raises(DataNotFoundError):
            await service.get_data_range("INVALID", "1d")

        # Verify repository method was called
        mock_repository.get_data_range.assert_called_once()

    def test_load_cached_data_uses_repository(self, mock_repository):
        """Verify load_cached_data uses DataRepository."""
        # Setup repository mock
        sample_df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [95.0, 96.0],
                "close": [102.0, 103.0],
                "volume": [1000, 1100],
            },
            index=pd.date_range(start="2023-01-01", periods=2, freq="D"),
        )
        mock_repository.load_from_cache.return_value = sample_df

        service = DataService()
        result = service.load_cached_data("AAPL", "1d")

        # Verify repository method was called
        mock_repository.load_from_cache.assert_called_once_with(
            symbol="AAPL",
            timeframe="1d",
            start_date=None,
            end_date=None,
        )

        # Verify result is the DataFrame
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
