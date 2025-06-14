"""
Tests for the enhanced FuzzyService with batch overlay functionality.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from ktrdr.api.services.fuzzy_service import FuzzyService
from ktrdr.fuzzy.config import FuzzyConfigLoader
from ktrdr.errors import DataError, ConfigurationError, ProcessingError


@pytest.fixture
def sample_fuzzy_config():
    """Create a sample fuzzy configuration for testing."""
    config_dict = {
        "rsi": {
            "low": {"type": "triangular", "parameters": [0.0, 0.0, 50.0]},
            "neutral": {"type": "triangular", "parameters": [20.0, 50.0, 80.0]},
            "high": {"type": "triangular", "parameters": [50.0, 100.0, 100.0]},
        },
        "macd": {
            "negative": {"type": "triangular", "parameters": [-10.0, -10.0, 0.0]},
            "positive": {"type": "triangular", "parameters": [0.0, 10.0, 10.0]},
        },
    }
    return FuzzyConfigLoader.load_from_dict(config_dict)


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="1h")
    np.random.seed(42)  # For reproducible tests

    # Generate realistic OHLCV data
    close_prices = 100 + np.cumsum(np.random.randn(100) * 0.1)

    data = {
        "open": close_prices + np.random.randn(100) * 0.05,
        "high": close_prices + np.abs(np.random.randn(100) * 0.1),
        "low": close_prices - np.abs(np.random.randn(100) * 0.1),
        "close": close_prices,
        "volume": np.random.randint(1000, 10000, 100),
    }

    return pd.DataFrame(data, index=dates)


@pytest.fixture
def sample_rsi_data():
    """Create sample RSI indicator data."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="1h")
    # Create RSI values that vary across different fuzzy regions
    rsi_values = (
        50 + 30 * np.sin(np.linspace(0, 4 * np.pi, 100)) + np.random.randn(100) * 5
    )
    rsi_values = np.clip(rsi_values, 0, 100)  # Ensure RSI is in valid range

    return pd.Series(rsi_values, index=dates, name="rsi")


class TestFuzzyServiceEnhanced:
    """Test cases for enhanced FuzzyService with overlay functionality."""

    @patch("ktrdr.api.services.fuzzy_service.FuzzyConfigLoader")
    @patch("ktrdr.api.services.fuzzy_service.DataManager")
    @patch("ktrdr.api.services.fuzzy_service.IndicatorEngine")
    def test_initialization_with_batch_calculator(
        self,
        mock_indicator_engine,
        mock_data_manager,
        mock_config_loader,
        sample_fuzzy_config,
    ):
        """Test that FuzzyService initializes with BatchFuzzyCalculator."""
        # Configure mocks
        mock_config_loader.return_value.load_from_yaml.return_value = (
            sample_fuzzy_config
        )

        # Initialize service
        service = FuzzyService(config_path="test_config.yaml")

        # Verify initialization
        assert service.fuzzy_engine is not None
        assert service.batch_calculator is not None
        assert hasattr(service, "data_manager")
        assert hasattr(service, "indicator_engine")

    @pytest.mark.asyncio
    @patch("ktrdr.api.services.fuzzy_service.FuzzyConfigLoader")
    async def test_get_fuzzy_overlays_basic(
        self,
        mock_config_loader,
        sample_fuzzy_config,
        sample_ohlcv_data,
        sample_rsi_data,
    ):
        """Test basic fuzzy overlay generation."""
        # Configure mocks
        mock_config_loader.return_value.load_from_yaml.return_value = (
            sample_fuzzy_config
        )

        service = FuzzyService(config_path="test_config.yaml")

        # Mock data loading (DataManager.load is sync, not async)
        service.data_manager.load = Mock(return_value=sample_ohlcv_data)

        # Mock indicator calculation to return RSI data
        service._get_indicator_values = AsyncMock(return_value=sample_rsi_data)

        # Call the method
        result = await service.get_fuzzy_overlays(
            symbol="AAPL", timeframe="1h", indicators=["rsi"]
        )

        # Verify response structure
        assert "symbol" in result
        assert "timeframe" in result
        assert "data" in result
        assert result["symbol"] == "AAPL"
        assert result["timeframe"] == "1h"

        # Verify RSI fuzzy data structure
        assert "rsi" in result["data"]
        rsi_data = result["data"]["rsi"]
        assert isinstance(rsi_data, list)

        # Check fuzzy sets
        set_names = [fs["set"] for fs in rsi_data]
        assert "low" in set_names
        assert "neutral" in set_names
        assert "high" in set_names

        # Verify membership data structure
        for fuzzy_set in rsi_data:
            assert "set" in fuzzy_set
            assert "membership" in fuzzy_set
            assert isinstance(fuzzy_set["membership"], list)

            # Check membership points structure
            if fuzzy_set["membership"]:
                point = fuzzy_set["membership"][0]
                assert "timestamp" in point
                assert "value" in point
                assert isinstance(point["value"], (float, type(None)))

    @pytest.mark.asyncio
    @patch("ktrdr.api.services.fuzzy_service.FuzzyConfigLoader")
    async def test_get_fuzzy_overlays_uninitialized_engine(self, mock_config_loader):
        """Test error handling when fuzzy engine is not initialized."""
        mock_config_loader.return_value.load_from_yaml.side_effect = Exception(
            "Config load failed"
        )

        service = FuzzyService(config_path="test_config.yaml")

        # Engine should be None due to initialization failure
        assert service.fuzzy_engine is None
        assert service.batch_calculator is None

        # Should raise ConfigurationError
        with pytest.raises(ConfigurationError) as exc_info:
            await service.get_fuzzy_overlays(
                symbol="AAPL", timeframe="1h", indicators=["rsi"]
            )

        assert "Fuzzy engine is not initialized" in str(exc_info.value)
        assert exc_info.value.error_code == "CONFIG-FuzzyEngineNotInitialized"
