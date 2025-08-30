"""
Unit tests for FuzzyService.

Tests the fuzzy service layer that adapts the core fuzzy logic modules for API use.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from ktrdr.api.services.fuzzy_service import FuzzyService
from ktrdr.errors import ConfigurationError, DataError, ProcessingError
from ktrdr.fuzzy.config import FuzzyConfig


@pytest.fixture
def mock_fuzzy_engine():
    """Create a mock FuzzyEngine for testing the service."""
    with patch("ktrdr.api.services.fuzzy_service.FuzzyEngine") as mock_engine:
        mock_instance = MagicMock()
        mock_engine.return_value = mock_instance

        # Mock available indicators
        mock_instance.get_available_indicators.return_value = ["rsi", "macd", "bb"]

        # Mock getting fuzzy sets for indicators
        mock_instance.get_fuzzy_sets.side_effect = lambda indicator: {
            "rsi": ["low", "medium", "high"],
            "macd": ["negative", "zero", "positive"],
            "bb": ["lower", "middle", "upper"],
        }.get(indicator, [])

        # Mock getting output names
        mock_instance.get_output_names.side_effect = lambda indicator: [
            f"{indicator}_{s}"
            for s in {
                "rsi": ["low", "medium", "high"],
                "macd": ["negative", "zero", "positive"],
                "bb": ["lower", "middle", "upper"],
            }.get(indicator, [])
        ]

        # Mock fuzzify method
        def mock_fuzzify(indicator, values):
            if indicator not in ["rsi", "macd", "bb"]:
                raise ProcessingError(
                    message=f"Unknown indicator: {indicator}",
                    error_code="ENGINE-UnknownIndicator",
                    details={"indicator": indicator},
                )

            # Create a dataframe with fuzzified values
            if isinstance(values, pd.Series):
                index = values.index
                length = len(values)
            else:
                index = pd.RangeIndex(len(values) if hasattr(values, "__len__") else 1)
                length = len(index)

            result = {}
            fuzzy_sets = {
                "rsi": ["low", "medium", "high"],
                "macd": ["negative", "zero", "positive"],
                "bb": ["lower", "middle", "upper"],
            }.get(indicator, [])

            for fuzzy_set in fuzzy_sets:
                output_name = f"{indicator}_{fuzzy_set}"
                # Generate some dummy fuzzified values
                result[output_name] = np.random.random(length)

            return pd.DataFrame(result, index=index)

        mock_instance.fuzzify.side_effect = mock_fuzzify

        yield mock_instance


@pytest.fixture
def mock_config_loader():
    """Create a mock FuzzyConfigLoader for testing the service."""
    with patch(
        "ktrdr.api.services.fuzzy_service.FuzzyConfigLoader"
    ) as mock_loader_class:
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader

        # Mock the config
        mock_config = MagicMock(spec=FuzzyConfig)

        # Set up root dictionary with indicators and fuzzy sets
        mock_config.root = {"rsi": MagicMock(), "macd": MagicMock(), "bb": MagicMock()}

        # Mock fuzzy set configs for each indicator
        for indicator in mock_config.root:
            mock_indicator_config = mock_config.root[indicator]

            # Set up fuzzy sets for this indicator
            fuzzy_sets = {
                "rsi": ["low", "medium", "high"],
                "macd": ["negative", "zero", "positive"],
                "bb": ["lower", "middle", "upper"],
            }.get(indicator, [])

            mock_indicator_config.root = {
                fuzzy_set: MagicMock() for fuzzy_set in fuzzy_sets
            }

            # Configure each fuzzy set
            for _fuzzy_set, config in mock_indicator_config.root.items():
                config.type = "triangular"
                config.parameters = [0.0, 0.5, 1.0]  # Dummy parameters

        # Set up loader methods to return the mock config
        mock_loader.load_from_yaml.return_value = mock_config
        mock_loader.load_default.return_value = mock_config

        yield mock_loader


@pytest.fixture
def mock_data_manager():
    """Create a mock DataManager for testing the service."""
    with patch("ktrdr.api.services.fuzzy_service.DataManager") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance

        # Create sample DataFrame for load method
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [95.0, 96.0, 97.0],
                "close": [102.0, 103.0, 104.0],
                "volume": [1000, 1100, 1200],
            },
            index=pd.date_range(start="2023-01-01", periods=3, freq="D"),
        )

        # Set up mock to return sample DataFrame
        mock_instance.load.return_value = df

        yield mock_instance


@pytest.mark.api
def test_init_with_defaults(mock_config_loader, mock_fuzzy_engine):
    """Test that FuzzyService can be initialized with default values."""
    service = FuzzyService()
    assert service is not None
    # Verify that load_default was called
    mock_config_loader.load_default.assert_called_once()


@pytest.mark.api
def test_init_with_config_path(mock_config_loader, mock_fuzzy_engine):
    """Test that FuzzyService can be initialized with a config path."""
    service = FuzzyService(config_path="config/fuzzy.yaml")
    assert service is not None
    # Verify that load_from_yaml was called with the path
    mock_config_loader.load_from_yaml.assert_called_once_with("config/fuzzy.yaml")


@pytest.mark.api
def test_init_handles_exception():
    """Test that FuzzyService gracefully handles initialization exceptions."""
    with (
        patch(
            "ktrdr.api.services.fuzzy_service.FuzzyConfigLoader"
        ) as mock_loader_class,
        patch("ktrdr.api.services.fuzzy_service.FuzzyConfig") as mock_config_class,
    ):
        # Mock the loader to raise an exception
        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load_default.side_effect = Exception("Test error")

        # Mock FuzzyConfig to avoid validation errors
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        # Should not raise an exception, but create an empty config and a None engine
        service = FuzzyService()
        assert service is not None
        assert service.fuzzy_engine is None


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_available_indicators(mock_fuzzy_engine, mock_config_loader):
    """Test retrieval of available indicators."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine

    result = await service.get_available_indicators()

    # Verify result
    assert isinstance(result, list)
    assert len(result) == 3  # rsi, macd, bb

    # Check structure of indicator info
    for indicator_info in result:
        assert "id" in indicator_info
        assert "name" in indicator_info
        assert "fuzzy_sets" in indicator_info
        assert "output_columns" in indicator_info

    # Verify the mock was called
    mock_fuzzy_engine.get_available_indicators.assert_called_once()


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_available_indicators_no_engine(mock_config_loader):
    """Test handling of no fuzzy engine in get_available_indicators."""
    service = FuzzyService()
    service.fuzzy_engine = None

    # Should return empty list, not raise exception
    result = await service.get_available_indicators()
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_fuzzy_sets(mock_fuzzy_engine, mock_config_loader):
    """Test retrieval of fuzzy sets for an indicator."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine
    service.config = mock_config_loader.load_default()

    result = await service.get_fuzzy_sets("rsi")

    # Verify result
    assert isinstance(result, dict)
    assert len(result) == 3  # low, medium, high

    # Check structure of fuzzy set info
    for _set_name, set_info in result.items():
        assert "type" in set_info
        assert "parameters" in set_info

    # Verify the mock was called
    mock_fuzzy_engine.get_fuzzy_sets.assert_called_once_with("rsi")


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_fuzzy_sets_no_engine(mock_config_loader):
    """Test handling of no fuzzy engine in get_fuzzy_sets."""
    service = FuzzyService()
    service.fuzzy_engine = None

    # Should raise ConfigurationError
    with pytest.raises(ConfigurationError) as excinfo:
        await service.get_fuzzy_sets("rsi")

    assert "Fuzzy engine is not initialized" in str(excinfo.value)


@pytest.mark.api
@pytest.mark.asyncio
async def test_get_fuzzy_sets_unknown_indicator(mock_fuzzy_engine, mock_config_loader):
    """Test handling of unknown indicator in get_fuzzy_sets."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine
    service.config = mock_config_loader.load_default()

    # Setup mock to raise for unknown indicator
    mock_fuzzy_engine.get_fuzzy_sets.side_effect = lambda indicator: {
        "rsi": ["low", "medium", "high"],
        "macd": ["negative", "zero", "positive"],
        "bb": ["lower", "middle", "upper"],
    }.get(indicator, [])
    mock_fuzzy_engine.get_available_indicators.return_value = ["rsi", "macd", "bb"]

    # Should raise ConfigurationError
    with pytest.raises(ConfigurationError) as excinfo:
        await service.get_fuzzy_sets("unknown")

    assert "Unknown fuzzy indicator" in str(excinfo.value)


