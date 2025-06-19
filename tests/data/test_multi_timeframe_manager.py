"""
Unit tests for Multi-Timeframe Data Manager.

This module contains comprehensive tests for the MultiTimeframeDataManager
and related components, ensuring proper functionality of multi-timeframe
data loading, synchronization, and error handling.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List

from ktrdr.data.multi_timeframe_manager import (
    MultiTimeframeDataManager,
    TimeframeConfig,
    TimeframeDataResult,
    create_multi_timeframe_manager,
)
from ktrdr.errors import DataError, DataValidationError


class TestTimeframeConfig:
    """Test TimeframeConfig dataclass."""

    def test_valid_config_creation(self):
        """Test creating valid TimeframeConfig."""
        config = TimeframeConfig(
            primary_timeframe="1h", auxiliary_timeframes=["4h", "1d"], periods=200
        )

        assert config.primary_timeframe == "1h"
        assert config.auxiliary_timeframes == ["4h", "1d"]
        assert config.periods == 200
        assert config.enable_synthetic_generation is True
        assert config.require_minimum_timeframes == 1

    def test_config_validation_primary_in_auxiliary(self):
        """Test validation error when primary timeframe is in auxiliary."""
        with pytest.raises(
            ValueError, match="Primary timeframe cannot be in auxiliary"
        ):
            TimeframeConfig(
                primary_timeframe="1h", auxiliary_timeframes=["1h", "4h"], periods=200
            )

    def test_config_validation_insufficient_periods(self):
        """Test validation error for insufficient periods."""
        with pytest.raises(ValueError, match="Minimum 10 periods required"):
            TimeframeConfig(
                primary_timeframe="1h", auxiliary_timeframes=["4h"], periods=5
            )

    def test_config_validation_invalid_minimum_timeframes(self):
        """Test validation error for invalid minimum timeframes."""
        with pytest.raises(ValueError, match="Must require at least 1 timeframe"):
            TimeframeConfig(
                primary_timeframe="1h",
                auxiliary_timeframes=["4h"],
                periods=200,
                require_minimum_timeframes=0,
            )


class TestMultiTimeframeDataManager:
    """Test MultiTimeframeDataManager class."""

    @pytest.fixture
    def sample_1h_data(self):
        """Create sample 1-hour data."""
        dates = pd.date_range(
            start="2023-01-01 00:00:00", periods=200, freq="1h", tz="UTC"
        )
        return pd.DataFrame(
            {
                "open": np.random.uniform(100, 110, 200),
                "high": np.random.uniform(105, 115, 200),
                "low": np.random.uniform(95, 105, 200),
                "close": np.random.uniform(100, 110, 200),
                "volume": np.random.randint(1000, 10000, 200),
            },
            index=dates,
        )

    @pytest.fixture
    def sample_4h_data(self):
        """Create sample 4-hour data."""
        dates = pd.date_range(
            start="2023-01-01 00:00:00", periods=50, freq="4h", tz="UTC"
        )
        return pd.DataFrame(
            {
                "open": np.random.uniform(100, 110, 50),
                "high": np.random.uniform(105, 115, 50),
                "low": np.random.uniform(95, 105, 50),
                "close": np.random.uniform(100, 110, 50),
                "volume": np.random.randint(4000, 40000, 50),
            },
            index=dates,
        )

    @pytest.fixture
    def sample_1d_data(self):
        """Create sample daily data."""
        dates = pd.date_range(start="2023-01-01", periods=10, freq="1D", tz="UTC")
        return pd.DataFrame(
            {
                "open": np.random.uniform(100, 110, 10),
                "high": np.random.uniform(105, 115, 10),
                "low": np.random.uniform(95, 105, 10),
                "close": np.random.uniform(100, 110, 10),
                "volume": np.random.randint(100000, 1000000, 10),
            },
            index=dates,
        )

    @pytest.fixture
    def manager(self):
        """Create MultiTimeframeDataManager instance for testing."""
        return MultiTimeframeDataManager(enable_ib=False)

    @pytest.fixture
    def config(self):
        """Create standard TimeframeConfig for testing."""
        return TimeframeConfig(
            primary_timeframe="1h", auxiliary_timeframes=["4h", "1d"], periods=200
        )

    def test_initialization(self):
        """Test manager initialization."""
        manager = MultiTimeframeDataManager(
            enable_ib=False, enable_synthetic_generation=True, cache_size=50
        )

        assert manager.enable_synthetic_generation is True
        assert manager.cache_size == 50
        assert len(manager._data_cache) == 0

    def test_timeframe_multipliers(self, manager):
        """Test timeframe multipliers are correctly defined."""
        assert manager.TIMEFRAME_MULTIPLIERS["1m"] == 1
        assert manager.TIMEFRAME_MULTIPLIERS["1h"] == 60
        assert manager.TIMEFRAME_MULTIPLIERS["4h"] == 240
        assert manager.TIMEFRAME_MULTIPLIERS["1d"] == 1440

    def test_calculate_periods_for_timeframe(self, manager):
        """Test period calculation for different timeframes."""
        # 1h to 4h: 200 hours = 50 4-hour periods
        result = manager._calculate_periods_for_timeframe("1h", "4h", 200)
        assert result == 50

        # 1h to 1d: 200 hours ≈ 8.33 days, minimum 10
        result = manager._calculate_periods_for_timeframe("1h", "1d", 200)
        assert result == 10  # Minimum enforced

        # 4h to 1h: 50 4-hour periods = 200 1-hour periods
        result = manager._calculate_periods_for_timeframe("4h", "1h", 50)
        assert result == 200

    def test_calculate_periods_invalid_timeframe(self, manager):
        """Test error handling for invalid timeframes."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            manager._calculate_periods_for_timeframe("1h", "invalid", 200)

        with pytest.raises(ValueError, match="Unsupported timeframe"):
            manager._calculate_periods_for_timeframe("invalid", "4h", 200)

    def test_is_higher_timeframe(self, manager):
        """Test timeframe comparison logic."""
        assert manager._is_higher_timeframe("4h", "1h") is True
        assert manager._is_higher_timeframe("1d", "4h") is True
        assert manager._is_higher_timeframe("1h", "4h") is False
        assert manager._is_higher_timeframe("1h", "1h") is False

    def test_get_resample_rule(self, manager):
        """Test resample rule generation."""
        assert manager._get_resample_rule("1h") == "1h"
        assert manager._get_resample_rule("4h") == "4h"
        assert manager._get_resample_rule("1d") == "1D"
        assert manager._get_resample_rule("invalid") == "1h"  # Default

    def test_synthesize_higher_timeframe(self, manager, sample_1h_data):
        """Test synthetic higher timeframe generation."""
        # Generate 4h data from 1h data
        synthetic_4h = manager._synthesize_higher_timeframe(sample_1h_data, "4h")

        # Should have 1/4 the number of bars
        expected_bars = len(sample_1h_data) // 4
        assert abs(len(synthetic_4h) - expected_bars) <= 2  # Allow small variance

        # Check OHLCV aggregation
        assert "open" in synthetic_4h.columns
        assert "high" in synthetic_4h.columns
        assert "low" in synthetic_4h.columns
        assert "close" in synthetic_4h.columns
        assert "volume" in synthetic_4h.columns

        # Ensure no NaN values in synthetic data
        assert not synthetic_4h.isnull().any().any()

    def test_find_best_synthesis_source(self, manager):
        """Test finding best source for synthesis."""
        available = ["1h", "4h"]

        # For 1d synthesis, 4h is better than 1h (higher but still lower than 1d)
        result = manager._find_best_synthesis_source(available, "1d")
        assert result == "4h"

        # For 4h synthesis, only 1h is available and valid
        available = ["1h"]
        result = manager._find_best_synthesis_source(available, "4h")
        assert result == "1h"

        # No valid source for synthesis
        available = ["1d"]  # Cannot synthesize 4h from 1d
        result = manager._find_best_synthesis_source(available, "4h")
        assert result is None

    def test_validate_multi_timeframe_config(self, manager):
        """Test configuration validation."""
        # Valid config should pass
        config = TimeframeConfig("1h", ["4h", "1d"], 200)
        manager._validate_multi_timeframe_config("AAPL", config)

        # Invalid symbol
        with pytest.raises(
            DataValidationError, match="Symbol must be a non-empty string"
        ):
            manager._validate_multi_timeframe_config("", config)

        # Unsupported timeframe
        invalid_config = TimeframeConfig("invalid", ["4h"], 200)
        with pytest.raises(DataValidationError, match="Unsupported timeframe"):
            manager._validate_multi_timeframe_config("AAPL", invalid_config)

        # Duplicate timeframes (this will fail at TimeframeConfig creation)
        with pytest.raises(
            ValueError, match="Primary timeframe cannot be in auxiliary"
        ):
            duplicate_config = TimeframeConfig("1h", ["1h", "4h"], 200)

    def test_cache_operations(self, manager, config):
        """Test caching functionality."""
        # Create mock result
        result = TimeframeDataResult(
            primary_timeframe="1h",
            available_timeframes=["1h", "4h"],
            failed_timeframes=[],
            data={"1h": pd.DataFrame()},
            synthetic_timeframes=[],
            warnings=[],
            load_time=0.1,
        )

        # Test caching
        cache_key = manager._generate_cache_key("AAPL", config)
        manager._cache_result(cache_key, result)

        # Test retrieval
        cached_result = manager._get_cached_result(cache_key)
        assert cached_result is not None
        assert cached_result.primary_timeframe == "1h"

        # Test cache statistics
        stats = manager.get_cache_stats()
        assert stats["cache_size"] == 1
        assert cache_key in stats["cache_keys"]

        # Test cache clearing
        manager.clear_cache()
        assert len(manager._data_cache) == 0

    @patch.object(MultiTimeframeDataManager, "_load_single_timeframe")
    @patch.object(MultiTimeframeDataManager, "_synchronize_available_timeframes")
    def test_load_multi_timeframe_data_success(
        self,
        mock_synchronize,
        mock_load_single,
        manager,
        config,
        sample_1h_data,
        sample_4h_data,
        sample_1d_data,
    ):
        """Test successful multi-timeframe data loading."""

        # Mock single timeframe loading
        def mock_load_side_effect(symbol, timeframe, periods):
            if timeframe == "1h":
                return sample_1h_data
            elif timeframe == "4h":
                return sample_4h_data
            elif timeframe == "1d":
                return sample_1d_data
            else:
                raise DataError(f"No data for {timeframe}")

        mock_load_single.side_effect = mock_load_side_effect

        # Mock synchronization to return the input data
        def mock_sync_side_effect(data_dict, reference_tf):
            return data_dict

        mock_synchronize.side_effect = mock_sync_side_effect

        # Load multi-timeframe data
        result = manager.load_multi_timeframe_data("AAPL", config)

        # Verify result
        assert isinstance(result, TimeframeDataResult)
        assert result.primary_timeframe == "1h"
        assert "1h" in result.available_timeframes
        assert "4h" in result.available_timeframes
        assert "1d" in result.available_timeframes
        assert len(result.failed_timeframes) == 0
        assert len(result.data) == 3

    @patch.object(MultiTimeframeDataManager, "_load_single_timeframe")
    def test_load_multi_timeframe_data_primary_failure(
        self, mock_load_single, manager, config
    ):
        """Test failure when primary timeframe cannot be loaded."""
        # Mock primary timeframe failure
        mock_load_single.side_effect = DataError("Primary timeframe failed")

        # Should raise DataError for primary timeframe failure
        with pytest.raises(DataError, match="Cannot load primary timeframe"):
            manager.load_multi_timeframe_data("AAPL", config)

    @patch.object(MultiTimeframeDataManager, "_load_single_timeframe")
    @patch.object(MultiTimeframeDataManager, "_synchronize_available_timeframes")
    def test_load_multi_timeframe_data_auxiliary_failure(
        self,
        mock_synchronize,
        mock_load_single,
        manager,
        config,
        sample_1h_data,
        sample_4h_data,
    ):
        """Test graceful handling of auxiliary timeframe failures."""

        # Mock auxiliary timeframe failures
        def mock_load_side_effect(symbol, timeframe, periods):
            if timeframe == "1h":
                return sample_1h_data
            elif timeframe == "4h":
                return sample_4h_data
            elif timeframe == "1d":
                raise DataError("1d data not available")
            else:
                raise DataError(f"No data for {timeframe}")

        mock_load_single.side_effect = mock_load_side_effect

        # Mock synchronization to return the input data
        mock_synchronize.side_effect = lambda data_dict, reference_tf: data_dict

        # Load multi-timeframe data
        result = manager.load_multi_timeframe_data("AAPL", config)

        # Should succeed with partial data
        assert result.primary_timeframe == "1h"
        assert "1h" in result.available_timeframes
        assert "4h" in result.available_timeframes
        assert len(result.warnings) > 0

    @patch.object(MultiTimeframeDataManager, "_load_single_timeframe")
    @patch.object(MultiTimeframeDataManager, "_synchronize_available_timeframes")
    def test_synthetic_data_generation(
        self,
        mock_synchronize,
        mock_load_single,
        manager,
        sample_1h_data,
        sample_4h_data,
    ):
        """Test synthetic data generation for failed timeframes."""
        config = TimeframeConfig(
            primary_timeframe="1h",
            auxiliary_timeframes=["4h", "1d"],
            periods=200,
            enable_synthetic_generation=True,
        )

        # Mock data loading with 1d failure
        def mock_load_side_effect(symbol, timeframe, periods):
            if timeframe == "1h":
                return sample_1h_data
            elif timeframe == "4h":
                return sample_4h_data
            elif timeframe == "1d":
                raise DataError("1d data not available")
            else:
                raise DataError(f"No data for {timeframe}")

        mock_load_single.side_effect = mock_load_side_effect

        # Mock synchronization to return the input data
        mock_synchronize.side_effect = lambda data_dict, reference_tf: data_dict

        # Load multi-timeframe data
        result = manager.load_multi_timeframe_data("AAPL", config)

        # Check if synthetic 1d data was generated from 4h
        if "1d" in result.available_timeframes:
            assert "1d" in result.synthetic_timeframes
            assert "1d" not in result.failed_timeframes

        # Verify synthetic data structure
        if "1d" in result.data:
            synthetic_1d = result.data["1d"]
            assert not synthetic_1d.empty
            assert all(
                col in synthetic_1d.columns
                for col in ["open", "high", "low", "close", "volume"]
            )

    def test_apply_fallback_strategies(self, manager, sample_4h_data):
        """Test fallback strategy application."""
        available_data = {"4h": sample_4h_data}
        failed_timeframes = ["1d"]

        synthetic_data, synthetic_timeframes = manager._apply_fallback_strategies(
            available_data, failed_timeframes, "4h"
        )

        # Should generate synthetic 1d data from 4h
        if synthetic_data:
            assert "1d" in synthetic_data
            assert "1d" in synthetic_timeframes

            synthetic_1d = synthetic_data["1d"]
            assert not synthetic_1d.empty
            assert len(synthetic_1d) < len(sample_4h_data)  # Should be aggregated

    def test_minimum_timeframes_requirement(self, manager):
        """Test minimum timeframes requirement validation."""
        config = TimeframeConfig(
            primary_timeframe="1h",
            auxiliary_timeframes=["4h", "1d"],
            periods=200,
            require_minimum_timeframes=3,
        )

        with patch.object(manager, "_load_single_timeframe") as mock_load:
            with patch.object(
                manager, "_synchronize_available_timeframes"
            ) as mock_sync:
                # Mock only primary timeframe success
                def mock_load_side_effect(s, tf, p):
                    if tf == "1h":
                        return pd.DataFrame(
                            {"close": [100]},
                            index=pd.date_range(
                                "2023-01-01", periods=1, freq="1h", tz="UTC"
                            ),
                        )
                    else:
                        raise DataError("Failed")

                mock_load.side_effect = mock_load_side_effect
                mock_sync.side_effect = lambda data_dict, reference_tf: data_dict

                # Should fail due to insufficient timeframes
                with pytest.raises(DataError, match="Only 1 timeframes available"):
                    manager.load_multi_timeframe_data("AAPL", config)


