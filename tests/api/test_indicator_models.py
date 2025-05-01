"""
API indicator models tests.

This module tests the indicator models for API requests and responses.
"""
import pytest
from pydantic import ValidationError

from ktrdr.api.models.indicators import (
    IndicatorType,
    IndicatorParameter,
    IndicatorMetadata,
    IndicatorConfig,
    IndicatorCalculateRequest
)


class TestIndicatorParameter:
    """Tests for the IndicatorParameter model."""
    
    def test_valid_parameter(self):
        """Test that a valid indicator parameter is created correctly."""
        param = IndicatorParameter(
            name="period",
            type="int",
            description="Lookback period",
            default=14,
            min_value=2,
            max_value=100
        )
        assert param.name == "period"
        assert param.type == "int"
        assert param.description == "Lookback period"
        assert param.default == 14
        assert param.min_value == 2
        assert param.max_value == 100
    
    def test_parameter_with_options(self):
        """Test that a parameter with options is created correctly."""
        param = IndicatorParameter(
            name="source",
            type="str",
            description="Price source",
            default="close",
            options=["open", "high", "low", "close"]
        )
        assert param.name == "source"
        assert param.type == "str"
        assert param.default == "close"
        assert "open" in param.options
        assert "close" in param.options
    
    def test_invalid_parameter_type(self):
        """Test that invalid parameter type raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorParameter(
                name="period",
                type="invalid_type",  # Invalid type
                description="Lookback period",
                default=14
            )
        assert "type" in str(exc_info.value)
    
    def test_min_value_greater_than_max_value(self):
        """Test that min_value > max_value raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorParameter(
                name="period",
                type="int",
                description="Lookback period",
                default=14,
                min_value=100,  # Greater than max_value
                max_value=10
            )
        assert "min_value" in str(exc_info.value) and "max_value" in str(exc_info.value)
    
    def test_default_not_in_options(self):
        """Test that default value not in options raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorParameter(
                name="source",
                type="str",
                description="Price source",
                default="volume",  # Not in options
                options=["open", "high", "low", "close"]
            )
        assert "default value" in str(exc_info.value) and "options" in str(exc_info.value)


class TestIndicatorMetadata:
    """Tests for the IndicatorMetadata model."""
    
    def test_valid_metadata(self):
        """Test that valid indicator metadata is created correctly."""
        metadata = IndicatorMetadata(
            id="rsi",
            name="Relative Strength Index",
            description="Momentum oscillator",
            type=IndicatorType.MOMENTUM,
            parameters=[
                IndicatorParameter(
                    name="period",
                    type="int",
                    description="Lookback period",
                    default=14,
                    min_value=2,
                    max_value=100
                ),
                IndicatorParameter(
                    name="source",
                    type="str",
                    description="Price source",
                    default="close",
                    options=["open", "high", "low", "close"]
                )
            ]
        )
        assert metadata.id == "rsi"
        assert metadata.name == "Relative Strength Index"
        assert metadata.type == IndicatorType.MOMENTUM
        assert len(metadata.parameters) == 2
        assert metadata.parameters[0].name == "period"
        assert metadata.parameters[1].name == "source"


class TestIndicatorConfig:
    """Tests for the IndicatorConfig model."""
    
    def test_valid_config(self):
        """Test that a valid indicator configuration is created correctly."""
        config = IndicatorConfig(
            id="rsi",
            parameters={"period": 14, "source": "close"},
            output_name="RSI_14"
        )
        assert config.id == "rsi"
        assert config.parameters["period"] == 14
        assert config.parameters["source"] == "close"
        assert config.output_name == "RSI_14"
    
    def test_config_without_parameters(self):
        """Test that a config can be created without parameters."""
        config = IndicatorConfig(
            id="rsi"
        )
        assert config.id == "rsi"
        assert config.parameters == {}
        assert config.output_name is None


class TestIndicatorCalculateRequest:
    """Tests for the IndicatorCalculateRequest model."""
    
    def test_valid_request(self):
        """Test that a valid calculate request is created correctly."""
        request = IndicatorCalculateRequest(
            symbol="AAPL",
            timeframe="1d",
            indicators=[
                IndicatorConfig(
                    id="rsi",
                    parameters={"period": 14}
                ),
                IndicatorConfig(
                    id="sma",
                    parameters={"period": 20}
                )
            ],
            start_date="2023-01-01",
            end_date="2023-01-31"
        )
        assert request.symbol == "AAPL"
        assert request.timeframe == "1d"
        assert len(request.indicators) == 2
        assert request.indicators[0].id == "rsi"
        assert request.indicators[1].id == "sma"
        assert request.start_date == "2023-01-01"
        assert request.end_date == "2023-01-31"
    
    def test_invalid_timeframe(self):
        """Test that invalid timeframe raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorCalculateRequest(
                symbol="AAPL",
                timeframe="invalid",  # Invalid timeframe
                indicators=[
                    IndicatorConfig(
                        id="rsi",
                        parameters={"period": 14}
                    )
                ]
            )
        assert "timeframe" in str(exc_info.value)
    
    def test_empty_indicators(self):
        """Test that empty indicators list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorCalculateRequest(
                symbol="AAPL",
                timeframe="1d",
                indicators=[]  # Empty list
            )
        assert "indicators" in str(exc_info.value)