"""
Tests for IndicatorFactory and BaseIndicator with explicit naming.

Tests the integration of explicit naming through the factory and indicator chain.
"""

import pytest
import pandas as pd

from ktrdr.config.models import IndicatorConfig
from ktrdr.indicators import IndicatorFactory, RSIIndicator
from ktrdr.errors import ConfigurationError


class TestIndicatorFactoryExplicitNaming:
    """Test IndicatorFactory with explicit naming system."""

    def test_build_with_explicit_naming(self):
        """Test building indicators with explicit indicator + name fields."""
        configs = [
            IndicatorConfig(indicator="rsi", name="rsi_14", period=14),
            IndicatorConfig(indicator="rsi", name="rsi_fast", period=7),
        ]

        factory = IndicatorFactory(configs)
        indicators = factory.build()

        assert len(indicators) == 2
        assert all(isinstance(ind, RSIIndicator) for ind in indicators)

        # The indicator should have the explicit name stored
        # This will be used by get_column_name()
        assert hasattr(indicators[0], "_custom_column_name")
        assert indicators[0]._custom_column_name == "rsi_14"
        assert indicators[1]._custom_column_name == "rsi_fast"

    def test_indicator_uses_custom_name_for_column(self):
        """Test that indicators use custom names when generating column names."""
        config = IndicatorConfig(indicator="rsi", name="rsi_custom", period=14)

        factory = IndicatorFactory([config])
        indicators = factory.build()

        # Get column name - should use custom name, not auto-generated
        column_name = indicators[0].get_column_name()
        assert column_name == "rsi_custom"

    def test_indicator_column_name_with_suffix(self):
        """Test that custom names work with suffixes."""
        config = IndicatorConfig(indicator="macd", name="macd_standard", fast_period=12)

        factory = IndicatorFactory([config])
        indicators = factory.build()

        # MACD might generate multiple columns with suffixes
        base_name = indicators[0].get_column_name()
        signal_name = indicators[0].get_column_name(suffix="signal")

        assert base_name == "macd_standard"
        assert signal_name == "macd_standard_signal"

    def test_fallback_to_auto_generated_name_if_no_custom_name(self):
        """Test that indicators without custom names fall back to auto-generated names."""
        # This tests backward compatibility if we directly instantiate indicators
        indicator = RSIIndicator(period=14)

        # Should not have custom column name attribute
        assert not hasattr(indicator, "_custom_column_name")

        # Should generate name from parameters
        column_name = indicator.get_column_name()
        assert column_name == "rsi_14"

    def test_multiple_same_indicator_different_names(self):
        """Test creating multiple instances of the same indicator with different names."""
        configs = [
            IndicatorConfig(indicator="rsi", name="rsi_short", period=7),
            IndicatorConfig(indicator="rsi", name="rsi_medium", period=14),
            IndicatorConfig(indicator="rsi", name="rsi_long", period=21),
        ]

        factory = IndicatorFactory(configs)
        indicators = factory.build()

        assert len(indicators) == 3

        names = [ind.get_column_name() for ind in indicators]
        assert names == ["rsi_short", "rsi_medium", "rsi_long"]

    def test_flat_yaml_params_extracted_correctly(self):
        """Test that parameters from flat YAML format are passed to indicator."""
        config = IndicatorConfig(
            indicator="rsi",
            name="rsi_14",
            period=14,
            source="close"
        )

        factory = IndicatorFactory([config])
        indicators = factory.build()

        # Check that params were extracted and passed
        assert indicators[0].params["period"] == 14
        assert indicators[0].params["source"] == "close"

    def test_indicator_compute_uses_custom_name(self):
        """Test that computed indicator results use custom column names."""
        config = IndicatorConfig(indicator="rsi", name="rsi_custom", period=14)

        factory = IndicatorFactory([config])
        indicators = factory.build()

        # Create sample data
        data = pd.DataFrame({
            "close": [100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
                     110, 112, 111, 113, 115, 114, 116, 118, 117, 119]
        })

        # Compute indicator
        result = indicators[0].compute(data)

        # Result should be a Series with custom name
        assert result.name == "rsi_custom"


class TestBaseIndicatorColumnNaming:
    """Test BaseIndicator get_column_name() with custom names."""

    def test_get_column_name_with_custom_name(self):
        """Test that custom column name is used when set."""
        indicator = RSIIndicator(period=14)
        indicator._custom_column_name = "rsi_custom"

        assert indicator.get_column_name() == "rsi_custom"

    def test_get_column_name_without_custom_name(self):
        """Test that auto-generated name is used when no custom name."""
        indicator = RSIIndicator(period=14)

        # Should generate: rsi_14
        assert indicator.get_column_name() == "rsi_14"

    def test_get_column_name_custom_with_suffix(self):
        """Test that suffix is appended to custom name."""
        indicator = RSIIndicator(period=14)
        indicator._custom_column_name = "rsi_custom"

        assert indicator.get_column_name(suffix="smoothed") == "rsi_custom_smoothed"

    def test_get_column_name_auto_with_suffix(self):
        """Test that suffix is appended to auto-generated name."""
        indicator = RSIIndicator(period=14)

        assert indicator.get_column_name(suffix="smoothed") == "rsi_14_smoothed"
