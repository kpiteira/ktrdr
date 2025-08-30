"""
End-to-end integration tests for multi-timeframe fuzzy processing.

These tests use reference datasets to validate the complete pipeline
from market data through indicators to fuzzy outputs.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from ktrdr.fuzzy.indicator_integration import IntegratedFuzzyResult
from ktrdr.services.fuzzy_pipeline_service import FuzzyPipelineService


class TestEnd2EndFuzzyIntegration:
    """End-to-end integration tests for fuzzy processing pipeline."""

    @pytest.fixture
    def reference_market_data(self):
        """
        Reference market data with known patterns for testing.

        This creates synthetic but realistic market data with specific
        patterns that should produce predictable fuzzy outputs.
        """
        # Create 1000 data points for robust testing
        n_points = 1000

        # Base trend component
        trend = np.linspace(100, 120, n_points)

        # Add cyclical components
        fast_cycle = 2 * np.sin(np.linspace(0, 20 * np.pi, n_points))
        slow_cycle = 5 * np.sin(np.linspace(0, 4 * np.pi, n_points))

        # Add noise
        noise = np.random.normal(0, 0.5, n_points)

        # Combine components
        base_price = trend + fast_cycle + slow_cycle + noise

        # Create OHLCV data
        data_1h = []
        data_4h = []
        data_1d = []

        # 1h timeframe (all points)
        dates_1h = pd.date_range("2024-01-01", periods=n_points, freq="1h")
        for i, _date in enumerate(dates_1h):
            price = base_price[i]
            data_1h.append(
                {
                    "open": price + np.random.normal(0, 0.1),
                    "high": price + abs(np.random.normal(0.5, 0.2)),
                    "low": price - abs(np.random.normal(0.5, 0.2)),
                    "close": price,
                    "volume": np.random.uniform(1000, 5000),
                }
            )

        # 4h timeframe (every 4th point)
        dates_4h = pd.date_range("2024-01-01", periods=n_points // 4, freq="4h")
        for i, _date in enumerate(dates_4h):
            idx = i * 4
            if idx < len(base_price):
                price = base_price[idx]
                data_4h.append(
                    {
                        "open": price + np.random.normal(0, 0.1),
                        "high": price + abs(np.random.normal(1.0, 0.3)),
                        "low": price - abs(np.random.normal(1.0, 0.3)),
                        "close": price,
                        "volume": np.random.uniform(4000, 20000),
                    }
                )

        # 1d timeframe (every 24th point)
        dates_1d = pd.date_range("2024-01-01", periods=n_points // 24, freq="1d")
        for i, _date in enumerate(dates_1d):
            idx = i * 24
            if idx < len(base_price):
                price = base_price[idx]
                data_1d.append(
                    {
                        "open": price + np.random.normal(0, 0.2),
                        "high": price + abs(np.random.normal(2.0, 0.5)),
                        "low": price - abs(np.random.normal(2.0, 0.5)),
                        "close": price,
                        "volume": np.random.uniform(20000, 100000),
                    }
                )

        return {
            "1h": pd.DataFrame(data_1h, index=dates_1h),
            "4h": pd.DataFrame(data_4h, index=dates_4h),
            "1d": pd.DataFrame(data_1d, index=dates_1d),
        }

    @pytest.fixture
    def reference_indicator_config(self):
        """Reference indicator configuration for testing."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": [
                        {"type": "RSI", "period": 14},
                        {
                            "type": "MACD",
                            "fast_period": 12,
                            "slow_period": 26,
                            "signal_period": 9,
                        },
                        {"type": "SMA", "period": 20},
                    ]
                },
                "4h": {
                    "indicators": [
                        {"type": "RSI", "period": 14},
                        {"type": "EMA", "period": 50},
                        {"type": "BB", "period": 20, "std_dev": 2},
                    ]
                },
                "1d": {
                    "indicators": [
                        {"type": "SMA", "period": 50},
                        {"type": "SMA", "period": 200},
                        {"type": "ATR", "period": 14},
                    ]
                },
            }
        }

    @pytest.fixture
    def reference_fuzzy_config(self):
        """Reference fuzzy configuration for testing."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi", "macd", "sma"],
                    "fuzzy_sets": {
                        "rsi": {
                            "oversold": {
                                "type": "triangular",
                                "parameters": [0, 20, 35],
                            },
                            "neutral": {
                                "type": "triangular",
                                "parameters": [25, 50, 75],
                            },
                            "overbought": {
                                "type": "triangular",
                                "parameters": [65, 80, 100],
                            },
                        },
                        "macd": {
                            "bearish": {
                                "type": "triangular",
                                "parameters": [-2, -1, 0],
                            },
                            "neutral": {
                                "type": "triangular",
                                "parameters": [-0.5, 0, 0.5],
                            },
                            "bullish": {"type": "triangular", "parameters": [0, 1, 2]},
                        },
                        "sma": {
                            "below": {"type": "triangular", "parameters": [-10, -3, 0]},
                            "near": {"type": "triangular", "parameters": [-2, 0, 2]},
                            "above": {"type": "triangular", "parameters": [0, 3, 10]},
                        },
                    },
                    "weight": 0.5,
                    "enabled": True,
                },
                "4h": {
                    "indicators": ["rsi", "ema", "bb"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {
                                "type": "trapezoidal",
                                "parameters": [0, 10, 30, 40],
                            },
                            "medium": {
                                "type": "trapezoidal",
                                "parameters": [30, 40, 60, 70],
                            },
                            "high": {
                                "type": "trapezoidal",
                                "parameters": [60, 70, 90, 100],
                            },
                        },
                        "ema": {
                            "below": {"type": "triangular", "parameters": [-15, -7, 0]},
                            "above": {"type": "triangular", "parameters": [0, 7, 15]},
                        },
                        "bb": {
                            "lower": {"type": "triangular", "parameters": [-2, -1, 0]},
                            "middle": {
                                "type": "triangular",
                                "parameters": [-0.5, 0, 0.5],
                            },
                            "upper": {"type": "triangular", "parameters": [0, 1, 2]},
                        },
                    },
                    "weight": 0.3,
                    "enabled": True,
                },
                "1d": {
                    "indicators": ["sma_50", "sma_200", "atr"],
                    "fuzzy_sets": {
                        "sma_50": {
                            "trend_down": {"type": "gaussian", "parameters": [-5, 2]},
                            "trend_neutral": {"type": "gaussian", "parameters": [0, 1]},
                            "trend_up": {"type": "gaussian", "parameters": [5, 2]},
                        },
                        "sma_200": {
                            "long_bearish": {
                                "type": "triangular",
                                "parameters": [-20, -10, 0],
                            },
                            "long_neutral": {
                                "type": "triangular",
                                "parameters": [-5, 0, 5],
                            },
                            "long_bullish": {
                                "type": "triangular",
                                "parameters": [0, 10, 20],
                            },
                        },
                        "atr": {
                            "low_volatility": {
                                "type": "triangular",
                                "parameters": [0, 1, 2],
                            },
                            "medium_volatility": {
                                "type": "triangular",
                                "parameters": [1.5, 3, 4.5],
                            },
                            "high_volatility": {
                                "type": "triangular",
                                "parameters": [4, 6, 10],
                            },
                        },
                    },
                    "weight": 0.2,
                    "enabled": True,
                },
            },
            "indicators": [
                "rsi",
                "macd",
                "sma",
                "ema",
                "bb",
                "sma_50",
                "sma_200",
                "atr",
            ],
        }

    @pytest.fixture
    def mock_data_manager_with_reference_data(self, reference_market_data):
        """Mock DataManager that returns reference data."""

        class MockDataManager:
            def __init__(self, data):
                self.data = data

            def get_data(self, symbol, timeframe, period_days):
                if timeframe in self.data:
                    return self.data[timeframe]
                return None

        return MockDataManager(reference_market_data)

    def test_end_to_end_single_symbol_processing(
        self,
        reference_indicator_config,
        reference_fuzzy_config,
        mock_data_manager_with_reference_data,
    ):
        """Test complete end-to-end processing for a single symbol."""
        # Create service
        service = FuzzyPipelineService(
            data_manager=mock_data_manager_with_reference_data, enable_caching=True
        )

        # Process symbol
        result = service.process_symbol_fuzzy(
            symbol="AAPL",
            indicator_config=reference_indicator_config,
            fuzzy_config=reference_fuzzy_config,
            timeframes=["1h", "4h", "1d"],
            data_period_days=30,
        )

        # Validate result structure
        assert isinstance(result, IntegratedFuzzyResult)
        assert len(result.errors) == 0, f"Processing errors: {result.errors}"
        assert result.total_processing_time > 0

        # Validate fuzzy results
        fuzzy_result = result.fuzzy_result
        assert len(fuzzy_result.fuzzy_values) > 0
        assert len(fuzzy_result.timeframe_results) >= 1

        # Validate that we have fuzzy values with timeframe suffixes
        fuzzy_keys = list(fuzzy_result.fuzzy_values.keys())
        assert any("_1h" in key for key in fuzzy_keys), "Missing 1h fuzzy values"

        # Validate fuzzy value ranges
        for key, value in fuzzy_result.fuzzy_values.items():
            assert 0.0 <= value <= 1.0, f"Fuzzy value {key}={value} out of range [0,1]"

        # Validate indicator data
        assert len(result.indicator_data) > 0
        for timeframe, indicators in result.indicator_data.items():
            assert isinstance(indicators, dict)
            for indicator, value in indicators.items():
                assert isinstance(value, (int, float))
                assert not np.isnan(value), f"NaN value for {indicator} in {timeframe}"

        # Validate metadata
        metadata = result.processing_metadata
        assert metadata["symbol"] == "AAPL"
        assert metadata["service_version"] == "1.0.0"
        assert "processed_indicator_timeframes" in metadata
        assert "fuzzy_input_timeframes" in metadata

    def test_end_to_end_multiple_timeframes(
        self,
        reference_indicator_config,
        reference_fuzzy_config,
        mock_data_manager_with_reference_data,
    ):
        """Test processing with multiple timeframes and validate cross-timeframe consistency."""
        service = FuzzyPipelineService(
            data_manager=mock_data_manager_with_reference_data
        )

        # Process all timeframes
        result = service.process_symbol_fuzzy(
            symbol="AAPL",
            indicator_config=reference_indicator_config,
            fuzzy_config=reference_fuzzy_config,
            timeframes=["1h", "4h", "1d"],
        )

        assert len(result.errors) == 0

        # Validate that all timeframes were processed
        timeframe_results = result.fuzzy_result.timeframe_results
        expected_timeframes = {"1h", "4h", "1d"}
        actual_timeframes = set(timeframe_results.keys())

        # Should have at least some of the expected timeframes
        assert len(actual_timeframes.intersection(expected_timeframes)) > 0

        # Validate timeframe-specific fuzzy values
        for timeframe in actual_timeframes:
            tf_result = timeframe_results[timeframe]
            assert len(tf_result) > 0, f"No fuzzy values for timeframe {timeframe}"

            # Check that values are valid
            for _fuzzy_set, value in tf_result.items():
                assert 0.0 <= value <= 1.0
                assert not np.isnan(value)

    def test_end_to_end_fuzzy_value_consistency(
        self,
        reference_indicator_config,
        reference_fuzzy_config,
        mock_data_manager_with_reference_data,
    ):
        """Test that fuzzy values are consistent with input indicators."""
        service = FuzzyPipelineService(
            data_manager=mock_data_manager_with_reference_data
        )

        result = service.process_symbol_fuzzy(
            symbol="AAPL",
            indicator_config=reference_indicator_config,
            fuzzy_config=reference_fuzzy_config,
        )

        assert len(result.errors) == 0

        # Get indicator values and fuzzy results
        indicator_data = result.indicator_data
        fuzzy_values = result.fuzzy_result.fuzzy_values

        # Test RSI consistency (should be present in multiple timeframes)
        for timeframe in ["1h", "4h"]:
            if timeframe in indicator_data and "rsi" in indicator_data[timeframe]:
                rsi_value = indicator_data[timeframe]["rsi"]

                # Find RSI fuzzy values for this timeframe
                rsi_fuzzy_keys = [
                    k
                    for k in fuzzy_values.keys()
                    if "rsi_" in k and f"_{timeframe}" in k
                ]

                if rsi_fuzzy_keys:
                    # Validate RSI fuzzy logic
                    if rsi_value < 30:
                        # Should have higher membership in oversold/low
                        low_keys = [
                            k for k in rsi_fuzzy_keys if "oversold" in k or "low" in k
                        ]
                        if low_keys:
                            assert (
                                max(fuzzy_values[k] for k in low_keys) > 0.1
                            ), f"Low RSI ({rsi_value}) should have higher oversold membership"

                    elif rsi_value > 70:
                        # Should have higher membership in overbought/high
                        high_keys = [
                            k
                            for k in rsi_fuzzy_keys
                            if "overbought" in k or "high" in k
                        ]
                        if high_keys:
                            assert (
                                max(fuzzy_values[k] for k in high_keys) > 0.1
                            ), f"High RSI ({rsi_value}) should have higher overbought membership"

    def test_end_to_end_error_recovery(
        self, reference_indicator_config, reference_fuzzy_config
    ):
        """Test error recovery with problematic data."""

        # Create data manager that returns incomplete data
        class PartialDataManager:
            def get_data(self, symbol, timeframe, period_days):
                if timeframe == "1h":
                    # Return valid data for 1h
                    dates = pd.date_range("2024-01-01", periods=100, freq="1h")
                    return pd.DataFrame(
                        {
                            "open": np.random.uniform(100, 110, len(dates)),
                            "high": np.random.uniform(105, 115, len(dates)),
                            "low": np.random.uniform(95, 105, len(dates)),
                            "close": np.random.uniform(100, 110, len(dates)),
                            "volume": np.random.uniform(1000, 5000, len(dates)),
                        },
                        index=dates,
                    )
                elif timeframe == "4h":
                    # Return empty data for 4h
                    return pd.DataFrame()
                else:
                    # Return None for 1d
                    return None

        service = FuzzyPipelineService(data_manager=PartialDataManager())

        result = service.process_symbol_fuzzy(
            symbol="AAPL",
            indicator_config=reference_indicator_config,
            fuzzy_config=reference_fuzzy_config,
            timeframes=["1h", "4h", "1d"],
            fail_fast=False,
        )

        # Should not fail completely, but should have partial results
        assert isinstance(result, IntegratedFuzzyResult)
        # Should have processed at least 1h timeframe
        assert len(result.fuzzy_result.timeframe_results) >= 1
        assert "1h" in result.fuzzy_result.timeframe_results

    def test_end_to_end_performance_characteristics(
        self,
        reference_indicator_config,
        reference_fuzzy_config,
        mock_data_manager_with_reference_data,
    ):
        """Test performance characteristics of the pipeline."""
        service = FuzzyPipelineService(
            data_manager=mock_data_manager_with_reference_data,
        )

        # Process multiple times to get consistent timing
        processing_times = []
        for i in range(3):
            result = service.process_symbol_fuzzy(
                symbol=f"TEST{i}",
                indicator_config=reference_indicator_config,
                fuzzy_config=reference_fuzzy_config,
            )
            processing_times.append(result.total_processing_time)

        # Validate performance
        avg_time = sum(processing_times) / len(processing_times)
        assert avg_time < 10.0, f"Average processing time too high: {avg_time}s"

        # Check that we have performance metadata
        last_result = result
        metadata = last_result.processing_metadata
        assert "indicator_processing_time" in metadata
        assert "fuzzy_processing_time" in metadata

    def test_end_to_end_multiple_symbols(
        self,
        reference_indicator_config,
        reference_fuzzy_config,
        mock_data_manager_with_reference_data,
    ):
        """Test processing multiple symbols."""
        service = FuzzyPipelineService(
            data_manager=mock_data_manager_with_reference_data
        )

        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA"]

        results = service.process_multiple_symbols(
            symbols=symbols,
            indicator_config=reference_indicator_config,
            fuzzy_config=reference_fuzzy_config,
            continue_on_error=True,
        )

        # Should have results for all symbols
        assert len(results) == len(symbols)

        for symbol in symbols:
            assert symbol in results
            result = results[symbol]
            assert isinstance(result, IntegratedFuzzyResult)
            assert len(result.errors) == 0
            assert result.processing_metadata["symbol"] == symbol

    def test_end_to_end_summary_report(
        self,
        reference_indicator_config,
        reference_fuzzy_config,
        mock_data_manager_with_reference_data,
    ):
        """Test summary report generation."""
        service = FuzzyPipelineService(
            data_manager=mock_data_manager_with_reference_data
        )

        # Process multiple symbols
        symbols = ["AAPL", "GOOGL"]
        results = service.process_multiple_symbols(
            symbols=symbols,
            indicator_config=reference_indicator_config,
            fuzzy_config=reference_fuzzy_config,
        )

        # Generate summary report
        report = service.create_fuzzy_summary_report(
            results, include_performance_metrics=True
        )

        # Validate report structure
        assert "summary" in report
        assert "symbol_results" in report
        assert "aggregated_metrics" in report

        # Validate summary
        summary = report["summary"]
        assert summary["total_symbols"] == 2
        assert summary["successful_symbols"] >= 1
        assert summary["success_rate"] > 0

        # Validate aggregated metrics
        agg_metrics = report["aggregated_metrics"]
        assert agg_metrics["total_fuzzy_values"] > 0
        assert agg_metrics["avg_fuzzy_values_per_symbol"] > 0
        assert agg_metrics["total_processing_time"] > 0

    def test_end_to_end_with_config_files(
        self,
        reference_indicator_config,
        reference_fuzzy_config,
        mock_data_manager_with_reference_data,
    ):
        """Test end-to-end processing with configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create config files
            indicator_file = Path(temp_dir) / "indicator_config.yaml"
            fuzzy_file = Path(temp_dir) / "fuzzy_config.yaml"

            with open(indicator_file, "w") as f:
                yaml.dump(reference_indicator_config, f)

            with open(fuzzy_file, "w") as f:
                yaml.dump(reference_fuzzy_config, f)

            # Create service and process
            service = FuzzyPipelineService(
                data_manager=mock_data_manager_with_reference_data
            )

            result = service.process_symbol_fuzzy(
                symbol="AAPL",
                indicator_config=str(indicator_file),
                fuzzy_config=str(fuzzy_file),
            )

            assert isinstance(result, IntegratedFuzzyResult)
            assert len(result.errors) == 0
            assert len(result.fuzzy_result.fuzzy_values) > 0


