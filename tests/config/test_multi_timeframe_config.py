"""Tests for multi-timeframe configuration models and loader."""

import pytest
import tempfile
import yaml
from pathlib import Path
from pydantic import ValidationError

from ktrdr.config.models import (
    TimeframeIndicatorConfig,
    MultiTimeframeIndicatorConfig,
    IndicatorConfig,
    IndicatorsConfig,
)
from ktrdr.config.loader import ConfigLoader


class TestTimeframeIndicatorConfig:
    """Test cases for TimeframeIndicatorConfig."""

    def test_valid_configuration(self):
        """Test valid timeframe indicator configuration."""
        config = TimeframeIndicatorConfig(
            timeframe="1h",
            indicators=[
                IndicatorConfig(type="RSI", params={"period": 14}),
                IndicatorConfig(type="SMA", params={"period": 20}),
            ],
            enabled=True,
            weight=1.5,
        )

        assert config.timeframe == "1h"
        assert len(config.indicators) == 2
        assert config.enabled == True
        assert config.weight == 1.5

    def test_timeframe_validation(self):
        """Test timeframe validation."""
        # Valid timeframes
        valid_timeframes = ["1h", "4h", "1d", "1w", "1M", "5m", "15m", "30m"]

        for tf in valid_timeframes:
            config = TimeframeIndicatorConfig(timeframe=tf, indicators=[])
            assert config.timeframe == tf

    def test_invalid_timeframe(self):
        """Test invalid timeframe validation."""
        with pytest.raises(ValidationError):
            TimeframeIndicatorConfig(timeframe="invalid", indicators=[])

        with pytest.raises(ValidationError):
            TimeframeIndicatorConfig(timeframe="", indicators=[])

    def test_weight_validation(self):
        """Test weight validation."""
        # Valid weight
        config = TimeframeIndicatorConfig(timeframe="1h", indicators=[], weight=2.5)
        assert config.weight == 2.5

        # Invalid weight
        with pytest.raises(ValidationError):
            TimeframeIndicatorConfig(timeframe="1h", indicators=[], weight=0.0)

        with pytest.raises(ValidationError):
            TimeframeIndicatorConfig(timeframe="1h", indicators=[], weight=-1.0)

    def test_default_values(self):
        """Test default values."""
        config = TimeframeIndicatorConfig(timeframe="1h", indicators=[])

        assert config.enabled == True
        assert config.weight == 1.0


class TestMultiTimeframeIndicatorConfig:
    """Test cases for MultiTimeframeIndicatorConfig."""

    def test_valid_configuration(self):
        """Test valid multi-timeframe configuration."""
        config = MultiTimeframeIndicatorConfig(
            timeframes=[
                TimeframeIndicatorConfig(
                    timeframe="1h",
                    indicators=[IndicatorConfig(type="RSI", params={"period": 14})],
                ),
                TimeframeIndicatorConfig(
                    timeframe="4h",
                    indicators=[IndicatorConfig(type="SMA", params={"period": 20})],
                ),
            ],
            cross_timeframe_features={
                "rsi_divergence": {
                    "primary_timeframe": "1h",
                    "secondary_timeframe": "4h",
                    "operation": "difference",
                }
            },
            column_standardization=True,
        )

        assert len(config.timeframes) == 2
        assert "rsi_divergence" in config.cross_timeframe_features
        assert config.column_standardization == True

    def test_duplicate_timeframes(self):
        """Test validation of duplicate timeframes."""
        with pytest.raises(ValidationError):
            MultiTimeframeIndicatorConfig(
                timeframes=[
                    TimeframeIndicatorConfig(timeframe="1h", indicators=[]),
                    TimeframeIndicatorConfig(
                        timeframe="1h", indicators=[]  # Duplicate
                    ),
                ]
            )

    def test_default_values(self):
        """Test default values."""
        config = MultiTimeframeIndicatorConfig()

        assert config.timeframes == []
        assert config.cross_timeframe_features == {}
        assert config.column_standardization == True

    def test_cross_timeframe_features(self):
        """Test cross-timeframe features configuration."""
        config = MultiTimeframeIndicatorConfig(
            timeframes=[
                TimeframeIndicatorConfig(timeframe="1h", indicators=[]),
                TimeframeIndicatorConfig(timeframe="4h", indicators=[]),
            ],
            cross_timeframe_features={
                "feature1": {
                    "primary_timeframe": "1h",
                    "secondary_timeframe": "4h",
                    "primary_column": "rsi_1h",
                    "secondary_column": "rsi_4h",
                    "operation": "ratio",
                },
                "feature2": {
                    "primary_timeframe": "1h",
                    "secondary_timeframe": "4h",
                    "operation": "correlation",
                    "window": 20,
                },
            },
        )

        assert len(config.cross_timeframe_features) == 2
        assert config.cross_timeframe_features["feature1"]["operation"] == "ratio"
        assert config.cross_timeframe_features["feature2"]["window"] == 20


