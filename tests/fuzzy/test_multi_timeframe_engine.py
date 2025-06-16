"""
Tests for multi-timeframe fuzzy engine implementation.
"""

import pytest
import numpy as np
import pandas as pd
from typing import Dict, Any

from ktrdr.fuzzy.multi_timeframe_engine import (
    MultiTimeframeFuzzyEngine,
    TimeframeConfig,
    MultiTimeframeFuzzyResult,
    create_multi_timeframe_fuzzy_engine
)
from ktrdr.fuzzy.config import FuzzyConfig, FuzzySetConfig, TriangularMFConfig
from ktrdr.errors import ConfigurationError, DataValidationError, ProcessingError


class TestMultiTimeframeFuzzyEngine:
    """Tests for MultiTimeframeFuzzyEngine implementation."""

    @pytest.fixture
    def sample_multi_timeframe_config(self):
        """Sample multi-timeframe fuzzy configuration."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi", "macd"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {
                                "type": "triangular",
                                "parameters": [0, 20, 40]
                            },
                            "medium": {
                                "type": "triangular", 
                                "parameters": [30, 50, 70]
                            },
                            "high": {
                                "type": "triangular",
                                "parameters": [60, 80, 100]
                            }
                        },
                        "macd": {
                            "negative": {
                                "type": "triangular",
                                "parameters": [-1, -0.5, 0]
                            },
                            "positive": {
                                "type": "triangular",
                                "parameters": [0, 0.5, 1]
                            }
                        }
                    },
                    "weight": 0.5,
                    "enabled": True
                },
                "4h": {
                    "indicators": ["rsi"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {
                                "type": "trapezoidal",
                                "parameters": [0, 10, 30, 40]
                            },
                            "high": {
                                "type": "trapezoidal", 
                                "parameters": [60, 70, 90, 100]
                            }
                        }
                    },
                    "weight": 0.3,
                    "enabled": True
                },
                "1d": {
                    "indicators": ["trend"],
                    "fuzzy_sets": {
                        "trend": {
                            "downtrend": {
                                "type": "gaussian",
                                "parameters": [-1, 0.3]
                            },
                            "sideways": {
                                "type": "gaussian",
                                "parameters": [0, 0.2]
                            },
                            "uptrend": {
                                "type": "gaussian",
                                "parameters": [1, 0.3]
                            }
                        }
                    },
                    "weight": 0.2,
                    "enabled": True
                }
            },
            "indicators": ["rsi", "macd", "trend"]
        }

    @pytest.fixture
    def sample_single_timeframe_config(self):
        """Sample single-timeframe fuzzy configuration for backward compatibility."""
        return FuzzyConfig({
            "rsi": FuzzySetConfig({
                "low": TriangularMFConfig(type="triangular", parameters=[0, 20, 40]),
                "high": TriangularMFConfig(type="triangular", parameters=[60, 80, 100])
            })
        })

    @pytest.fixture 
    def sample_indicator_data(self):
        """Sample indicator data for multiple timeframes."""
        return {
            "1h": {
                "rsi": 35.0,
                "macd": -0.02
            },
            "4h": {
                "rsi": 45.0
            },
            "1d": {
                "trend": 0.8
            }
        }

    def test_multi_timeframe_initialization(self, sample_multi_timeframe_config):
        """Test initialization with multi-timeframe configuration."""
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        
        assert engine.is_multi_timeframe_enabled()
        assert len(engine.get_supported_timeframes()) == 3
        assert "1h" in engine.get_supported_timeframes()
        assert "4h" in engine.get_supported_timeframes() 
        assert "1d" in engine.get_supported_timeframes()

    def test_single_timeframe_backward_compatibility(self, sample_single_timeframe_config):
        """Test backward compatibility with single-timeframe configurations."""
        engine = MultiTimeframeFuzzyEngine(sample_single_timeframe_config)
        
        assert not engine.is_multi_timeframe_enabled()
        assert len(engine.get_supported_timeframes()) == 0

    def test_invalid_configuration(self):
        """Test that invalid configurations raise appropriate errors."""
        # Empty configuration
        with pytest.raises(ConfigurationError) as exc_info:
            MultiTimeframeFuzzyEngine({})
        assert "cannot be empty" in str(exc_info.value)

        # Missing required keys
        with pytest.raises(ConfigurationError) as exc_info:
            MultiTimeframeFuzzyEngine({"timeframes": {}})
        assert "missing required key: indicators" in str(exc_info.value)

        # Invalid timeframe configuration - missing fuzzy_sets
        with pytest.raises(ConfigurationError) as exc_info:
            MultiTimeframeFuzzyEngine({
                "timeframes": {
                    "1h": {
                        "indicators": ["rsi"]  # Missing fuzzy_sets
                    }
                },
                "indicators": ["rsi"]
            })
        assert "missing required key: fuzzy_sets" in str(exc_info.value)

        # Invalid timeframe configuration - empty indicators
        with pytest.raises(ConfigurationError) as exc_info:
            MultiTimeframeFuzzyEngine({
                "timeframes": {
                    "1h": {
                        "indicators": [],  # Empty indicators
                        "fuzzy_sets": {}
                    }
                },
                "indicators": ["rsi"]
            })
        assert "indicators must be a non-empty list" in str(exc_info.value)

    def test_timeframe_config_objects(self, sample_multi_timeframe_config):
        """Test that TimeframeConfig objects are created properly."""
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        configs = engine.get_timeframe_configurations()
        
        assert len(configs) == 3
        
        # Check 1h config
        tf_1h = configs["1h"]
        assert isinstance(tf_1h, TimeframeConfig)
        assert tf_1h.timeframe == "1h"
        assert tf_1h.indicators == ["rsi", "macd"]
        assert tf_1h.weight == 0.5
        assert tf_1h.enabled is True

        # Check 4h config 
        tf_4h = configs["4h"]
        assert tf_4h.timeframe == "4h"
        assert tf_4h.indicators == ["rsi"]
        assert tf_4h.weight == 0.3

        # Check 1d config
        tf_1d = configs["1d"]
        assert tf_1d.timeframe == "1d"
        assert tf_1d.indicators == ["trend"]
        assert tf_1d.weight == 0.2

    def test_fuzzify_multi_timeframe_basic(self, sample_multi_timeframe_config, sample_indicator_data):
        """Test basic multi-timeframe fuzzification."""
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        result = engine.fuzzify_multi_timeframe(sample_indicator_data)
        
        assert isinstance(result, MultiTimeframeFuzzyResult)
        assert len(result.timeframe_results) == 3
        assert "1h" in result.timeframe_results
        assert "4h" in result.timeframe_results
        assert "1d" in result.timeframe_results
        
        # Check that fuzzy values have timeframe suffixes
        fuzzy_keys = list(result.fuzzy_values.keys())
        assert any("_1h" in key for key in fuzzy_keys)
        assert any("_4h" in key for key in fuzzy_keys)
        assert any("_1d" in key for key in fuzzy_keys)

    def test_fuzzify_with_timeframe_filter(self, sample_multi_timeframe_config, sample_indicator_data):
        """Test fuzzification with timeframe filtering."""
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        
        # Filter to only process 1h timeframe
        result = engine.fuzzify_multi_timeframe(
            sample_indicator_data, 
            timeframe_filter=["1h"]
        )
        
        assert len(result.timeframe_results) == 1
        assert "1h" in result.timeframe_results
        assert "4h" not in result.timeframe_results
        assert "1d" not in result.timeframe_results

    def test_invalid_indicator_data(self, sample_multi_timeframe_config):
        """Test validation of indicator data."""
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        
        # Empty data
        with pytest.raises(DataValidationError) as exc_info:
            engine.fuzzify_multi_timeframe({})
        assert "cannot be empty" in str(exc_info.value)

        # Invalid data structure
        with pytest.raises(DataValidationError) as exc_info:
            engine.fuzzify_multi_timeframe({"1h": "not a dict"})
        assert "must be a dictionary" in str(exc_info.value)

        # Invalid indicator value
        with pytest.raises(DataValidationError) as exc_info:
            engine.fuzzify_multi_timeframe({
                "1h": {"rsi": "not a number"}
            })
        assert "Invalid value" in str(exc_info.value)

        # NaN value
        with pytest.raises(DataValidationError) as exc_info:
            engine.fuzzify_multi_timeframe({
                "1h": {"rsi": np.nan}
            })
        assert "Invalid value" in str(exc_info.value)

    def test_disabled_timeframe(self, sample_multi_timeframe_config, sample_indicator_data):
        """Test that disabled timeframes are skipped."""
        # Disable 4h timeframe
        sample_multi_timeframe_config["timeframes"]["4h"]["enabled"] = False
        
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        result = engine.fuzzify_multi_timeframe(sample_indicator_data)
        
        # Should only process 1h and 1d timeframes
        assert len(result.timeframe_results) == 2
        assert "1h" in result.timeframe_results
        assert "4h" not in result.timeframe_results
        assert "1d" in result.timeframe_results

    def test_missing_indicator_data_graceful_handling(self, sample_multi_timeframe_config):
        """Test graceful handling of missing indicator data."""
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        
        # Data missing for some timeframes
        partial_data = {
            "1h": {
                "rsi": 35.0
                # missing "macd"
            },
            # missing "4h" entirely
            "1d": {
                "trend": 0.8
            }
        }
        
        result = engine.fuzzify_multi_timeframe(partial_data)
        
        # Should process available timeframes/indicators
        assert "1h" in result.timeframe_results
        assert "1d" in result.timeframe_results
        
        # Should only process indicators that have data
        # 1h should only have RSI results (no MACD since data is missing)
        assert "rsi_1h_low" in result.timeframe_results["1h"]
        assert any("macd" in key for key in result.timeframe_results["1h"].keys()) is False
        
        # Should successfully process available timeframes (no warnings for missing individual indicators)
        # Warnings are only added for timeframe processing failures, not missing indicators
        assert len(result.warnings) == 0

    def test_result_metadata(self, sample_multi_timeframe_config, sample_indicator_data):
        """Test that result metadata is properly populated."""
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        result = engine.fuzzify_multi_timeframe(sample_indicator_data)
        
        metadata = result.metadata
        assert "processed_timeframes" in metadata
        assert "total_fuzzy_values" in metadata
        assert "input_timeframes" in metadata
        
        assert len(metadata["processed_timeframes"]) == 3
        assert metadata["total_fuzzy_values"] > 0
        assert set(metadata["input_timeframes"]) == {"1h", "4h", "1d"}

    def test_processing_time_measurement(self, sample_multi_timeframe_config, sample_indicator_data):
        """Test that processing time is measured."""
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        result = engine.fuzzify_multi_timeframe(sample_indicator_data)
        
        assert result.processing_time > 0
        assert result.processing_time < 1.0  # Should be fast

    def test_membership_function_types(self, sample_multi_timeframe_config):
        """Test that different membership function types work correctly."""
        engine = MultiTimeframeFuzzyEngine(sample_multi_timeframe_config)
        
        # Test data that should trigger different membership functions
        test_data = {
            "1h": {"rsi": 25.0, "macd": 0.3},  # Triangular MFs
            "4h": {"rsi": 75.0},               # Trapezoidal MFs  
            "1d": {"trend": 0.5}               # Gaussian MFs
        }
        
        result = engine.fuzzify_multi_timeframe(test_data)
        
        # Should have results from all timeframes
        assert len(result.timeframe_results) == 3
        assert all(len(tf_result) > 0 for tf_result in result.timeframe_results.values())

    def test_create_factory_function(self, sample_multi_timeframe_config):
        """Test the factory function for creating engines."""
        engine = create_multi_timeframe_fuzzy_engine(sample_multi_timeframe_config)
        
        assert isinstance(engine, MultiTimeframeFuzzyEngine)
        assert engine.is_multi_timeframe_enabled()


class TestTimeframeConfig:
    """Tests for TimeframeConfig dataclass."""

    def test_timeframe_config_creation(self):
        """Test creating TimeframeConfig objects."""
        config = TimeframeConfig(
            timeframe="1h",
            indicators=["rsi", "macd"], 
            fuzzy_sets={},
            weight=0.5,
            enabled=True
        )
        
        assert config.timeframe == "1h"
        assert config.indicators == ["rsi", "macd"]
        assert config.weight == 0.5
        assert config.enabled is True

    def test_timeframe_config_defaults(self):
        """Test default values for TimeframeConfig."""
        config = TimeframeConfig(
            timeframe="4h",
            indicators=["sma"],
            fuzzy_sets={}
        )
        
        assert config.weight == 1.0  # Default weight
        assert config.enabled is True  # Default enabled


class TestMultiTimeframeFuzzyResult:
    """Tests for MultiTimeframeFuzzyResult dataclass."""

    def test_result_creation(self):
        """Test creating MultiTimeframeFuzzyResult objects."""
        result = MultiTimeframeFuzzyResult(
            fuzzy_values={"rsi_low_1h": 0.8, "macd_negative_1h": 0.3},
            timeframe_results={"1h": {"rsi_low": 0.8, "macd_negative": 0.3}},
            metadata={"processed_timeframes": ["1h"]},
            warnings=["Missing data for 4h"],
            processing_time=0.05
        )
        
        assert len(result.fuzzy_values) == 2
        assert len(result.timeframe_results) == 1
        assert len(result.warnings) == 1
        assert result.processing_time == 0.05