@pytest.mark.api
@pytest.mark.asyncio
async def test_fuzzify_indicator(mock_fuzzy_engine, mock_config_loader):
    """Test fuzzification of indicator values."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine

    # Test with normal values
    values = [30.0, 45.0, 70.0]
    result = await service.fuzzify_indicator("rsi", values)

    # Verify result structure
    assert isinstance(result, dict)
    assert "indicator" in result
    assert "fuzzy_sets" in result
    assert "values" in result
    assert "points" in result

    # Check values
    assert result["indicator"] == "rsi"
    assert isinstance(result["values"], dict)
    assert len(result["values"]) == 3  # rsi_low, rsi_medium, rsi_high
    assert result["points"] == 3

    # Verify the mock was called
    mock_fuzzy_engine.fuzzify.assert_called_once()


@pytest.mark.api
@pytest.mark.asyncio
async def test_fuzzify_indicator_with_dates(mock_fuzzy_engine, mock_config_loader):
    """Test fuzzification with dates."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine

    # Test with values and dates
    values = [30.0, 45.0, 70.0]
    dates = ["2023-01-01", "2023-01-02", "2023-01-03"]
    result = await service.fuzzify_indicator("rsi", values, dates)

    # Verify result structure
    assert isinstance(result, dict)
    assert "values" in result
    assert len(result["values"]) == 3  # rsi_low, rsi_medium, rsi_high

    # Verify the mock was called with dates
    args, kwargs = mock_fuzzy_engine.fuzzify.call_args
    assert isinstance(args[1], pd.Series)
    assert len(args[1]) == 3


