"""Integration tests for complex multi-indicator configurations."""


import numpy as np
import pandas as pd
import pytest

from ktrdr.indicators.complex_configuration_handler import (
    ComplexConfigurationHandler,
    FallbackStrategy,
    create_robust_configuration,
    validate_configuration_feasibility,
)
from ktrdr.indicators.multi_timeframe_indicator_engine import TimeframeIndicatorConfig


class TestComplexConfigurationHandler:
    """Test complex configuration handling."""

    @pytest.fixture
    def small_data(self):
        """Create small dataset that will cause data insufficiency issues."""
        dates = pd.date_range("2024-01-01", periods=30, freq="1h")  # Only 30 hours
        np.random.seed(42)

        prices = 100 + np.cumsum(np.random.normal(0, 1, 30))

        data_1h = pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices * 0.999,
                "high": prices * 1.001,
                "low": prices * 0.998,
                "close": prices,
                "volume": np.random.randint(1000, 10000, 30),
            }
        )

        # Create smaller 4h data
        data_4h = data_1h.iloc[::4].reset_index(
            drop=True
        )  # Every 4th hour = 7-8 points

        # Even smaller daily data
        data_1d = data_1h.iloc[::24].reset_index(
            drop=True
        )  # Every 24th hour = 1-2 points

        return {"1h": data_1h, "4h": data_4h, "1d": data_1d}

    @pytest.fixture
    def demanding_configuration(self):
        """Create configuration that demands a lot of data."""
        return [
            TimeframeIndicatorConfig(
                timeframe="1h",
                indicators=[
                    {"type": "RSI", "params": {"period": 14}},
                    {
                        "type": "SimpleMovingAverage",
                        "params": {"period": 50},
                    },  # Needs 50 points
                    {
                        "type": "MACD",
                        "params": {
                            "fast_period": 12,
                            "slow_period": 26,
                            "signal_period": 9,
                        },
                    },
                ],
            ),
            TimeframeIndicatorConfig(
                timeframe="4h",
                indicators=[
                    {
                        "type": "SimpleMovingAverage",
                        "params": {"period": 200},
                    },  # Impossible with 7 points
                    {"type": "BollingerBands", "params": {"period": 20}},
                ],
            ),
            TimeframeIndicatorConfig(
                timeframe="1d",
                indicators=[
                    {
                        "type": "StochasticOscillator",
                        "params": {"k_period": 14, "d_period": 3},
                    },
                    {"type": "ATR", "params": {"period": 14}},
                ],
            ),
        ]

    def test_data_availability_analysis(self, small_data):
        """Test analysis of data availability."""
        handler = ComplexConfigurationHandler()

        availability = handler.analyze_data_availability(small_data)

        assert len(availability) == 3
        assert "1h" in availability
        assert "4h" in availability
        assert "1d" in availability

        # Check 1h data
        assert availability["1h"].total_points == 30
        assert availability["1h"].valid_points == 30

        # Check 4h data (smaller)
        assert availability["4h"].total_points > 0
        assert availability["4h"].total_points < 10

        # Check 1d data (very small)
        assert availability["1d"].total_points > 0
        assert availability["1d"].total_points < 5

    def test_configuration_validation_with_insufficient_data(
        self, small_data, demanding_configuration
    ):
        """Test configuration validation when data is insufficient."""
        handler = ComplexConfigurationHandler()

        availability = handler.analyze_data_availability(small_data)
        issues, corrected_configs = handler.validate_configuration(
            demanding_configuration, availability
        )

        # Should find multiple issues
        assert len(issues) > 0

        # Should find issues with indicators needing more data
        issue_types = {issue.indicator_type for issue in issues}
        assert (
            "SimpleMovingAverage" in issue_types
        )  # SMA(200) impossible with small data

        # Should have corrected configurations
        assert len(corrected_configs) == 3

        # Check that corrections were made
        for config in corrected_configs:
            for indicator in config.indicators:
                params = indicator.get("params", {})
                if indicator["type"] == "SimpleMovingAverage":
                    period = params.get("period", 20)
                    # Should be reduced from original large periods
                    if config.timeframe == "4h":
                        assert period < 200  # Much smaller than requested

    def test_fallback_strategy_skip(self, small_data, demanding_configuration):
        """Test SKIP fallback strategy."""
        handler = ComplexConfigurationHandler(FallbackStrategy.SKIP)

        availability = handler.analyze_data_availability(small_data)
        issues, corrected_configs = handler.validate_configuration(
            demanding_configuration, availability
        )

        # Should skip problematic indicators
        for config in corrected_configs:
            if config.timeframe == "4h":
                # Should have fewer indicators (some skipped)
                assert len(config.indicators) <= len(
                    demanding_configuration[1].indicators
                )

    def test_fallback_strategy_reduce_period(self, small_data, demanding_configuration):
        """Test REDUCE_PERIOD fallback strategy."""
        handler = ComplexConfigurationHandler(FallbackStrategy.REDUCE_PERIOD)

        availability = handler.analyze_data_availability(small_data)
        issues, corrected_configs = handler.validate_configuration(
            demanding_configuration, availability
        )

        # Should reduce periods instead of skipping
        for config in corrected_configs:
            for indicator in config.indicators:
                params = indicator.get("params", {})

                if (
                    indicator["type"] == "SimpleMovingAverage"
                    and config.timeframe == "4h"
                ):
                    period = params.get("period", 20)
                    available_points = availability[config.timeframe].valid_points
                    # Period should be reasonable for available data
                    assert period < available_points

    def test_create_robust_configuration(self, small_data, demanding_configuration):
        """Test creating robust configuration that adapts to data."""
        engine, issues = create_robust_configuration(
            demanding_configuration, small_data, FallbackStrategy.REDUCE_PERIOD
        )

        # Should create working engine despite data issues
        assert engine is not None
        assert len(engine.engines) > 0

        # Should report issues found
        assert len(issues) > 0

        # Test that engine can process the data without errors
        try:
            results = engine.apply_multi_timeframe(small_data)
            assert len(results) > 0

            # Results should have proper column naming
            for timeframe, df in results.items():
                indicator_cols = [
                    col
                    for col in df.columns
                    if col
                    not in ["timestamp", "open", "high", "low", "close", "volume"]
                ]
                for col in indicator_cols:
                    assert col.endswith(f"_{timeframe}")

        except Exception as e:
            pytest.fail(f"Robust configuration should not fail: {e}")

    def test_validate_configuration_feasibility(
        self, small_data, demanding_configuration
    ):
        """Test configuration feasibility validation."""
        report = validate_configuration_feasibility(demanding_configuration, small_data)

        # Should report infeasibility
        assert report["feasible"] == False

        # Should have data availability info
        assert "data_availability" in report
        assert "1h" in report["data_availability"]

        # Should have requirements
        assert "requirements" in report
        assert "1h" in report["requirements"]

        # Should have issues
        assert len(report["issues"]) > 0

        # Should have recommendations
        assert len(report["recommendations"]) > 0

    def test_minimum_data_requirements(self, demanding_configuration):
        """Test calculation of minimum data requirements."""
        handler = ComplexConfigurationHandler()

        requirements = handler.suggest_minimum_data_requirements(
            demanding_configuration
        )

        assert len(requirements) == 3
        assert "1h" in requirements
        assert "4h" in requirements
        assert "1d" in requirements

        # 4h should have highest requirement due to SMA(200)
        assert requirements["4h"] >= 200

        # 1h should need significant data for MACD
        assert requirements["1h"] >= 35  # 26 + 9 for MACD

    def test_complex_real_world_scenario(self):
        """Test a complex real-world scenario with mixed data quality."""

        # Create realistic but challenging dataset
        np.random.seed(42)

        # 1h: Good data (3 months)
        dates_1h = pd.date_range("2024-01-01", periods=24 * 90, freq="1h")
        prices_1h = 100 + np.cumsum(np.random.normal(0, 1, len(dates_1h)))
        data_1h = pd.DataFrame(
            {
                "timestamp": dates_1h,
                "open": prices_1h * 0.999,
                "high": prices_1h * 1.001,
                "low": prices_1h * 0.998,
                "close": prices_1h,
                "volume": np.random.randint(1000, 10000, len(dates_1h)),
            }
        )

        # 4h: Medium data (1 month)
        dates_4h = pd.date_range("2024-01-01", periods=24 * 30 // 4, freq="4h")
        prices_4h = 100 + np.cumsum(np.random.normal(0, 1, len(dates_4h)))
        data_4h = pd.DataFrame(
            {
                "timestamp": dates_4h,
                "open": prices_4h * 0.999,
                "high": prices_4h * 1.001,
                "low": prices_4h * 0.998,
                "close": prices_4h,
                "volume": np.random.randint(5000, 50000, len(dates_4h)),
            }
        )

        # 1d: Limited data (2 months - enough for some indicators)
        dates_1d = pd.date_range("2024-01-01", periods=60, freq="1d")
        prices_1d = 100 + np.cumsum(np.random.normal(0, 1, len(dates_1d)))
        data_1d = pd.DataFrame(
            {
                "timestamp": dates_1d,
                "open": prices_1d * 0.999,
                "high": prices_1d * 1.001,
                "low": prices_1d * 0.998,
                "close": prices_1d,
                "volume": np.random.randint(50000, 500000, len(dates_1d)),
            }
        )

        complex_data = {"1h": data_1h, "4h": data_4h, "1d": data_1d}

        # Complex configuration with varying demands
        complex_config = [
            TimeframeIndicatorConfig(
                timeframe="1h",
                indicators=[
                    {"type": "RSI", "params": {"period": 14}},
                    {"type": "SimpleMovingAverage", "params": {"period": 20}},
                    {"type": "SimpleMovingAverage", "params": {"period": 50}},
                    {
                        "type": "MACD",
                        "params": {
                            "fast_period": 12,
                            "slow_period": 26,
                            "signal_period": 9,
                        },
                    },
                    {"type": "BollingerBands", "params": {"period": 20, "std_dev": 2}},
                ],
            ),
            TimeframeIndicatorConfig(
                timeframe="4h",
                indicators=[
                    {"type": "RSI", "params": {"period": 14}},
                    {
                        "type": "SimpleMovingAverage",
                        "params": {"period": 100},
                    },  # May need reduction
                    {"type": "ExponentialMovingAverage", "params": {"period": 21}},
                ],
            ),
            TimeframeIndicatorConfig(
                timeframe="1d",
                indicators=[
                    {
                        "type": "SimpleMovingAverage",
                        "params": {"period": 50},
                    },  # Will need reduction
                    {"type": "ATR", "params": {"period": 14}},  # Will need reduction
                ],
            ),
        ]

        # Test with different fallback strategies
        for strategy in [FallbackStrategy.REDUCE_PERIOD, FallbackStrategy.SKIP]:
            engine, issues = create_robust_configuration(
                complex_config, complex_data, strategy
            )

            # Should create working engine
            assert engine is not None

            # Should be able to process data
            results = engine.apply_multi_timeframe(complex_data)
            assert len(results) >= 2  # At least 1h and 4h should work

            # 1h should work well (good data)
            assert "1h" in results
            assert len(results["1h"]) > 0

            # Check that results make sense
            for timeframe, df in results.items():
                assert not df.empty
                assert "close" in df.columns  # Original data preserved

                # Should have some indicator columns
                indicator_cols = [
                    col
                    for col in df.columns
                    if col
                    not in ["timestamp", "open", "high", "low", "close", "volume"]
                ]
                assert len(indicator_cols) > 0

    def test_edge_cases(self):
        """Test edge cases in configuration handling."""
        handler = ComplexConfigurationHandler()

        # Test with empty data
        empty_data = {"1h": pd.DataFrame(), "4h": pd.DataFrame(), "1d": pd.DataFrame()}

        availability = handler.analyze_data_availability(empty_data)

        for tf, avail in availability.items():
            assert avail.total_points == 0
            assert avail.valid_points == 0

        # Test with data containing NaN values
        dates = pd.date_range("2024-01-01", periods=50, freq="1h")
        data_with_nans = pd.DataFrame(
            {
                "timestamp": dates,
                "open": [100] * 50,
                "high": [101] * 50,
                "low": [99] * 50,
                "close": [100] * 25 + [np.nan] * 25,  # Half NaN
                "volume": [1000] * 50,
            }
        )

        nan_data = {"1h": data_with_nans}
        availability = handler.analyze_data_availability(nan_data)

        assert availability["1h"].total_points == 50
        assert availability["1h"].valid_points == 25  # Only non-NaN close values

        # Test configuration that should work with reduced data
        simple_config = [
            TimeframeIndicatorConfig(
                timeframe="1h",
                indicators=[
                    {
                        "type": "SimpleMovingAverage",
                        "params": {"period": 40},
                    }  # Needs reduction
                ],
            )
        ]

        issues, corrected = handler.validate_configuration(simple_config, availability)

        # Should suggest reduction since we only have 25 valid points
        assert len(issues) > 0
        assert len(corrected) == 1
        assert len(corrected[0].indicators) == 1

        # Period should be reduced
        corrected_period = corrected[0].indicators[0]["params"]["period"]
        assert corrected_period < 40

    def test_unknown_indicators(self):
        """Test handling of unknown indicator types."""
        handler = ComplexConfigurationHandler()

        # Configuration with unknown indicator
        unknown_config = [
            TimeframeIndicatorConfig(
                timeframe="1h",
                indicators=[
                    {"type": "UnknownIndicator", "params": {"some_param": 123}},
                    {"type": "RSI", "params": {"period": 14}},  # Known indicator
                ],
            )
        ]

        # Good data
        dates = pd.date_range("2024-01-01", periods=100, freq="1h")
        good_data = {
            "1h": pd.DataFrame(
                {
                    "timestamp": dates,
                    "open": [100] * 100,
                    "high": [101] * 100,
                    "low": [99] * 100,
                    "close": [100] * 100,
                    "volume": [1000] * 100,
                }
            )
        }

        availability = handler.analyze_data_availability(good_data)
        issues, corrected = handler.validate_configuration(unknown_config, availability)

        # Should handle unknown indicator gracefully
        assert len(corrected) == 1
        assert len(corrected[0].indicators) == 2  # Both indicators preserved

        # Known indicator should pass validation without issues
        rsi_indicator = next(
            ind for ind in corrected[0].indicators if ind["type"] == "RSI"
        )
        assert rsi_indicator["params"]["period"] == 14  # Unchanged
