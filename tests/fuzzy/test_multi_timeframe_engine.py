"""
Unit tests for Multi-Timeframe Fuzzy Engine.

This module contains comprehensive tests for the MultiTimeframeFuzzyEngine
and enhanced membership functions.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch

from ktrdr.fuzzy.multi_timeframe_engine import (
    MultiTimeframeFuzzyEngine,
    TimeframeConfig,
    MultiTimeframeFuzzyResult,
    create_multi_timeframe_fuzzy_engine
)
from ktrdr.fuzzy.membership import (
    TrapezoidalMF,
    GaussianMF,
    MembershipFunctionFactory
)
from ktrdr.fuzzy.config import FuzzyConfig, FuzzySetConfig, TriangularMFConfig
from ktrdr.errors import ConfigurationError, ProcessingError, DataValidationError


class TestEnhancedMembershipFunctions:
    """Test enhanced membership functions."""
    
    def test_trapezoidal_mf_initialization(self):
        """Test TrapezoidalMF initialization."""
        # Valid parameters
        mf = TrapezoidalMF([0, 20, 30, 50])
        assert mf.a == 0
        assert mf.b == 20
        assert mf.c == 30
        assert mf.d == 50
        
    def test_trapezoidal_mf_invalid_parameters(self):
        """Test TrapezoidalMF with invalid parameters."""
        # Wrong number of parameters
        with pytest.raises(ConfigurationError, match="exactly 4 parameters"):
            TrapezoidalMF([0, 20, 30])
        
        # Invalid parameter order
        with pytest.raises(ConfigurationError, match="must satisfy: a ≤ b ≤ c ≤ d"):
            TrapezoidalMF([30, 20, 40, 50])
    
    def test_trapezoidal_mf_evaluation(self):
        """Test TrapezoidalMF evaluation."""
        mf = TrapezoidalMF([0, 20, 30, 50])
        
        # Test scalar evaluation
        assert mf.evaluate(-10) == 0.0  # Below range
        assert mf.evaluate(10) == 0.5   # Rising edge
        assert mf.evaluate(25) == 1.0   # Plateau
        assert mf.evaluate(40) == 0.5   # Falling edge
        assert mf.evaluate(60) == 0.0   # Above range
        
        # Test with numpy array
        x = np.array([-10, 10, 25, 40, 60])
        expected = np.array([0.0, 0.5, 1.0, 0.5, 0.0])
        result = mf.evaluate(x)
        np.testing.assert_array_almost_equal(result, expected)
    
    def test_gaussian_mf_initialization(self):
        """Test GaussianMF initialization."""
        # Valid parameters
        mf = GaussianMF([50, 10])
        assert mf.mu == 50
        assert mf.sigma == 10
        
    def test_gaussian_mf_invalid_parameters(self):
        """Test GaussianMF with invalid parameters."""
        # Wrong number of parameters
        with pytest.raises(ConfigurationError, match="exactly 2 parameters"):
            GaussianMF([50])
        
        # Invalid sigma
        with pytest.raises(ConfigurationError, match="sigma must be greater than 0"):
            GaussianMF([50, -5])
    
    def test_gaussian_mf_evaluation(self):
        """Test GaussianMF evaluation."""
        mf = GaussianMF([50, 10])
        
        # Test scalar evaluation
        assert mf.evaluate(50) == 1.0  # Peak
        assert abs(mf.evaluate(60) - np.exp(-0.5)) < 1e-10  # One sigma away
        
        # Test with numpy array
        x = np.array([30, 40, 50, 60, 70])
        result = mf.evaluate(x)
        assert result[2] == 1.0  # Peak at mu=50
        assert all(result >= 0) and all(result <= 1)  # Valid range
    
    def test_membership_function_factory(self):
        """Test MembershipFunctionFactory."""
        # Test triangular
        mf = MembershipFunctionFactory.create("triangular", [0, 50, 100])
        assert hasattr(mf, 'a') and mf.a == 0
        
        # Test trapezoidal
        mf = MembershipFunctionFactory.create("trapezoidal", [0, 20, 30, 50])
        assert hasattr(mf, 'd') and mf.d == 50
        
        # Test gaussian
        mf = MembershipFunctionFactory.create("gaussian", [50, 10])
        assert hasattr(mf, 'mu') and mf.mu == 50
        
        # Test unknown type
        with pytest.raises(ConfigurationError, match="Unknown membership function type"):
            MembershipFunctionFactory.create("unknown", [0, 50, 100])
        
        # Test supported types
        types = MembershipFunctionFactory.get_supported_types()
        assert "triangular" in types
        assert "trapezoidal" in types
        assert "gaussian" in types


class TestTimeframeConfig:
    """Test TimeframeConfig dataclass."""
    
    def test_timeframe_config_creation(self):
        """Test TimeframeConfig creation."""
        config = TimeframeConfig(
            timeframe="1h",
            indicators=["rsi", "macd"],
            fuzzy_sets={},
            weight=0.8,
            enabled=True
        )
        
        assert config.timeframe == "1h"
        assert config.indicators == ["rsi", "macd"]
        assert config.weight == 0.8
        assert config.enabled is True


class TestMultiTimeframeFuzzyResult:
    """Test MultiTimeframeFuzzyResult dataclass."""
    
    def test_result_creation(self):
        """Test MultiTimeframeFuzzyResult creation."""
        result = MultiTimeframeFuzzyResult(
            fuzzy_values={"rsi_low_1h": 0.8, "rsi_high_4h": 0.3},
            timeframe_results={"1h": {"rsi_low": 0.8}, "4h": {"rsi_high": 0.3}},
            metadata={"processed_timeframes": ["1h", "4h"]},
            warnings=["Missing data for 1d"],
            processing_time=0.05
        )
        
        assert len(result.fuzzy_values) == 2
        assert len(result.timeframe_results) == 2
        assert len(result.warnings) == 1
        assert result.processing_time == 0.05


class TestMultiTimeframeFuzzyEngine:
    """Test MultiTimeframeFuzzyEngine class."""
    
    @pytest.fixture
    def single_timeframe_config(self):
        """Create a simple single-timeframe config for backward compatibility testing."""
        mf_config = TriangularMFConfig(type="triangular", parameters=[0, 50, 100])
        fuzzy_set = FuzzySetConfig(root={"high": mf_config})
        return FuzzyConfig(root={"rsi": fuzzy_set})
    
    @pytest.fixture
    def multi_timeframe_config(self):
        """Create a multi-timeframe fuzzy configuration."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi", "macd"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {"type": "triangular", "parameters": [0, 30, 40]},
                            "high": {"type": "triangular", "parameters": [60, 70, 100]}
                        },
                        "macd": {
                            "negative": {"type": "trapezoidal", "parameters": [-1, -0.5, -0.1, 0]},
                            "positive": {"type": "trapezoidal", "parameters": [0, 0.1, 0.5, 1]}
                        }
                    },
                    "weight": 1.0,
                    "enabled": True
                },
                "4h": {
                    "indicators": ["rsi", "trend"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {"type": "triangular", "parameters": [0, 25, 35]},
                            "high": {"type": "triangular", "parameters": [65, 75, 100]}
                        },
                        "trend": {
                            "down": {"type": "gaussian", "parameters": [0.3, 0.1]},
                            "up": {"type": "gaussian", "parameters": [0.7, 0.1]}
                        }
                    },
                    "weight": 1.5,
                    "enabled": True
                }
            },
            "indicators": ["rsi", "macd", "trend"]
        }
    
    def test_backward_compatibility_initialization(self, single_timeframe_config):
        """Test backward compatibility with single-timeframe configs."""
        engine = MultiTimeframeFuzzyEngine(single_timeframe_config)
        
        assert not engine.is_multi_timeframe_enabled()
        assert engine.get_supported_timeframes() == []
        assert "rsi" in engine.get_available_indicators()
    
    def test_multi_timeframe_initialization(self, multi_timeframe_config):
        """Test multi-timeframe initialization."""
        engine = MultiTimeframeFuzzyEngine(multi_timeframe_config)
        
        assert engine.is_multi_timeframe_enabled()
        supported_timeframes = engine.get_supported_timeframes()
        assert "1h" in supported_timeframes
        assert "4h" in supported_timeframes
        
        # Check timeframe configurations
        tf_configs = engine.get_timeframe_configurations()
        assert "1h" in tf_configs
        assert "4h" in tf_configs
        assert tf_configs["1h"].weight == 1.0
        assert tf_configs["4h"].weight == 1.5
    
    def test_invalid_multi_timeframe_config(self):
        """Test invalid multi-timeframe configuration."""
        # Empty config
        with pytest.raises(ConfigurationError, match="cannot be empty"):
            MultiTimeframeFuzzyEngine({})
        
        # Missing required keys
        with pytest.raises(ConfigurationError, match="missing required key"):
            MultiTimeframeFuzzyEngine({"indicators": []})
        
        # Invalid timeframes structure
        with pytest.raises(ConfigurationError, match="must be a non-empty dictionary"):
            MultiTimeframeFuzzyEngine({
                "timeframes": [],
                "indicators": []
            })
    
    def test_single_timeframe_fuzzify(self, single_timeframe_config):
        """Test single-value fuzzification in backward compatibility mode."""
        engine = MultiTimeframeFuzzyEngine(single_timeframe_config)
        
        # Test with scalar value
        result = engine.fuzzify("rsi", 75.0)
        assert isinstance(result, dict)
        assert "rsi_high" in result
        assert 0 <= result["rsi_high"] <= 1
    
    def test_multi_timeframe_fuzzify_success(self, multi_timeframe_config):
        """Test successful multi-timeframe fuzzification."""
        engine = MultiTimeframeFuzzyEngine(multi_timeframe_config)
        
        indicator_data = {
            "1h": {"rsi": 35.0, "macd": -0.2},
            "4h": {"rsi": 45.0, "trend": 0.7}
        }
        
        result = engine.fuzzify_multi_timeframe(indicator_data)
        
        assert isinstance(result, MultiTimeframeFuzzyResult)
        assert len(result.fuzzy_values) > 0
        assert "1h" in result.timeframe_results
        assert "4h" in result.timeframe_results
        assert result.processing_time > 0
        
        # Check that fuzzy values have proper timeframe suffixes
        fuzzy_keys = list(result.fuzzy_values.keys())
        assert any(key.endswith("_1h") for key in fuzzy_keys)
        assert any(key.endswith("_4h") for key in fuzzy_keys)
    
    def test_multi_timeframe_fuzzify_with_filter(self, multi_timeframe_config):
        """Test multi-timeframe fuzzification with timeframe filter."""
        engine = MultiTimeframeFuzzyEngine(multi_timeframe_config)
        
        indicator_data = {
            "1h": {"rsi": 35.0, "macd": -0.2},
            "4h": {"rsi": 45.0, "trend": 0.7}
        }
        
        # Filter to only process 1h
        result = engine.fuzzify_multi_timeframe(indicator_data, timeframe_filter=["1h"])
        
        assert "1h" in result.timeframe_results
        assert "4h" not in result.timeframe_results
        
        # All fuzzy values should be from 1h timeframe
        fuzzy_keys = list(result.fuzzy_values.keys())
        assert all(key.endswith("_1h") for key in fuzzy_keys)
    
    def test_multi_timeframe_fuzzify_invalid_data(self, multi_timeframe_config):
        """Test multi-timeframe fuzzification with invalid data."""
        engine = MultiTimeframeFuzzyEngine(multi_timeframe_config)
        
        # Empty data
        with pytest.raises(DataValidationError, match="cannot be empty"):
            engine.fuzzify_multi_timeframe({})
        
        # Invalid indicator structure
        with pytest.raises(DataValidationError, match="must be a dictionary"):
            engine.fuzzify_multi_timeframe({"1h": "not_a_dict"})
        
        # Invalid indicator value
        with pytest.raises(DataValidationError, match="Invalid value"):
            engine.fuzzify_multi_timeframe({"1h": {"rsi": "not_a_number"}})
    
    def test_multi_timeframe_fuzzify_missing_indicators(self, multi_timeframe_config):
        """Test graceful handling of missing indicators."""
        engine = MultiTimeframeFuzzyEngine(multi_timeframe_config)
        
        # Missing some indicators
        indicator_data = {
            "1h": {"rsi": 35.0},  # Missing macd
            "4h": {"rsi": 45.0}   # Missing trend
        }
        
        result = engine.fuzzify_multi_timeframe(indicator_data)
        
        # Should still succeed with available indicators
        assert isinstance(result, MultiTimeframeFuzzyResult)
        assert len(result.fuzzy_values) > 0
        assert "1h" in result.timeframe_results
        assert "4h" in result.timeframe_results
    
    def test_multi_timeframe_fuzzify_processing_error(self, multi_timeframe_config):
        """Test handling of processing errors during fuzzification."""
        engine = MultiTimeframeFuzzyEngine(multi_timeframe_config)
        
        # Mock the base fuzzify method to raise an error
        with patch.object(engine, 'fuzzify', side_effect=ProcessingError("Test error", "TEST", {})):
            indicator_data = {"1h": {"rsi": 35.0}}
            
            result = engine.fuzzify_multi_timeframe(indicator_data)
            
            # Should gracefully handle error and include warning
            assert len(result.warnings) > 0
            assert "Failed to process timeframe" in result.warnings[0]
    
    def test_factory_function(self, multi_timeframe_config):
        """Test factory function."""
        engine = create_multi_timeframe_fuzzy_engine(multi_timeframe_config)
        
        assert isinstance(engine, MultiTimeframeFuzzyEngine)
        assert engine.is_multi_timeframe_enabled()
    
    def test_timeframe_specific_membership_functions(self, multi_timeframe_config):
        """Test that different membership functions work correctly across timeframes."""
        engine = MultiTimeframeFuzzyEngine(multi_timeframe_config)
        
        indicator_data = {
            "1h": {"rsi": 35.0, "macd": -0.2},  # RSI uses triangular, MACD uses trapezoidal
            "4h": {"rsi": 25.0, "trend": 0.7}   # RSI uses triangular, trend uses gaussian
        }
        
        result = engine.fuzzify_multi_timeframe(indicator_data)
        
        # Verify different membership functions produced results
        assert len(result.fuzzy_values) > 0
        
        # Check that both timeframes processed successfully
        assert "1h" in result.timeframe_results
        assert "4h" in result.timeframe_results
        
        # Verify RSI processing in both timeframes (different thresholds)
        tf_1h_result = result.timeframe_results["1h"]
        tf_4h_result = result.timeframe_results["4h"]
        
        # Both should have RSI fuzzy values
        rsi_keys_1h = [k for k in tf_1h_result.keys() if k.startswith("rsi_")]
        rsi_keys_4h = [k for k in tf_4h_result.keys() if k.startswith("rsi_")]
        
        assert len(rsi_keys_1h) > 0
        assert len(rsi_keys_4h) > 0


