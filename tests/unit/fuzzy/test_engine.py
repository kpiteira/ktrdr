"""
Tests for the FuzzyEngine implementation.

This module contains tests for the FuzzyEngine class that transforms
indicator values into fuzzy membership degrees.
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import ConfigurationError, ProcessingError
from ktrdr.fuzzy import FuzzyConfig, FuzzyEngine


class TestFuzzyEngine:
    """Test suite for the FuzzyEngine class."""

    def test_initialization(self, valid_fuzzy_config):
        """Test that FuzzyEngine initializes correctly with a valid configuration."""
        engine = FuzzyEngine(valid_fuzzy_config)

        # Check that indicators were loaded correctly
        assert "rsi" in engine.get_available_indicators()
        assert "macd" in engine.get_available_indicators()

        # Check that fuzzy sets were loaded
        assert sorted(engine.get_fuzzy_sets("rsi")) == sorted(["low", "medium", "high"])
        assert sorted(engine.get_fuzzy_sets("macd")) == sorted(
            ["negative", "neutral", "positive"]
        )

    def test_initialization_empty_config(self):
        """Test that FuzzyEngine raises an error with an empty configuration."""
        # We can't create an empty FuzzyConfig directly due to validation,
        # so we'll use a slightly different test approach
        with pytest.raises(ConfigurationError) as excinfo:
            # Create minimal config dictionary with no indicators
            minimal_config = {}
            # This should be caught by FuzzyConfig validation
            config = FuzzyConfig.model_validate(minimal_config)

        # Check the message instead of error code since this is coming from the config validation
        assert "At least one indicator must be defined" in str(excinfo.value)
        # Or if we can access the error_code:
        if hasattr(excinfo.value, "error_code"):
            assert excinfo.value.error_code == "CONFIG-EmptyFuzzyConfig"

    def test_fuzzify_scalar(self, fuzzy_engine):
        """Test fuzzification of scalar values."""
        # Test RSI value in the middle range
        rsi_value = 50.0
        result = fuzzy_engine.fuzzify("rsi", rsi_value)

        assert "rsi_low" in result
        assert "rsi_medium" in result
        assert "rsi_high" in result

        # For RSI = 50, the medium membership should be highest
        assert result["rsi_medium"] > result["rsi_low"]
        assert result["rsi_medium"] > result["rsi_high"]

        # Test RSI value in the low range
        rsi_value = 20.0
        result = fuzzy_engine.fuzzify("rsi", rsi_value)

        # For RSI = 20, the low membership should be highest
        assert result["rsi_low"] > result["rsi_medium"]
        assert result["rsi_low"] > result["rsi_high"]

    def test_fuzzify_series(self, fuzzy_engine):
        """Test fuzzification of pandas Series."""
        # Create a series of RSI values
        rsi_values = pd.Series([20.0, 50.0, 80.0], index=[0, 1, 2])
        result = fuzzy_engine.fuzzify("rsi", rsi_values)

        # Check output shape
        assert isinstance(result, pd.DataFrame)
        assert result.shape == (3, 3)  # 3 rows, 3 columns (low, medium, high)
        assert list(result.columns) == ["rsi_low", "rsi_medium", "rsi_high"]

        # Check index preservation
        assert list(result.index) == [0, 1, 2]

        # Check specific values
        # For RSI = 20, low membership should be highest
        assert result.loc[0, "rsi_low"] > result.loc[0, "rsi_medium"]
        assert result.loc[0, "rsi_low"] > result.loc[0, "rsi_high"]

        # For RSI = 50, medium membership should be highest
        assert result.loc[1, "rsi_medium"] > result.loc[1, "rsi_low"]
        assert result.loc[1, "rsi_medium"] > result.loc[1, "rsi_high"]

        # For RSI = 80, high membership should be highest
        assert result.loc[2, "rsi_high"] > result.loc[2, "rsi_low"]
        assert result.loc[2, "rsi_high"] > result.loc[2, "rsi_medium"]

    def test_fuzzify_numpy_array(self, fuzzy_engine):
        """Test fuzzification of numpy arrays."""
        # Create a numpy array of RSI values
        rsi_values = np.array([20.0, 50.0, 80.0])
        result = fuzzy_engine.fuzzify("rsi", rsi_values)

        # Check output shape
        assert isinstance(result, pd.DataFrame)
        assert result.shape == (3, 3)  # 3 rows, 3 columns (low, medium, high)

        # Check specific values (same as Series test)
        assert result.iloc[0]["rsi_low"] > result.iloc[0]["rsi_medium"]
        assert result.iloc[1]["rsi_medium"] > result.iloc[1]["rsi_low"]
        assert result.iloc[2]["rsi_high"] > result.iloc[2]["rsi_medium"]

    def test_fuzzify_unknown_indicator(self, fuzzy_engine):
        """Test fuzzification with an unknown indicator."""
        with pytest.raises(ProcessingError) as excinfo:
            fuzzy_engine.fuzzify("unknown", 50.0)

        # Check both message and error code
        assert "Unknown indicator" in str(excinfo.value)
        assert excinfo.value.error_code == "ENGINE-UnknownIndicator"

    def test_fuzzify_invalid_input_type(self, fuzzy_engine):
        """Test fuzzification with an invalid input type."""
        with pytest.raises(TypeError):
            fuzzy_engine.fuzzify("rsi", "not_a_number")

    def test_fuzzify_nan_values(self, fuzzy_engine):
        """Test fuzzification with NaN values."""
        # Create a series with NaN values
        rsi_values = pd.Series([20.0, np.nan, 80.0])
        result = fuzzy_engine.fuzzify("rsi", rsi_values)

        # Check that NaN inputs result in NaN outputs
        assert not np.isnan(result.iloc[0]["rsi_low"])  # Non-NaN input
        assert np.isnan(result.iloc[1]["rsi_low"])  # NaN input
        assert not np.isnan(result.iloc[2]["rsi_low"])  # Non-NaN input

    def test_get_fuzzy_sets_unknown_indicator(self, fuzzy_engine):
        """Test get_fuzzy_sets with an unknown indicator."""
        with pytest.raises(ProcessingError) as excinfo:
            fuzzy_engine.get_fuzzy_sets("unknown")

        # Check both message and error code
        assert "Unknown indicator" in str(excinfo.value)
        assert excinfo.value.error_code == "ENGINE-UnknownIndicator"

    def test_get_output_names(self, fuzzy_engine):
        """Test get_output_names method."""
        output_names = fuzzy_engine.get_output_names("rsi")
        expected = ["rsi_low", "rsi_medium", "rsi_high"]
        assert sorted(output_names) == sorted(expected)

        output_names = fuzzy_engine.get_output_names("macd")
        expected = ["macd_negative", "macd_neutral", "macd_positive"]
        assert sorted(output_names) == sorted(expected)


@pytest.fixture
def valid_fuzzy_config():
    """Fixture for creating a valid fuzzy configuration."""
    config_dict = {
        "rsi": {
            "low": {"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
            "medium": {"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
            "high": {"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
        },
        "macd": {
            "negative": {"type": "triangular", "parameters": [-10.0, -5.0, 0.0]},
            "neutral": {"type": "triangular", "parameters": [-2.0, 0.0, 2.0]},
            "positive": {"type": "triangular", "parameters": [0.0, 5.0, 10.0]},
        },
    }
    return FuzzyConfig.model_validate(config_dict)


@pytest.fixture
def fuzzy_engine(valid_fuzzy_config):
    """Fixture for creating a FuzzyEngine instance with a valid configuration."""
    return FuzzyEngine(valid_fuzzy_config)