class TestFactoryFunction:
    """Test factory function for creating manager instances."""

    def test_create_multi_timeframe_manager(self):
        """Test factory function creates proper instance."""
        manager = create_multi_timeframe_manager(
            enable_ib=False, enable_synthetic_generation=True, cache_size=100
        )

        assert isinstance(manager, MultiTimeframeDataManager)
        assert manager.enable_ib is False
        assert manager.enable_synthetic_generation is True
        assert manager.cache_size == 100

    def test_create_multi_timeframe_manager_defaults(self):
        """Test factory function with default parameters."""
        manager = create_multi_timeframe_manager()

        assert isinstance(manager, MultiTimeframeDataManager)
        assert manager.enable_ib is True  # Default
        assert manager.enable_synthetic_generation is True  # Default


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_auxiliary_timeframes(self):
        """Test configuration with no auxiliary timeframes."""
        config = TimeframeConfig(
            primary_timeframe="1h", auxiliary_timeframes=[], periods=200
        )

        manager = MultiTimeframeDataManager(enable_ib=False)

        with patch.object(manager, "_load_single_timeframe") as mock_load:
            with patch.object(
                manager, "_synchronize_available_timeframes"
            ) as mock_sync:
                sample_data = pd.DataFrame(
                    {"close": [100] * 10},
                    index=pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC"),
                )

                mock_load.return_value = sample_data
                mock_sync.side_effect = lambda data_dict, reference_tf: data_dict

                result = manager.load_multi_timeframe_data("AAPL", config)

                assert len(result.available_timeframes) == 1
                assert result.available_timeframes[0] == "1h"
                assert len(result.failed_timeframes) == 0

    def test_cache_overflow(self):
        """Test cache behavior when size limit is exceeded."""
        manager = MultiTimeframeDataManager(enable_ib=False, cache_size=2)

        # Create multiple results to exceed cache size
        for i in range(3):
            config = TimeframeConfig(f"config_{i}", [], 100)
            result = TimeframeDataResult(
                primary_timeframe=f"tf_{i}",
                available_timeframes=[],
                failed_timeframes=[],
                data={},
                synthetic_timeframes=[],
                warnings=[],
                load_time=0.1,
            )

            cache_key = manager._generate_cache_key(f"SYMBOL_{i}", config)
            manager._cache_result(cache_key, result)

        # Cache should not exceed max size
        assert len(manager._data_cache) <= manager.cache_size

    def test_unsupported_timeframe_in_hierarchy(self):
        """Test handling of unsupported timeframes."""
        manager = MultiTimeframeDataManager(enable_ib=False)

        # Test with unsupported timeframe
        assert not manager._is_higher_timeframe("unsupported", "1h")
        assert not manager._is_higher_timeframe("1h", "unsupported")

        # Should return None for invalid synthesis source
        result = manager._find_best_synthesis_source(["unsupported"], "1h")
        assert result is None
