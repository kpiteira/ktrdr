"""
Tests for IndicatorEngine validation with explicit naming.

Tests that IndicatorEngine properly validates the new explicit naming format
through IndicatorConfig model validation.
"""

import pandas as pd
import pytest

from ktrdr.errors import ConfigurationError
from ktrdr.indicators.indicator_engine import IndicatorEngine


class TestIndicatorEngineValidation:
    """Test cases for IndicatorEngine validation with explicit naming."""

    @pytest.fixture
    def sample_data(self):
        """Sample OHLCV data for testing (30 rows for indicators that need history)."""
        # Create 30 rows of sample data
        rows = 30
        return pd.DataFrame(
            {
                "open": [100.0 + i for i in range(rows)],
                "high": [105.0 + i for i in range(rows)],
                "low": [99.0 + i for i in range(rows)],
                "close": [104.0 + i for i in range(rows)],
                "volume": [1000 + i * 100 for i in range(rows)],
            }
        )

    def test_valid_explicit_naming_config(self, sample_data):
        """Test that valid explicit naming config works correctly."""
        indicators = [
            {"indicator": "rsi", "name": "rsi_14", "period": 14},
            {"indicator": "sma", "name": "sma_20", "period": 20},
        ]

        engine = IndicatorEngine(indicators)
        result = engine.apply(sample_data)

        # Should have original columns plus two indicator columns
        assert isinstance(result, pd.DataFrame)
        assert "rsi_14" in result.columns
        assert "sma_20" in result.columns

    def test_missing_indicator_field_raises_error(self, sample_data):
        """Test that missing 'indicator' field raises validation error."""
        indicators = [{"name": "rsi_14", "period": 14}]  # Missing 'indicator' field

        with pytest.raises(Exception) as excinfo:
            IndicatorEngine(indicators)

        # Should raise during IndicatorConfig validation
        error_msg = str(excinfo.value).lower()
        assert "indicator" in error_msg or "field required" in error_msg

    def test_missing_name_field_raises_error(self, sample_data):
        """Test that missing 'name' field raises validation error."""
        indicators = [{"indicator": "rsi", "period": 14}]  # Missing 'name' field

        with pytest.raises(Exception) as excinfo:
            IndicatorEngine(indicators)

        # Should raise during IndicatorConfig validation
        error_msg = str(excinfo.value).lower()
        assert "name" in error_msg or "field required" in error_msg

    def test_invalid_name_format_raises_error(self, sample_data):
        """Test that invalid name format raises validation error."""
        indicators = [
            {
                "indicator": "rsi",
                "name": "123invalid",
                "period": 14,
            }  # Invalid: starts with number
        ]

        with pytest.raises(Exception) as excinfo:
            IndicatorEngine(indicators)

        error_msg = str(excinfo.value).lower()
        assert "name" in error_msg or "start with letter" in error_msg

    def test_empty_name_raises_error(self, sample_data):
        """Test that empty name raises validation error."""
        indicators = [{"indicator": "rsi", "name": "", "period": 14}]  # Empty name

        with pytest.raises(Exception) as excinfo:
            IndicatorEngine(indicators)

        error_msg = str(excinfo.value).lower()
        assert "name" in error_msg or "empty" in error_msg

    def test_whitespace_name_raises_error(self, sample_data):
        """Test that whitespace-only name raises validation error."""
        indicators = [
            {"indicator": "rsi", "name": "   ", "period": 14}  # Whitespace only
        ]

        with pytest.raises(Exception) as excinfo:
            IndicatorEngine(indicators)

        error_msg = str(excinfo.value).lower()
        assert "name" in error_msg or "empty" in error_msg

    def test_duplicate_names_raises_error(self, sample_data):
        """Test that duplicate indicator names raise validation error."""
        indicators = [
            {"indicator": "rsi", "name": "my_indicator", "period": 14},
            {
                "indicator": "sma",
                "name": "my_indicator",
                "period": 20,
            },  # Duplicate name
        ]

        with pytest.raises(ConfigurationError) as excinfo:
            IndicatorEngine(indicators)

        error_msg = str(excinfo.value).lower()
        assert "duplicate" in error_msg or "unique" in error_msg

    def test_valid_name_with_underscores(self, sample_data):
        """Test that valid names with underscores work correctly."""
        indicators = [{"indicator": "rsi", "name": "my_rsi_indicator", "period": 14}]

        engine = IndicatorEngine(indicators)
        result = engine.apply(sample_data)

        assert "my_rsi_indicator" in result.columns

    def test_valid_name_with_dashes(self, sample_data):
        """Test that valid names with dashes work correctly."""
        indicators = [{"indicator": "rsi", "name": "my-rsi-indicator", "period": 14}]

        engine = IndicatorEngine(indicators)
        result = engine.apply(sample_data)

        assert "my-rsi-indicator" in result.columns

    def test_valid_name_with_numbers(self, sample_data):
        """Test that valid names with numbers (not at start) work correctly."""
        indicators = [{"indicator": "rsi", "name": "rsi14indicator", "period": 14}]

        engine = IndicatorEngine(indicators)
        result = engine.apply(sample_data)

        assert "rsi14indicator" in result.columns

    def test_flat_format_parameters(self, sample_data):
        """Test that flat format (params at top level) works correctly."""
        indicators = [
            {"indicator": "rsi", "name": "rsi_14", "period": 14, "source": "close"}
        ]

        engine = IndicatorEngine(indicators)
        result = engine.apply(sample_data)

        assert "rsi_14" in result.columns

    def test_nested_format_parameters(self, sample_data):
        """Test that nested format (params in dict) works correctly."""
        indicators = [
            {
                "indicator": "rsi",
                "name": "rsi_14",
                "params": {"period": 14, "source": "close"},
            }
        ]

        engine = IndicatorEngine(indicators)
        result = engine.apply(sample_data)

        assert "rsi_14" in result.columns
