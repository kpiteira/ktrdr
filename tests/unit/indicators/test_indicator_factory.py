"""
Tests for the IndicatorFactory class.
"""

import pytest
import yaml

from ktrdr.config.models import IndicatorConfig, IndicatorsConfig
from ktrdr.errors import ConfigurationError
from ktrdr.indicators import (
    ExponentialMovingAverage,
    IndicatorFactory,
    RSIIndicator,
    SimpleMovingAverage,
)


class TestIndicatorFactory:
    """Test cases for the IndicatorFactory class."""

    def test_initialization(self):
        """Test initialization with different config types."""
        # Test with IndicatorsConfig
        config = IndicatorsConfig(
            indicators=[IndicatorConfig(type="RSI", params={"period": 14})]
        )
        factory = IndicatorFactory(config)
        assert len(factory.indicators_config.indicators) == 1

        # Test with list of IndicatorConfig
        configs = [
            IndicatorConfig(type="RSI", params={"period": 14}),
            IndicatorConfig(type="SMA", params={"period": 20}),
        ]
        factory = IndicatorFactory(configs)
        assert len(factory.indicators_config.indicators) == 2

        # Test with invalid config type
        with pytest.raises(ConfigurationError) as excinfo:
            IndicatorFactory("invalid")
        assert "Invalid indicator configuration type" in str(excinfo.value)

    def test_build_basic_indicators(self):
        """Test building basic indicators."""
        configs = [
            IndicatorConfig(type="RSI", params={"period": 14}),
            IndicatorConfig(type="SMA", params={"period": 20}),
            IndicatorConfig(type="EMA", params={"period": 12}),
        ]
        factory = IndicatorFactory(configs)
        indicators = factory.build()

        # Check that we got the right number of indicators
        assert len(indicators) == 3

        # Check that the indicators are of the correct types
        assert isinstance(indicators[0], RSIIndicator)
        assert isinstance(indicators[1], SimpleMovingAverage)
        assert isinstance(indicators[2], ExponentialMovingAverage)

        # Check parameters
        assert indicators[0].params["period"] == 14
        assert indicators[1].params["period"] == 20
        assert indicators[2].params["period"] == 12

    def test_indicator_custom_names(self):
        """Test creating indicators with custom names."""
        configs = [IndicatorConfig(type="RSI", name="CustomRSI", params={"period": 14})]
        factory = IndicatorFactory(configs)
        indicators = factory.build()

        # Check that the custom name was applied
        assert indicators[0].name == "CustomRSI"

    def test_invalid_indicator_type(self):
        """Test behavior with an invalid indicator type."""
        configs = [IndicatorConfig(type="NonExistentIndicator", params={})]
        factory = IndicatorFactory(configs)

        # This should raise an error
        with pytest.raises(ConfigurationError) as excinfo:
            factory.build()
        assert "Indicator type NonExistentIndicator not found" in str(excinfo.value)

    def test_invalid_parameters(self):
        """Test behavior with invalid indicator parameters."""
        configs = [IndicatorConfig(type="RSI", params={"period": -5})]  # Invalid period
        factory = IndicatorFactory(configs)

        # This should fail during indicator initialization
        with pytest.raises(ConfigurationError) as excinfo:
            factory.build()
        assert "Failed to create any indicators" in str(excinfo.value)

    def test_partial_failures(self):
        """Test behavior when some indicators fail but others succeed."""
        configs = [
            IndicatorConfig(type="RSI", params={"period": 14}),  # Valid
            IndicatorConfig(type="SMA", params={"period": -5}),  # Invalid
            IndicatorConfig(type="EMA", params={"period": 12}),  # Valid
        ]
        factory = IndicatorFactory(configs)

        # This should succeed with warnings for the failed indicator
        indicators = factory.build()

        # Check that we got 2 valid indicators
        assert len(indicators) == 2
        assert isinstance(indicators[0], RSIIndicator)
        assert isinstance(indicators[1], ExponentialMovingAverage)

    def test_load_from_yaml_file(self, tmp_path):
        """Test loading indicators from a YAML file."""
        # Create a temporary YAML file
        yaml_content = """
        indicators:
          - type: RSI
            params:
              period: 14
          - type: SMA
            params:
              period: 10
        """
        yaml_file = tmp_path / "test_indicators.yaml"
        yaml_file.write_text(yaml_content)

        # Load the configuration
        with open(yaml_file) as f:
            config_data = yaml.safe_load(f)

        indicators_config = IndicatorsConfig(**config_data)
        factory = IndicatorFactory(indicators_config)
        indicators = factory.build()

        # Check that we got the right indicators
        assert len(indicators) == 2
        assert isinstance(indicators[0], RSIIndicator)
        assert isinstance(indicators[1], SimpleMovingAverage)
        assert indicators[0].params["period"] == 14
        assert indicators[1].params["period"] == 10