class TestIndicatorsConfig:
    """Test cases for updated IndicatorsConfig with multi-timeframe support."""

    def test_legacy_indicators_only(self):
        """Test configuration with only legacy indicators."""
        config = IndicatorsConfig(
            indicators=[
                IndicatorConfig(type="RSI", params={"period": 14}),
                IndicatorConfig(type="SMA", params={"period": 20}),
            ]
        )

        assert len(config.indicators) == 2
        assert config.multi_timeframe is None

    def test_multi_timeframe_only(self):
        """Test configuration with only multi-timeframe indicators."""
        config = IndicatorsConfig(
            multi_timeframe=MultiTimeframeIndicatorConfig(
                timeframes=[
                    TimeframeIndicatorConfig(
                        timeframe="1h",
                        indicators=[IndicatorConfig(type="RSI", params={"period": 14})],
                    )
                ]
            )
        )

        assert len(config.indicators) == 0
        assert config.multi_timeframe is not None
        assert len(config.multi_timeframe.timeframes) == 1

    def test_mixed_configuration(self):
        """Test configuration with both legacy and multi-timeframe indicators."""
        config = IndicatorsConfig(
            indicators=[IndicatorConfig(type="RSI", params={"period": 14})],
            multi_timeframe=MultiTimeframeIndicatorConfig(
                timeframes=[
                    TimeframeIndicatorConfig(
                        timeframe="1h",
                        indicators=[IndicatorConfig(type="SMA", params={"period": 20})],
                    )
                ]
            ),
        )

        assert len(config.indicators) == 1
        assert config.multi_timeframe is not None
        assert len(config.multi_timeframe.timeframes) == 1


