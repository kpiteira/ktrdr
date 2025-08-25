"""
Integration tests for DataProcessor component with DataManager.

Tests that DataProcessor integrates correctly with DataManager and maintains
the expected behavior while providing the extracted functionality.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch

from ktrdr.data.data_manager import DataManager
from ktrdr.data.components.data_processor import DataProcessor, ProcessorConfig


class TestDataProcessorIntegration:
    """Test DataProcessor integration with DataManager."""

    @pytest.fixture
    def data_manager(self):
        """Create DataManager instance for testing."""
        return DataManager(enable_ib=False)  # Disable IB for testing

    @pytest.fixture
    def valid_ohlc_data(self):
        """Create valid OHLC test data."""
        dates = pd.date_range(
            start="2023-01-01 09:30:00", periods=10, freq="1h", tz="UTC"
        )
        return pd.DataFrame(
            {
                "open": np.random.uniform(100, 110, 10),
                "high": np.random.uniform(110, 120, 10),
                "low": np.random.uniform(90, 100, 10),
                "close": np.random.uniform(100, 110, 10),
                "volume": np.random.randint(1000, 10000, 10),
            },
            index=dates,
        )

    def test_data_manager_has_data_processor(self, data_manager):
        """Test that DataManager initializes with DataProcessor."""
        assert hasattr(data_manager, "data_processor")
        assert isinstance(data_manager.data_processor, DataProcessor)

    def test_data_processor_config_integration(self, data_manager):
        """Test that DataProcessor is configured correctly."""
        processor = data_manager.data_processor
        config = processor.config

        # Should have reasonable defaults from DataManager
        assert config.remove_duplicates is True
        assert config.validate_ohlc is True
        assert config.timezone_conversion is True
        assert config.auto_correct is True

    def test_timezone_normalization_uses_processor(self, data_manager, valid_ohlc_data):
        """Test that timezone normalization delegates to DataProcessor."""
        # Create data with naive timestamps
        naive_data = valid_ohlc_data.copy()
        naive_data.index = naive_data.index.tz_localize(None)

        # DataManager's method should use DataProcessor internally
        result = data_manager._normalize_dataframe_timezone(naive_data)

        # Should have timezone-aware index
        assert result.index.tz is not None
        assert str(result.index.tz) == "UTC"

    def test_validation_uses_data_processor(self, data_manager):
        """Test that data validation uses DataProcessor."""
        # Mock data loading to test validation path
        with patch.object(data_manager, "_load_with_fallback") as mock_load:
            # Setup mock to return test data
            valid_data = pd.DataFrame(
                {
                    "open": [100, 105, 102],
                    "high": [102, 107, 104],
                    "low": [98, 103, 100],
                    "close": [101, 106, 103],
                    "volume": [1000, 1500, 1200],
                },
                index=pd.date_range(
                    "2023-01-01 09:30:00", periods=3, freq="1h", tz="UTC"
                ),
            )

            mock_load.return_value = valid_data

            # Load data with validation enabled
            result = data_manager.load_data(
                "TEST", "1h", validate=True, repair=True, progress_callback=None
            )

            # Should return processed data
            assert isinstance(result, pd.DataFrame)
            assert len(result) > 0

    def test_backward_compatibility_maintained(self, data_manager, valid_ohlc_data):
        """Test that DataManager API remains backward compatible."""
        # Test that existing method signatures work
        # Mock the local data loader to return our test data
        with patch.object(data_manager, "_load_with_fallback") as mock_load:
            mock_load.return_value = valid_ohlc_data

            # Test different parameter combinations that existed before
            result1 = data_manager.load_data("TEST", "1h", validate=False)
            result2 = data_manager.load_data("TEST", "1h", validate=True, repair=False)
            result3 = data_manager.load_data("TEST", "1h", validate=True, repair=True)

            # All should return DataFrames
            assert isinstance(result1, pd.DataFrame)
            assert isinstance(result2, pd.DataFrame)
            assert isinstance(result3, pd.DataFrame)

    def test_processor_error_handling_integration(self, data_manager):
        """Test that DataProcessor errors are handled properly in DataManager."""
        with patch.object(data_manager, "_load_with_fallback") as mock_load:
            # Create data that will cause validation issues
            invalid_data = pd.DataFrame(
                {
                    "open": [100, 105],
                    "high": [95, 107],  # high < open in first row
                    "low": [98, 103],
                    "close": [102, 106],
                    "volume": [1000, 1500],
                },
                index=pd.date_range(
                    "2023-01-01 09:30:00", periods=2, freq="1h", tz="UTC"
                ),
            )

            mock_load.return_value = invalid_data

            # Should handle validation errors gracefully
            result = data_manager.load_data(
                "TEST", "1h", validate=True, repair=True, progress_callback=None
            )

            # Should still return a DataFrame (corrected)
            assert isinstance(result, pd.DataFrame)

    @patch("ktrdr.data.data_manager.DataProcessor")
    def test_processor_initialization_called_correctly(
        self, mock_processor_class, data_manager
    ):
        """Test that DataProcessor is initialized with correct parameters."""
        # DataManager should have called DataProcessor constructor
        mock_processor_class.assert_called_once()

        # Check the config passed to DataProcessor
        call_args = mock_processor_class.call_args
        config = call_args[0][0]  # First argument should be ProcessorConfig

        assert config.remove_duplicates is True
        assert config.validate_ohlc is True
        assert config.timezone_conversion is True
        assert config.auto_correct is True

    def test_component_method_delegation(self, data_manager, valid_ohlc_data):
        """Test that DataManager properly delegates to DataProcessor methods."""
        processor = data_manager.data_processor

        # Test timezone normalization delegation
        naive_data = valid_ohlc_data.copy()
        naive_data.index = naive_data.index.tz_localize(None)

        # Both should produce same result
        dm_result = data_manager._normalize_dataframe_timezone(naive_data)
        processor_result = processor._normalize_dataframe_timezone(naive_data)

        pd.testing.assert_frame_equal(dm_result, processor_result)

    def test_processing_pipeline_integration(self, data_manager):
        """Test complete processing pipeline through DataManager."""
        # Create test data with known issues (duplicates, timezone problems)
        dates = pd.date_range(
            "2023-01-01 09:30:00", periods=5, freq="1h"
        )  # Naive timestamps
        dates = dates.insert(2, dates[1])  # Add duplicate

        test_data = pd.DataFrame(
            {
                "open": [100, 105, 105, 102, 108, 106],  # Duplicate values
                "high": [102, 107, 107, 104, 110, 108],
                "low": [98, 103, 103, 100, 106, 104],
                "close": [101, 106, 106, 103, 109, 107],
                "volume": [1000, 1500, 1500, 1200, 1800, 1300],
            },
            index=dates,
        )

        # Process through DataManager (which uses DataProcessor)
        with patch.object(data_manager, "_load_with_fallback") as mock_load:
            mock_load.return_value = test_data

            result = data_manager.load_data(
                "TEST", "1h", validate=True, repair=True, progress_callback=None
            )

            # Should have processed the data
            assert isinstance(result, pd.DataFrame)
            # Should have removed duplicates
            assert len(result) < len(test_data)
            # Should have timezone-aware index
            assert result.index.tz is not None