@pytest.mark.api
@pytest.mark.asyncio
async def test_fuzzify_indicator_no_engine(mock_config_loader):
    """Test handling of no fuzzy engine in fuzzify_indicator."""
    service = FuzzyService()
    service.fuzzy_engine = None

    # Should raise ConfigurationError
    with pytest.raises(ConfigurationError) as excinfo:
        await service.fuzzify_indicator("rsi", [30.0, 45.0, 70.0])

    assert "Fuzzy engine is not initialized" in str(excinfo.value)


@pytest.mark.api
@pytest.mark.asyncio
async def test_fuzzify_indicator_unknown_indicator(
    mock_fuzzy_engine, mock_config_loader
):
    """Test handling of unknown indicator in fuzzify_indicator."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine

    # Set up mock to fail for unknown indicator
    mock_fuzzy_engine.get_available_indicators.return_value = ["rsi", "macd", "bb"]

    # Should raise ConfigurationError
    with pytest.raises(ConfigurationError) as excinfo:
        await service.fuzzify_indicator("unknown", [30.0, 45.0, 70.0])

    assert "Unknown fuzzy indicator" in str(excinfo.value)


@pytest.mark.api
@pytest.mark.asyncio
async def test_fuzzify_data(mock_fuzzy_engine, mock_data_manager, mock_config_loader):
    """Test fuzzification of data from symbol/timeframe."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine
    service.data_manager = mock_data_manager

    # Define indicator configs
    indicator_configs = [
        {"name": "rsi", "source_column": "close"},
        {"name": "macd", "source_column": "close"},
    ]

    result = await service.fuzzify_data(
        symbol="AAPL", timeframe="1d", indicator_configs=indicator_configs
    )

    # Verify result structure
    assert isinstance(result, dict)
    assert "symbol" in result
    assert "timeframe" in result
    assert "dates" in result
    assert "indicators" in result
    assert "metadata" in result

    # Check values
    assert result["symbol"] == "AAPL"
    assert result["timeframe"] == "1d"
    assert len(result["dates"]) == 3
    assert "rsi" in result["indicators"]
    assert "macd" in result["indicators"]

    # Verify the mocks were called
    mock_data_manager.load.assert_called_once()
    assert mock_fuzzy_engine.fuzzify.call_count == 2  # Once for each indicator