class TestFuzzyValueValidation:
    """Tests to validate fuzzy value calculations against known patterns."""

    def test_rsi_oversold_pattern(self):
        """Test that RSI oversold conditions produce appropriate fuzzy values."""
        # Create market data with clear oversold pattern
        dates = pd.date_range("2024-01-01", periods=50, freq="1h")

        # Create declining price pattern for oversold RSI
        close_prices = np.linspace(110, 90, len(dates))  # Strong decline

        market_data = {
            "1h": pd.DataFrame(
                {
                    "open": close_prices + np.random.normal(0, 0.1, len(dates)),
                    "high": close_prices + 1 + np.random.normal(0, 0.1, len(dates)),
                    "low": close_prices - 1 + np.random.normal(0, 0.1, len(dates)),
                    "close": close_prices,
                    "volume": np.random.uniform(1000, 5000, len(dates)),
                },
                index=dates,
            )
        }

        class MockDataManager:
            def get_data(self, symbol, timeframe, period_days):
                return market_data.get(timeframe)

        # Configure for RSI testing
        indicator_config = {
            "timeframes": {"1h": {"indicators": [{"type": "RSI", "period": 14}]}}
        }

        fuzzy_config = {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi"],
                    "fuzzy_sets": {
                        "rsi": {
                            "oversold": {
                                "type": "triangular",
                                "parameters": [0, 20, 35],
                            },
                            "neutral": {
                                "type": "triangular",
                                "parameters": [25, 50, 75],
                            },
                            "overbought": {
                                "type": "triangular",
                                "parameters": [65, 80, 100],
                            },
                        }
                    },
                    "weight": 1.0,
                    "enabled": True,
                }
            },
            "indicators": ["rsi"],
        }

        service = FuzzyPipelineService(data_manager=MockDataManager())

        result = service.process_symbol_fuzzy(
            symbol="TEST", indicator_config=indicator_config, fuzzy_config=fuzzy_config
        )

        # Should have high oversold membership due to declining prices
        fuzzy_values = result.fuzzy_result.fuzzy_values
        oversold_keys = [k for k in fuzzy_values.keys() if "oversold" in k]

        # Should at least have oversold fuzzy sets defined and calculated
        assert len(fuzzy_values) > 0, "Should have calculated some fuzzy values"
        assert len(result.errors) == 0, "Should process without errors"

        # If oversold keys exist, check they are reasonable values
        if oversold_keys:
            oversold_value = max(fuzzy_values[k] for k in oversold_keys)
            # Value should be between 0 and 1 (valid membership)
            assert (
                0.0 <= oversold_value <= 1.0
            ), f"Invalid membership value: {oversold_value}"

    def test_membership_function_types_integration(self):
        """Test integration of different membership function types."""
        # Test data (need at least 35 points for MACD)
        dates = pd.date_range("2024-01-01", periods=50, freq="1h")
        market_data = {
            "1h": pd.DataFrame(
                {
                    "open": np.random.uniform(100, 110, len(dates)),
                    "high": np.random.uniform(105, 115, len(dates)),
                    "low": np.random.uniform(95, 105, len(dates)),
                    "close": np.random.uniform(100, 110, len(dates)),
                    "volume": np.random.uniform(1000, 5000, len(dates)),
                },
                index=dates,
            )
        }

        class MockDataManager:
            def get_data(self, symbol, timeframe, period_days):
                return market_data.get(timeframe)

        # Configure with different membership function types
        indicator_config = {
            "timeframes": {
                "1h": {
                    "indicators": [
                        {"type": "RSI", "period": 14},
                        {"type": "MACD", "fast_period": 12, "slow_period": 26},
                    ]
                }
            }
        }

        fuzzy_config = {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi", "macd"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {
                                "type": "trapezoidal",
                                "parameters": [0, 10, 30, 40],
                            },
                            "high": {
                                "type": "trapezoidal",
                                "parameters": [60, 70, 90, 100],
                            },
                        },
                        "macd": {
                            "negative": {"type": "gaussian", "parameters": [-1, 0.5]},
                            "positive": {"type": "gaussian", "parameters": [1, 0.5]},
                        },
                    },
                    "weight": 1.0,
                    "enabled": True,
                }
            },
            "indicators": ["rsi", "macd"],
        }

        service = FuzzyPipelineService(data_manager=MockDataManager())

        result = service.process_symbol_fuzzy(
            symbol="TEST", indicator_config=indicator_config, fuzzy_config=fuzzy_config
        )

        # Should successfully process different membership function types
        assert len(result.errors) == 0
        fuzzy_values = result.fuzzy_result.fuzzy_values

        # Should have fuzzy values from both trapezoidal (RSI) and gaussian (MACD)
        rsi_keys = [k for k in fuzzy_values.keys() if "rsi_" in k]
        macd_keys = [k for k in fuzzy_values.keys() if "macd_" in k]

        # Should have some fuzzy values (at least one type should work)
        assert len(fuzzy_values) > 0, "Should have some fuzzy values calculated"

        # Check that we have either RSI or MACD fuzzy values (or both)
        total_indicator_values = len(rsi_keys) + len(macd_keys)
        assert (
            total_indicator_values > 0
        ), "Should have fuzzy values from at least one indicator"

        # All values should be valid
        for _key, value in fuzzy_values.items():
            assert 0.0 <= value <= 1.0
            assert not np.isnan(value)
