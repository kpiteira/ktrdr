"""
Integration tests for DataRepository.

These tests validate the integration between:
- DataRepository
- LocalDataLoader (file I/O)
- DataQualityValidator (validation)
- Real filesystem operations

Integration tests are slower than unit tests but validate real component interactions.
"""

import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from ktrdr.data.repository import DataRepository
from ktrdr.errors import DataNotFoundError

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def integration_data_dir(tmp_path):
    """Create a temporary data directory for integration testing."""
    data_dir = tmp_path / "integration_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def sample_ohlcv_data():
    """Create realistic OHLCV data for integration testing."""
    dates = pd.date_range("2024-01-01", periods=1000, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0 + i * 0.1 for i in range(1000)],
            "high": [101.0 + i * 0.1 for i in range(1000)],
            "low": [99.0 + i * 0.1 for i in range(1000)],
            "close": [100.5 + i * 0.1 for i in range(1000)],
            "volume": [1000 + i * 10 for i in range(1000)],
        },
        index=dates,
    )


class TestDataRepositoryIntegration:
    """Integration tests for DataRepository with real file I/O."""

    def test_full_save_load_cycle(self, integration_data_dir, sample_ohlcv_data):
        """Test complete save-to-disk and load-from-disk cycle."""
        # Initialize repository
        repo = DataRepository(data_dir=str(integration_data_dir))

        # Save data to disk
        repo.save_to_cache("AAPL", "1h", sample_ohlcv_data)

        # Verify file was created on disk
        csv_file = integration_data_dir / "AAPL_1h.csv"
        assert csv_file.exists()
        assert csv_file.stat().st_size > 0

        # Load data back from disk
        loaded_data = repo.load_from_cache("AAPL", "1h")

        # Verify data integrity
        assert len(loaded_data) == 1000
        assert list(loaded_data.columns) == ["open", "high", "low", "close", "volume"]
        assert isinstance(loaded_data.index, pd.DatetimeIndex)

        # Verify data values match (compare values, not index frequency)
        pd.testing.assert_frame_equal(
            loaded_data.sort_index().reset_index(drop=True),
            sample_ohlcv_data.sort_index().reset_index(drop=True),
            check_dtype=False,  # Allow minor dtype differences
        )

    def test_multiple_symbols_isolation(self, integration_data_dir, sample_ohlcv_data):
        """Test that multiple symbols are properly isolated on disk."""
        repo = DataRepository(data_dir=str(integration_data_dir))

        # Save data for multiple symbols
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN"]
        for symbol in symbols:
            repo.save_to_cache(symbol, "1h", sample_ohlcv_data)

        # Verify each has its own file
        for symbol in symbols:
            csv_file = integration_data_dir / f"{symbol}_1h.csv"
            assert csv_file.exists()

        # Verify get_available_symbols returns all symbols
        available = repo.get_available_symbols()
        assert sorted(available) == sorted(symbols)

        # Verify each can be loaded independently
        for symbol in symbols:
            data = repo.load_from_cache(symbol, "1h")
            assert len(data) == 1000

    def test_multiple_timeframes_same_symbol(
        self, integration_data_dir, sample_ohlcv_data
    ):
        """Test that multiple timeframes for same symbol are isolated."""
        repo = DataRepository(data_dir=str(integration_data_dir))

        timeframes = ["1m", "5m", "1h", "1d"]

        # Save same symbol with different timeframes
        for tf in timeframes:
            repo.save_to_cache("AAPL", tf, sample_ohlcv_data)

        # Verify each has its own file
        for tf in timeframes:
            csv_file = integration_data_dir / f"AAPL_{tf}.csv"
            assert csv_file.exists()

        # Verify each can be loaded independently
        for tf in timeframes:
            data = repo.load_from_cache("AAPL", tf)
            assert len(data) == 1000

    def test_date_range_filtering_integration(
        self, integration_data_dir, sample_ohlcv_data
    ):
        """Test date range filtering with real file I/O."""
        repo = DataRepository(data_dir=str(integration_data_dir))

        # Save full dataset
        repo.save_to_cache("AAPL", "1h", sample_ohlcv_data)

        # Load with various date ranges
        start_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 20, tzinfo=timezone.utc)

        filtered_data = repo.load_from_cache(
            "AAPL", "1h", start_date=start_date, end_date=end_date
        )

        # Verify filtering worked
        assert filtered_data.index[0] >= start_date
        assert filtered_data.index[-1] <= end_date
        assert len(filtered_data) < len(sample_ohlcv_data)

    def test_data_persistence_across_repository_instances(
        self, integration_data_dir, sample_ohlcv_data
    ):
        """Test that data persists across repository instances."""
        # First instance: save data
        repo1 = DataRepository(data_dir=str(integration_data_dir))
        repo1.save_to_cache("AAPL", "1h", sample_ohlcv_data)

        # Second instance: load data
        repo2 = DataRepository(data_dir=str(integration_data_dir))
        loaded_data = repo2.load_from_cache("AAPL", "1h")

        # Verify data persisted
        assert len(loaded_data) == 1000
        pd.testing.assert_frame_equal(
            loaded_data.sort_index().reset_index(drop=True),
            sample_ohlcv_data.sort_index().reset_index(drop=True),
            check_dtype=False,
        )

    def test_overwrite_behavior(self, integration_data_dir, sample_ohlcv_data):
        """Test that saving overwrites existing data correctly."""
        repo = DataRepository(data_dir=str(integration_data_dir))

        # Save original data
        repo.save_to_cache("AAPL", "1h", sample_ohlcv_data)

        # Modify data
        modified_data = sample_ohlcv_data.copy()
        modified_data["close"] = modified_data["close"] * 2

        # Save modified data (should overwrite)
        repo.save_to_cache("AAPL", "1h", modified_data)

        # Load and verify it was overwritten
        loaded_data = repo.load_from_cache("AAPL", "1h")
        assert loaded_data["close"].iloc[0] == modified_data["close"].iloc[0]
        assert loaded_data["close"].iloc[0] != sample_ohlcv_data["close"].iloc[0]

    def test_get_data_range_integration(self, integration_data_dir, sample_ohlcv_data):
        """Test get_data_range with real file I/O."""
        repo = DataRepository(data_dir=str(integration_data_dir))

        # Save data
        repo.save_to_cache("AAPL", "1h", sample_ohlcv_data)

        # Get range info
        range_info = repo.get_data_range("AAPL", "1h")

        # Verify range info
        assert range_info["symbol"] == "AAPL"
        assert range_info["timeframe"] == "1h"
        assert range_info["rows"] == 1000
        assert range_info["exists"] is True
        assert range_info["start_date"] == sample_ohlcv_data.index[0]
        assert range_info["end_date"] == sample_ohlcv_data.index[-1]

    def test_delete_from_cache_integration(
        self, integration_data_dir, sample_ohlcv_data
    ):
        """Test delete_from_cache with real file deletion."""
        repo = DataRepository(data_dir=str(integration_data_dir))

        # Save data
        repo.save_to_cache("AAPL", "1h", sample_ohlcv_data)

        # Verify file exists
        csv_file = integration_data_dir / "AAPL_1h.csv"
        assert csv_file.exists()

        # Delete
        result = repo.delete_from_cache("AAPL", "1h")
        assert result is True

        # Verify file is gone
        assert not csv_file.exists()

        # Verify load now fails
        with pytest.raises(DataNotFoundError):
            repo.load_from_cache("AAPL", "1h")

    def test_cache_stats_integration(self, integration_data_dir, sample_ohlcv_data):
        """Test get_cache_stats with real files."""
        repo = DataRepository(data_dir=str(integration_data_dir))

        # Initially empty
        stats = repo.get_cache_stats()
        assert stats["total_files"] == 0
        assert stats["unique_symbols"] == 0

        # Add some data
        symbols = ["AAPL", "MSFT", "GOOGL"]
        timeframes = ["1h", "1d"]

        for symbol in symbols:
            for tf in timeframes:
                repo.save_to_cache(symbol, tf, sample_ohlcv_data)

        # Check stats
        stats = repo.get_cache_stats()
        assert stats["total_files"] == 6  # 3 symbols * 2 timeframes
        assert stats["unique_symbols"] == 3
        assert stats["data_directory"] == str(integration_data_dir)

    def test_performance_large_dataset(self, integration_data_dir):
        """Test performance with larger dataset (10K rows)."""
        # Create large dataset (use 1m for valid timeframe)
        dates = pd.date_range("2024-01-01", periods=10000, freq="1min", tz="UTC")
        large_data = pd.DataFrame(
            {
                "open": [100.0 + i * 0.01 for i in range(10000)],
                "high": [101.0 + i * 0.01 for i in range(10000)],
                "low": [99.0 + i * 0.01 for i in range(10000)],
                "close": [100.5 + i * 0.01 for i in range(10000)],
                "volume": [1000 + i for i in range(10000)],
            },
            index=dates,
        )

        repo = DataRepository(data_dir=str(integration_data_dir))

        # Time save operation (use "1m" for valid timeframe)
        start_save = time.time()
        repo.save_to_cache("PERF_TEST", "1m", large_data)
        save_time = time.time() - start_save

        # Time load operation
        start_load = time.time()
        loaded_data = repo.load_from_cache("PERF_TEST", "1m")
        load_time = time.time() - start_load

        # Verify data
        assert len(loaded_data) == 10000

        # Performance assertions (generous for integration tests)
        assert save_time < 2.0  # Should save 10K rows in <2s
        assert load_time < 2.0  # Should load 10K rows in <2s

        print(f"\nPerformance: Save={save_time:.3f}s, Load={load_time:.3f}s (10K rows)")

    def test_concurrent_access_safety(self, integration_data_dir, sample_ohlcv_data):
        """Test that repository handles concurrent access safely."""
        repo = DataRepository(data_dir=str(integration_data_dir))

        # Save initial data
        repo.save_to_cache("AAPL", "1h", sample_ohlcv_data)

        # Multiple reads should work (file system allows this)
        data1 = repo.load_from_cache("AAPL", "1h")
        data2 = repo.load_from_cache("AAPL", "1h")

        assert len(data1) == len(data2)
        pd.testing.assert_frame_equal(data1, data2)

    def test_edge_case_empty_directory_creation(self, tmp_path):
        """Test that repository creates nested directories as needed."""
        deep_path = tmp_path / "level1" / "level2" / "level3" / "data"

        # Should create all directories
        repo = DataRepository(data_dir=str(deep_path))

        # Verify directories were created
        assert deep_path.exists()
        assert deep_path.is_dir()

    def test_real_world_workflow(self, integration_data_dir):
        """Test realistic workflow: fetch → save → query → update → query."""
        repo = DataRepository(data_dir=str(integration_data_dir))

        # Step 1: Simulate initial data fetch and save
        initial_dates = pd.date_range("2024-01-01", periods=100, freq="1d", tz="UTC")
        initial_data = pd.DataFrame(
            {
                "open": range(100, 200),
                "high": range(105, 205),
                "low": range(95, 195),
                "close": range(102, 202),
                "volume": range(1000, 1100),
            },
            index=initial_dates,
        )
        repo.save_to_cache("AAPL", "1d", initial_data)

        # Step 2: Query date range
        range_info = repo.get_data_range("AAPL", "1d")
        assert range_info["rows"] == 100

        # Step 3: Simulate update with more recent data
        update_dates = pd.date_range("2024-01-01", periods=150, freq="1d", tz="UTC")
        updated_data = pd.DataFrame(
            {
                "open": range(100, 250),
                "high": range(105, 255),
                "low": range(95, 245),
                "close": range(102, 252),
                "volume": range(1000, 1150),
            },
            index=update_dates,
        )
        repo.save_to_cache("AAPL", "1d", updated_data)

        # Step 4: Query again - should have updated data
        new_range_info = repo.get_data_range("AAPL", "1d")
        assert new_range_info["rows"] == 150

        # Step 5: Query with date filter
        filtered = repo.load_from_cache(
            "AAPL",
            "1d",
            start_date=datetime(2024, 2, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        assert len(filtered) > 0
        assert len(filtered) < 150