@pytest.mark.api
@pytest.mark.asyncio
async def test_fuzzify_data_with_dates(
    mock_fuzzy_engine, mock_data_manager, mock_config_loader
):
    """Test fuzzification with date range."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine
    service.data_manager = mock_data_manager

    # Define indicator configs
    indicator_configs = [{"name": "rsi", "source_column": "close"}]

    result = await service.fuzzify_data(
        symbol="AAPL",
        timeframe="1d",
        indicator_configs=indicator_configs,
        start_date="2023-01-01",
        end_date="2023-01-03",
    )

    # Verify result
    assert isinstance(result, dict)
    assert "metadata" in result
    assert "start_date" in result["metadata"]
    assert "end_date" in result["metadata"]

    # Verify mock called with date range
    mock_data_manager.load.assert_called_once_with(
        symbol="AAPL", interval="1d", start_date="2023-01-01", end_date="2023-01-03"
    )


@pytest.mark.api
@pytest.mark.asyncio
async def test_fuzzify_data_no_engine(mock_config_loader):
    """Test handling of no fuzzy engine in fuzzify_data."""
    service = FuzzyService()
    service.fuzzy_engine = None

    # Should raise ConfigurationError
    with pytest.raises(ConfigurationError) as excinfo:
        await service.fuzzify_data(
            symbol="AAPL",
            timeframe="1d",
            indicator_configs=[{"name": "rsi", "source_column": "close"}],
        )

    assert "Fuzzy engine is not initialized" in str(excinfo.value)


@pytest.mark.api
@pytest.mark.asyncio
async def test_fuzzify_data_load_error(
    mock_fuzzy_engine, mock_data_manager, mock_config_loader
):
    """Test handling of data loading error in fuzzify_data."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine
    service.data_manager = mock_data_manager

    # Set up mock to raise exception
    mock_data_manager.load.side_effect = Exception("Test error")

    # Should raise DataError
    with pytest.raises(DataError) as excinfo:
        await service.fuzzify_data(
            symbol="AAPL",
            timeframe="1d",
            indicator_configs=[{"name": "rsi", "source_column": "close"}],
        )

    assert "Failed to load data" in str(excinfo.value)


@pytest.mark.api
@pytest.mark.asyncio
async def test_fuzzify_data_empty_data(
    mock_fuzzy_engine, mock_data_manager, mock_config_loader
):
    """Test handling of empty data in fuzzify_data."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine
    service.data_manager = mock_data_manager

    # Set up mock to return empty dataframe
    mock_data_manager.load.return_value = pd.DataFrame()

    # Should raise DataError
    with pytest.raises(DataError) as excinfo:
        await service.fuzzify_data(
            symbol="AAPL",
            timeframe="1d",
            indicator_configs=[{"name": "rsi", "source_column": "close"}],
        )

    assert "No data available" in str(excinfo.value)


@pytest.mark.api
@pytest.mark.asyncio
async def test_health_check_healthy(mock_fuzzy_engine, mock_config_loader):
    """Test health check when service is healthy."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine

    result = await service.health_check()

    # Verify result
    assert isinstance(result, dict)
    assert result["status"] == "healthy"
    assert result["initialized"] is True
    assert "available_indicators" in result
    assert "indicator_names" in result
    assert "sample_fuzzy_sets" in result
    assert "message" in result

    # Verify the mock was called
    mock_fuzzy_engine.get_available_indicators.assert_called()


@pytest.mark.api
@pytest.mark.asyncio
async def test_health_check_degraded(mock_config_loader):
    """Test health check when fuzzy engine is not initialized."""
    service = FuzzyService()
    service.fuzzy_engine = None

    result = await service.health_check()

    # Verify result
    assert isinstance(result, dict)
    assert result["status"] == "degraded"
    assert result["initialized"] is False
    assert "message" in result
    assert "Fuzzy engine is not initialized" in result["message"]


@pytest.mark.api
@pytest.mark.asyncio
async def test_health_check_error(mock_fuzzy_engine, mock_config_loader):
    """Test health check when there's an error."""
    service = FuzzyService()
    service.fuzzy_engine = mock_fuzzy_engine

    # Set up mock to raise exception
    mock_fuzzy_engine.get_available_indicators.side_effect = Exception("Test error")

    result = await service.health_check()

    # Verify result
    assert isinstance(result, dict)
    assert result["status"] == "unhealthy"
    assert "message" in result
    assert "Test error" in result["message"]