class TestMultiTimeframeFuzzyIntegration:
    """Test integration scenarios for multi-timeframe fuzzy processing."""
    
    @pytest.fixture
    def complex_config(self):
        """Create a complex multi-timeframe configuration."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi", "macd", "bb_position"],
                    "fuzzy_sets": {
                        "rsi": {
                            "oversold": {"type": "triangular", "parameters": [0, 30, 40]},
                            "neutral": {"type": "trapezoidal", "parameters": [35, 45, 55, 65]},
                            "overbought": {"type": "triangular", "parameters": [60, 70, 100]}
                        },
                        "macd": {
                            "negative": {"type": "triangular", "parameters": [-1, -0.5, 0]},
                            "positive": {"type": "triangular", "parameters": [0, 0.5, 1]}
                        },
                        "bb_position": {
                            "lower": {"type": "gaussian", "parameters": [0.2, 0.1]},
                            "upper": {"type": "gaussian", "parameters": [0.8, 0.1]}
                        }
                    },
                    "weight": 1.0,
                    "enabled": True
                },
                "4h": {
                    "indicators": ["rsi", "trend_strength"],
                    "fuzzy_sets": {
                        "rsi": {
                            "oversold": {"type": "triangular", "parameters": [0, 25, 35]},
                            "overbought": {"type": "triangular", "parameters": [65, 75, 100]}
                        },
                        "trend_strength": {
                            "weak": {"type": "triangular", "parameters": [0, 0.3, 0.5]},
                            "strong": {"type": "triangular", "parameters": [0.5, 0.7, 1.0]}
                        }
                    },
                    "weight": 1.5,
                    "enabled": True
                },
                "1d": {
                    "indicators": ["trend_direction"],
                    "fuzzy_sets": {
                        "trend_direction": {
                            "down": {"type": "triangular", "parameters": [-1, -0.5, 0]},
                            "up": {"type": "triangular", "parameters": [0, 0.5, 1]}
                        }
                    },
                    "weight": 2.0,
                    "enabled": True
                }
            },
            "indicators": ["rsi", "macd", "bb_position", "trend_strength", "trend_direction"]
        }
    
    def test_complex_multi_timeframe_processing(self, complex_config):
        """Test complex multi-timeframe processing with many indicators."""
        engine = MultiTimeframeFuzzyEngine(complex_config)
        
        indicator_data = {
            "1h": {"rsi": 35.0, "macd": -0.1, "bb_position": 0.2},
            "4h": {"rsi": 28.0, "trend_strength": 0.8},
            "1d": {"trend_direction": 0.6}
        }
        
        result = engine.fuzzify_multi_timeframe(indicator_data)
        
        # Verify all timeframes processed
        assert len(result.timeframe_results) == 3
        assert "1h" in result.timeframe_results
        assert "4h" in result.timeframe_results
        assert "1d" in result.timeframe_results
        
        # Verify fuzzy values created for all timeframes
        fuzzy_keys = list(result.fuzzy_values.keys())
        assert any(key.endswith("_1h") for key in fuzzy_keys)
        assert any(key.endswith("_4h") for key in fuzzy_keys)
        assert any(key.endswith("_1d") for key in fuzzy_keys)
        
        # Verify metadata
        metadata = result.metadata
        assert len(metadata["processed_timeframes"]) == 3
        assert metadata["total_fuzzy_values"] == len(result.fuzzy_values)
    
    def test_partial_timeframe_availability(self, complex_config):
        """Test processing when only some timeframes have data."""
        engine = MultiTimeframeFuzzyEngine(complex_config)
        
        # Only provide data for 1h and 4h
        indicator_data = {
            "1h": {"rsi": 35.0, "macd": -0.1},
            "4h": {"rsi": 28.0, "trend_strength": 0.8}
            # Missing 1d data
        }
        
        result = engine.fuzzify_multi_timeframe(indicator_data)
        
        # Should process available timeframes
        assert "1h" in result.timeframe_results
        assert "4h" in result.timeframe_results
        assert "1d" not in result.timeframe_results
        
        # Verify only available timeframes in fuzzy values
        fuzzy_keys = list(result.fuzzy_values.keys())
        assert any(key.endswith("_1h") for key in fuzzy_keys)
        assert any(key.endswith("_4h") for key in fuzzy_keys)
        assert not any(key.endswith("_1d") for key in fuzzy_keys)
    
    def test_disabled_timeframe_handling(self, complex_config):
        """Test handling of disabled timeframes."""
        # Disable 4h timeframe
        complex_config["timeframes"]["4h"]["enabled"] = False
        
        engine = MultiTimeframeFuzzyEngine(complex_config)
        
        indicator_data = {
            "1h": {"rsi": 35.0, "macd": -0.1},
            "4h": {"rsi": 28.0, "trend_strength": 0.8},  # Should be ignored
            "1d": {"trend_direction": 0.6}
        }
        
        result = engine.fuzzify_multi_timeframe(indicator_data)
        
        # Should skip disabled 4h timeframe
        assert "1h" in result.timeframe_results
        assert "4h" not in result.timeframe_results
        assert "1d" in result.timeframe_results