class TestConfigLoader:
    """Test cases for ConfigLoader with multi-timeframe support."""

    def test_load_multi_timeframe_indicators_success(self):
        """Test successful loading of multi-timeframe indicator configuration."""
        # Create a temporary YAML config file
        config_data = {
            "indicators": {
                "multi_timeframe": {
                    "column_standardization": True,
                    "timeframes": [
                        {
                            "timeframe": "1h",
                            "enabled": True,
                            "weight": 1.0,
                            "indicators": [{"type": "RSI", "params": {"period": 14}}],
                        },
                        {
                            "timeframe": "4h",
                            "enabled": True,
                            "weight": 1.5,
                            "indicators": [{"type": "SMA", "params": {"period": 20}}],
                        },
                    ],
                }
            },
            "data": {"directory": "./data"},
            "logging": {"level": "INFO"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            loader = ConfigLoader()
            mt_config = loader.load_multi_timeframe_indicators(temp_path)

            assert mt_config is not None
            assert len(mt_config.timeframes) == 2
            assert mt_config.column_standardization == True

            # Check timeframe details
            timeframes = {tf.timeframe: tf for tf in mt_config.timeframes}
            assert "1h" in timeframes
            assert "4h" in timeframes
            assert timeframes["1h"].weight == 1.0
            assert timeframes["4h"].weight == 1.5

        finally:
            Path(temp_path).unlink()

    def test_load_multi_timeframe_indicators_missing_section(self):
        """Test loading when multi-timeframe section is missing."""
        config_data = {"data": {"directory": "./data"}, "logging": {"level": "INFO"}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            loader = ConfigLoader()
            mt_config = loader.load_multi_timeframe_indicators(temp_path)

            # Should return empty config
            assert mt_config is not None
            assert len(mt_config.timeframes) == 0

        finally:
            Path(temp_path).unlink()

    def test_validate_multi_timeframe_config(self):
        """Test multi-timeframe configuration validation."""
        loader = ConfigLoader()

        # Valid configuration
        valid_config = MultiTimeframeIndicatorConfig(
            timeframes=[
                TimeframeIndicatorConfig(
                    timeframe="1h",
                    indicators=[
                        IndicatorConfig(type="RSI", params={"period": 14}),
                        IndicatorConfig(type="SMA", params={"period": 20}),
                    ],
                ),
                TimeframeIndicatorConfig(
                    timeframe="4h",
                    indicators=[
                        IndicatorConfig(type="RSI", params={"period": 14}),
                        IndicatorConfig(type="EMA", params={"period": 21}),
                    ],
                ),
            ]
        )

        validation_result = loader.validate_multi_timeframe_config(valid_config)

        assert validation_result["valid"] == True
        assert "timeframe_summary" in validation_result
        assert validation_result["timeframe_summary"]["count"] == 2
        assert (
            len(validation_result["timeframe_summary"]["common_indicator_types"]) == 1
        )  # RSI

        # Empty configuration
        empty_config = MultiTimeframeIndicatorConfig()
        validation_result = loader.validate_multi_timeframe_config(empty_config)

        assert validation_result["valid"] == False
        assert "No timeframes configured" in validation_result["errors"]

    def test_create_sample_multi_timeframe_config(self):
        """Test creating sample multi-timeframe configuration."""
        loader = ConfigLoader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            loader.create_sample_multi_timeframe_config(temp_path)

            # Verify the file was created and contains valid YAML
            assert Path(temp_path).exists()

            with open(temp_path, "r") as f:
                sample_config = yaml.safe_load(f)

            assert "indicators" in sample_config
            assert "multi_timeframe" in sample_config["indicators"]
            assert "timeframes" in sample_config["indicators"]["multi_timeframe"]

            timeframes = sample_config["indicators"]["multi_timeframe"]["timeframes"]
            assert len(timeframes) == 3  # 1h, 4h, 1d

            # Check timeframe structure
            for tf_config in timeframes:
                assert "timeframe" in tf_config
                assert "enabled" in tf_config
                assert "weight" in tf_config
                assert "indicators" in tf_config

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()


class TestConfigurationIntegration:
    """Integration tests for multi-timeframe configuration."""

    def test_full_configuration_cycle(self):
        """Test full configuration loading and validation cycle."""
        # Create comprehensive configuration
        config_data = {
            "indicators": {
                "indicators": [{"type": "RSI", "params": {"period": 14}}],
                "multi_timeframe": {
                    "column_standardization": True,
                    "timeframes": [
                        {
                            "timeframe": "1h",
                            "enabled": True,
                            "weight": 1.0,
                            "indicators": [
                                {
                                    "type": "RSI",
                                    "name": "rsi_short",
                                    "params": {"period": 14},
                                },
                                {
                                    "type": "SimpleMovingAverage",
                                    "name": "sma_fast",
                                    "params": {"period": 10},
                                },
                            ],
                        },
                        {
                            "timeframe": "4h",
                            "enabled": True,
                            "weight": 1.5,
                            "indicators": [
                                {
                                    "type": "RSI",
                                    "name": "rsi_medium",
                                    "params": {"period": 14},
                                }
                            ],
                        },
                    ],
                    "cross_timeframe_features": {
                        "rsi_divergence": {
                            "primary_timeframe": "1h",
                            "secondary_timeframe": "4h",
                            "primary_column": "rsi_short_1h",
                            "secondary_column": "rsi_medium_4h",
                            "operation": "difference",
                        }
                    },
                },
            },
            "data": {"directory": "./data"},
            "logging": {"level": "INFO"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            loader = ConfigLoader()

            # Load full configuration
            full_config = loader.load(temp_path)
            assert full_config is not None
            assert full_config.indicators is not None

            # Check legacy indicators
            assert len(full_config.indicators.indicators) == 1

            # Check multi-timeframe indicators
            assert full_config.indicators.multi_timeframe is not None
            mt_config = full_config.indicators.multi_timeframe

            assert len(mt_config.timeframes) == 2
            assert mt_config.column_standardization == True
            assert len(mt_config.cross_timeframe_features) == 1

            # Validate the configuration
            validation_result = loader.validate_multi_timeframe_config(mt_config)
            assert validation_result["valid"] == True

            # Check cross-timeframe feature validation
            assert "No timeframes configured" not in validation_result["errors"]

        finally:
            Path(temp_path).unlink()

    def test_configuration_error_handling(self):
        """Test error handling in configuration loading."""
        # Invalid timeframe configuration
        invalid_config_data = {
            "indicators": {
                "multi_timeframe": {
                    "timeframes": [{"timeframe": "invalid_timeframe", "indicators": []}]
                }
            },
            "data": {"directory": "./data"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(invalid_config_data, f)
            temp_path = f.name

        try:
            loader = ConfigLoader()

            with pytest.raises(Exception):  # Should raise validation error
                loader.load(temp_path)

        finally:
            Path(temp_path).unlink()
