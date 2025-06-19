"""
Tests for multi-timeframe fuzzy-indicator integration pipeline.
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any
from unittest.mock import Mock, patch

from ktrdr.fuzzy.indicator_integration import (
    MultiTimeframeFuzzyIndicatorPipeline,
    IntegratedFuzzyResult,
    create_integrated_pipeline,
)
from ktrdr.errors import ProcessingError, ConfigurationError


class TestMultiTimeframeFuzzyIndicatorPipeline:
    """Tests for the integrated fuzzy-indicator pipeline."""

    @pytest.fixture
    def sample_indicator_config(self):
        """Sample indicator configuration."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": [
                        {"type": "RSI", "period": 14},
                        {"type": "MACD", "fast_period": 12, "slow_period": 26},
                    ]
                },
                "4h": {
                    "indicators": [
                        {"type": "RSI", "period": 14},
                        {"type": "SMA", "period": 20},
                    ]
                },
            }
        }

    @pytest.fixture
    def sample_fuzzy_config(self):
        """Sample fuzzy configuration."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi", "macd"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {"type": "triangular", "parameters": [0, 20, 40]},
                            "high": {"type": "triangular", "parameters": [60, 80, 100]},
                        },
                        "macd": {
                            "negative": {
                                "type": "triangular",
                                "parameters": [-1, -0.5, 0],
                            },
                            "positive": {
                                "type": "triangular",
                                "parameters": [0, 0.5, 1],
                            },
                        },
                    },
                    "weight": 0.7,
                    "enabled": True,
                },
                "4h": {
                    "indicators": ["rsi", "sma"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {"type": "triangular", "parameters": [0, 30, 50]},
                            "high": {"type": "triangular", "parameters": [50, 70, 100]},
                        },
                        "sma": {
                            "below": {"type": "triangular", "parameters": [-10, -5, 0]},
                            "above": {"type": "triangular", "parameters": [0, 5, 10]},
                        },
                    },
                    "weight": 0.3,
                    "enabled": True,
                },
            },
            "indicators": ["rsi", "macd", "sma"],
        }

    @pytest.fixture
    def sample_market_data(self):
        """Sample market data for multiple timeframes."""
        # Create sample OHLCV data
        dates_1h = pd.date_range("2024-01-01", periods=100, freq="1h")
        dates_4h = pd.date_range("2024-01-01", periods=25, freq="4h")

        return {
            "1h": pd.DataFrame(
                {
                    "open": np.random.uniform(100, 110, len(dates_1h)),
                    "high": np.random.uniform(105, 115, len(dates_1h)),
                    "low": np.random.uniform(95, 105, len(dates_1h)),
                    "close": np.random.uniform(100, 110, len(dates_1h)),
                    "volume": np.random.uniform(1000, 10000, len(dates_1h)),
                },
                index=dates_1h,
            ),
            "4h": pd.DataFrame(
                {
                    "open": np.random.uniform(100, 110, len(dates_4h)),
                    "high": np.random.uniform(105, 115, len(dates_4h)),
                    "low": np.random.uniform(95, 105, len(dates_4h)),
                    "close": np.random.uniform(100, 110, len(dates_4h)),
                    "volume": np.random.uniform(4000, 40000, len(dates_4h)),
                },
                index=dates_4h,
            ),
        }

    def test_pipeline_initialization(
        self, sample_indicator_config, sample_fuzzy_config
    ):
        """Test successful pipeline initialization."""
        pipeline = MultiTimeframeFuzzyIndicatorPipeline(
            indicator_config=sample_indicator_config, fuzzy_config=sample_fuzzy_config
        )

        assert pipeline.indicator_engine is not None
        assert pipeline.fuzzy_engine is not None
        assert pipeline.enable_error_recovery is True
        assert pipeline.enable_performance_monitoring is True

    def test_configuration_compatibility_validation(self, sample_indicator_config):
        """Test configuration compatibility validation."""
        # Incompatible fuzzy config (no common timeframes)
        incompatible_fuzzy_config = {
            "timeframes": {
                "1d": {  # Different timeframe
                    "indicators": ["rsi"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {"type": "triangular", "parameters": [0, 30, 50]}
                        }
                    },
                    "weight": 1.0,
                    "enabled": True,
                }
            },
            "indicators": ["rsi"],
        }

        with pytest.raises(ConfigurationError) as exc_info:
            MultiTimeframeFuzzyIndicatorPipeline(
                indicator_config=sample_indicator_config,
                fuzzy_config=incompatible_fuzzy_config,
            )
        assert "No common timeframes" in str(exc_info.value)

    @patch("ktrdr.fuzzy.indicator_integration.MultiTimeframeIndicatorEngine")
    @patch("ktrdr.fuzzy.indicator_integration.MultiTimeframeFuzzyEngine")
    def test_process_market_data_success(
        self,
        mock_fuzzy_engine,
        mock_indicator_engine,
        sample_indicator_config,
        sample_fuzzy_config,
        sample_market_data,
    ):
        """Test successful market data processing."""
        # Mock indicator engine
        mock_indicator_instance = Mock()
        mock_indicator_engine.return_value = mock_indicator_instance
        mock_indicator_instance.get_supported_timeframes.return_value = ["1h", "4h"]
        mock_indicator_instance.apply_multi_timeframe.return_value = {
            "1h": pd.DataFrame(
                {"RSI_14_1h": [35.0, 45.0, 55.0], "MACD_12_26_1h": [0.1, -0.2, 0.3]}
            ),
            "4h": pd.DataFrame(
                {"RSI_14_4h": [40.0, 50.0], "SMA_20_4h": [105.0, 106.0]}
            ),
        }

        # Mock fuzzy engine
        mock_fuzzy_instance = Mock()
        mock_fuzzy_engine.return_value = mock_fuzzy_instance
        mock_fuzzy_instance.get_supported_timeframes.return_value = ["1h", "4h"]
        mock_fuzzy_instance.is_multi_timeframe_enabled.return_value = True

        # Mock fuzzy result
        from ktrdr.fuzzy.multi_timeframe_engine import MultiTimeframeFuzzyResult

        mock_fuzzy_result = MultiTimeframeFuzzyResult(
            fuzzy_values={"rsi_low_1h": 0.8, "macd_positive_1h": 0.6},
            timeframe_results={"1h": {"rsi_low": 0.8, "macd_positive": 0.6}},
            metadata={"processed_timeframes": ["1h"]},
            warnings=[],
            processing_time=0.05,
        )
        mock_fuzzy_instance.fuzzify_multi_timeframe.return_value = mock_fuzzy_result

        # Create pipeline and process
        pipeline = MultiTimeframeFuzzyIndicatorPipeline(
            indicator_config=sample_indicator_config, fuzzy_config=sample_fuzzy_config
        )

        result = pipeline.process_market_data(sample_market_data)

        # Verify result
        assert isinstance(result, IntegratedFuzzyResult)
        assert len(result.errors) == 0
        assert result.total_processing_time > 0
        assert result.fuzzy_result == mock_fuzzy_result
        assert "processed_indicator_timeframes" in result.processing_metadata

    @patch("ktrdr.fuzzy.indicator_integration.MultiTimeframeIndicatorEngine")
    @patch("ktrdr.fuzzy.indicator_integration.MultiTimeframeFuzzyEngine")
    def test_process_market_data_indicator_failure(
        self,
        mock_fuzzy_engine,
        mock_indicator_engine,
        sample_indicator_config,
        sample_fuzzy_config,
        sample_market_data,
    ):
        """Test handling of indicator processing failure."""
        # Mock indicator engine to fail
        mock_indicator_instance = Mock()
        mock_indicator_engine.return_value = mock_indicator_instance
        mock_indicator_instance.get_supported_timeframes.return_value = ["1h", "4h"]
        mock_indicator_instance.apply_multi_timeframe.side_effect = Exception(
            "Indicator processing failed"
        )

        # Mock fuzzy engine
        mock_fuzzy_instance = Mock()
        mock_fuzzy_engine.return_value = mock_fuzzy_instance
        mock_fuzzy_instance.get_supported_timeframes.return_value = ["1h", "4h"]
        mock_fuzzy_instance.is_multi_timeframe_enabled.return_value = True

        # Create pipeline
        pipeline = MultiTimeframeFuzzyIndicatorPipeline(
            indicator_config=sample_indicator_config,
            fuzzy_config=sample_fuzzy_config,
            enable_error_recovery=True,
        )

        result = pipeline.process_market_data(sample_market_data)

        # Should have errors but not raise exception
        assert len(result.errors) > 0
        assert "Indicator processing failed" in result.errors[0]
        assert result.total_processing_time > 0

    @patch("ktrdr.fuzzy.indicator_integration.MultiTimeframeIndicatorEngine")
    @patch("ktrdr.fuzzy.indicator_integration.MultiTimeframeFuzzyEngine")
    def test_process_market_data_fail_fast(
        self,
        mock_fuzzy_engine,
        mock_indicator_engine,
        sample_indicator_config,
        sample_fuzzy_config,
        sample_market_data,
    ):
        """Test fail_fast behavior."""
        # Mock indicator engine to fail
        mock_indicator_instance = Mock()
        mock_indicator_engine.return_value = mock_indicator_instance
        mock_indicator_instance.get_supported_timeframes.return_value = ["1h", "4h"]
        mock_indicator_instance.apply_multi_timeframe.side_effect = Exception(
            "Indicator processing failed"
        )

        # Mock fuzzy engine
        mock_fuzzy_instance = Mock()
        mock_fuzzy_engine.return_value = mock_fuzzy_instance
        mock_fuzzy_instance.get_supported_timeframes.return_value = ["1h", "4h"]
        mock_fuzzy_instance.is_multi_timeframe_enabled.return_value = True

        # Create pipeline
        pipeline = MultiTimeframeFuzzyIndicatorPipeline(
            indicator_config=sample_indicator_config,
            fuzzy_config=sample_fuzzy_config,
            enable_error_recovery=True,
        )

        # Should raise exception with fail_fast=True
        with pytest.raises(ProcessingError) as exc_info:
            pipeline.process_market_data(sample_market_data, fail_fast=True)
        assert "Indicator processing failed" in str(exc_info.value)

    def test_convert_indicators_to_fuzzy_input(
        self, sample_indicator_config, sample_fuzzy_config
    ):
        """Test conversion of indicator results to fuzzy input format."""
        pipeline = MultiTimeframeFuzzyIndicatorPipeline(
            indicator_config=sample_indicator_config, fuzzy_config=sample_fuzzy_config
        )

        # Sample indicator results
        indicator_results = {
            "1h": pd.DataFrame(
                {
                    "RSI_14_1h": [35.0, 45.0, 55.0],
                    "MACD_12_26_1h": [0.1, -0.2, 0.3],
                    "SMA_20_1h": [105.0, 106.0, 107.0],
                }
            ),
            "4h": pd.DataFrame(
                {"RSI_14_4h": [40.0, 50.0], "SMA_20_4h": [105.0, 106.0]}
            ),
        }

        fuzzy_input = pipeline._convert_indicators_to_fuzzy_input(indicator_results)

        # Check structure
        assert "1h" in fuzzy_input
        assert "4h" in fuzzy_input

        # Check 1h data (should use latest values)
        assert fuzzy_input["1h"]["rsi"] == 55.0
        assert fuzzy_input["1h"]["macd"] == 0.3
        assert fuzzy_input["1h"]["sma"] == 107.0

        # Check 4h data
        assert fuzzy_input["4h"]["rsi"] == 50.0
        assert fuzzy_input["4h"]["sma"] == 106.0

    def test_extract_base_indicator_name(
        self, sample_indicator_config, sample_fuzzy_config
    ):
        """Test extraction of base indicator name from standardized column name."""
        pipeline = MultiTimeframeFuzzyIndicatorPipeline(
            indicator_config=sample_indicator_config, fuzzy_config=sample_fuzzy_config
        )

        # Test various column name formats
        assert pipeline._extract_base_indicator_name("RSI_14_1h", "1h") == "rsi"
        assert pipeline._extract_base_indicator_name("MACD_12_26_1h", "1h") == "macd"
        assert pipeline._extract_base_indicator_name("SMA_20_4h", "4h") == "sma"
        assert pipeline._extract_base_indicator_name("close", "1h") == "close"

    def test_timeframe_filtering(self, sample_indicator_config, sample_fuzzy_config):
        """Test timeframe filtering in conversion."""
        pipeline = MultiTimeframeFuzzyIndicatorPipeline(
            indicator_config=sample_indicator_config, fuzzy_config=sample_fuzzy_config
        )

        indicator_results = {
            "1h": pd.DataFrame({"RSI_14_1h": [35.0]}),
            "4h": pd.DataFrame({"RSI_14_4h": [40.0]}),
            "1d": pd.DataFrame({"RSI_14_1d": [45.0]}),
        }

        # Filter to only 1h
        fuzzy_input = pipeline._convert_indicators_to_fuzzy_input(
            indicator_results, timeframe_filter=["1h"]
        )

        assert "1h" in fuzzy_input
        assert "4h" not in fuzzy_input
        assert "1d" not in fuzzy_input

    def test_get_supported_timeframes(
        self, sample_indicator_config, sample_fuzzy_config
    ):
        """Test getting common supported timeframes."""
        pipeline = MultiTimeframeFuzzyIndicatorPipeline(
            indicator_config=sample_indicator_config, fuzzy_config=sample_fuzzy_config
        )

        timeframes = pipeline.get_supported_timeframes()
        assert isinstance(timeframes, list)
        assert len(timeframes) > 0
        # Should have common timeframes between configs

    def test_get_pipeline_health(self, sample_indicator_config, sample_fuzzy_config):
        """Test pipeline health check."""
        pipeline = MultiTimeframeFuzzyIndicatorPipeline(
            indicator_config=sample_indicator_config, fuzzy_config=sample_fuzzy_config
        )

        health = pipeline.get_pipeline_health()

        assert "indicator_engine" in health
        assert "fuzzy_engine" in health
        assert "common_timeframes" in health
        assert "error_recovery_enabled" in health
        assert "performance_monitoring_enabled" in health

        assert health["indicator_engine"]["initialized"] is True
        assert health["fuzzy_engine"]["initialized"] is True
        assert health["error_recovery_enabled"] is True
        assert health["performance_monitoring_enabled"] is True

    def test_factory_function(self, sample_indicator_config, sample_fuzzy_config):
        """Test factory function for creating pipelines."""
        pipeline = create_integrated_pipeline(
            indicator_config=sample_indicator_config,
            fuzzy_config=sample_fuzzy_config,
            enable_error_recovery=False,
            enable_performance_monitoring=False,
        )

        assert isinstance(pipeline, MultiTimeframeFuzzyIndicatorPipeline)
        assert pipeline.enable_error_recovery is False
        assert pipeline.enable_performance_monitoring is False


class TestIntegratedFuzzyResult:
    """Tests for IntegratedFuzzyResult dataclass."""

    def test_result_creation(self):
        """Test creating IntegratedFuzzyResult objects."""
        from ktrdr.fuzzy.multi_timeframe_engine import MultiTimeframeFuzzyResult

        fuzzy_result = MultiTimeframeFuzzyResult(
            fuzzy_values={"rsi_low_1h": 0.8},
            timeframe_results={"1h": {"rsi_low": 0.8}},
            metadata={"processed_timeframes": ["1h"]},
            warnings=[],
            processing_time=0.05,
        )

        result = IntegratedFuzzyResult(
            fuzzy_result=fuzzy_result,
            indicator_data={"1h": {"rsi": 35.0}},
            processing_metadata={"symbol": "AAPL"},
            errors=[],
            warnings=["Minor warning"],
            total_processing_time=0.1,
        )

        assert result.fuzzy_result == fuzzy_result
        assert result.indicator_data == {"1h": {"rsi": 35.0}}
        assert result.processing_metadata == {"symbol": "AAPL"}
        assert result.errors == []
        assert result.warnings == ["Minor warning"]
        assert result.total_processing_time == 0.1
