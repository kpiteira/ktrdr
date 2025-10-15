"""
Comprehensive validation tests for all indicators against reference values.

This module provides systematic testing of all implemented indicators against
known reference values to ensure accuracy and consistency.
"""

import logging

import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.indicators import ExponentialMovingAverage, RSIIndicator, SimpleMovingAverage
from tests.indicators.reference_datasets import (
    REFERENCE_VALUES,
    TOLERANCES,
    create_reference_dataset_1,
    create_reference_dataset_2,
    create_reference_dataset_3,
    create_reference_dataset_4,
)
from tests.indicators.validation_utils import (
    generate_indicator_report,
    validate_indicator_against_reference,
)

# Setup logger
logger = logging.getLogger(__name__)


class TestSMAValidation:
    """Tests for validating Simple Moving Average against reference values."""

    def test_sma5_against_reference(self):
        """Test SMA(5) against reference values."""
        # Create indicator and dataset
        sma = SimpleMovingAverage(period=5)
        data = create_reference_dataset_1()

        # Get reference values
        reference = REFERENCE_VALUES["SMA"]["dataset_1"]["SMA_5"]
        tolerance = TOLERANCES["SMA"]

        # Run validation
        result = validate_indicator_against_reference(
            sma, data, reference, tolerance=tolerance, relative=True
        )

        # Log detailed results
        logger.info(str(result))
        if not result.passed:
            logger.warning(result.get_failure_details())

        # Assert all points pass validation
        assert (
            result.passed
        ), f"SMA(5) failed validation with {result.failed_points} points"

    def test_sma10_against_reference(self):
        """Test SMA(10) against reference values."""
        # Create indicator and dataset
        sma = SimpleMovingAverage(period=10)
        data = create_reference_dataset_1()

        # Get reference values
        reference = REFERENCE_VALUES["SMA"]["dataset_1"]["SMA_10"]
        tolerance = TOLERANCES["SMA"]

        # Run validation
        result = validate_indicator_against_reference(
            sma, data, reference, tolerance=tolerance, relative=True
        )

        # Log detailed results
        logger.info(str(result))
        if not result.passed:
            logger.warning(result.get_failure_details())

        # Assert all points pass validation
        assert (
            result.passed
        ), f"SMA(10) failed validation with {result.failed_points} points"

    def test_sma20_against_reference(self):
        """Test SMA(20) against reference values."""
        # Create indicator and dataset
        sma = SimpleMovingAverage(period=20)
        data = create_reference_dataset_1()

        # Get reference values
        reference = REFERENCE_VALUES["SMA"]["dataset_1"]["SMA_20"]
        tolerance = TOLERANCES["SMA"]

        # Run validation
        result = validate_indicator_against_reference(
            sma, data, reference, tolerance=tolerance, relative=True
        )

        # Log detailed results
        logger.info(str(result))
        if not result.passed:
            logger.warning(result.get_failure_details())

        # Assert all points pass validation
        assert (
            result.passed
        ), f"SMA(20) failed validation with {result.failed_points} points"

    def test_sma_various_parameters(self):
        """Test SMA with various parameters to ensure consistent behavior."""
        # Test data
        data = create_reference_dataset_2()

        # Test different periods
        for period in [5, 10, 20, 50]:
            sma = SimpleMovingAverage(period=period)
            result = sma.compute(data)

            # Basic validation
            assert isinstance(result, pd.Series)
            assert len(result) == len(data)
            assert pd.isna(result.iloc[0])
            assert not pd.isna(result.iloc[period])

            # The indicator should smooth the data
            if period > 1:
                # Volatility (standard deviation) should be lower than the original data
                original_std = data["close"].std()
                result_std = result.dropna().std()
                assert (
                    result_std <= original_std * 1.05
                ), f"SMA({period}) should reduce volatility"

            # Log report
            report = generate_indicator_report(
                sma, data, key_points=[period, period * 2, -1]
            )
            logger.info(f"SMA({period}) report: {report}")


class TestEMAValidation:
    """Tests for validating Exponential Moving Average against reference values."""

    def test_ema5_against_reference(self):
        """Test EMA(5) against reference values."""
        # Create indicator and dataset
        ema = ExponentialMovingAverage(period=5)
        data = create_reference_dataset_1()

        # Get reference values
        reference = REFERENCE_VALUES["EMA"]["dataset_1"]["EMA_5"]
        tolerance = TOLERANCES["EMA"]

        # Run validation
        result = validate_indicator_against_reference(
            ema, data, reference, tolerance=tolerance, relative=True
        )

        # Log detailed results
        logger.info(str(result))
        if not result.passed:
            logger.warning(result.get_failure_details())

        # Assert all points pass validation
        assert (
            result.passed
        ), f"EMA(5) failed validation with {result.failed_points} points"

    def test_ema10_against_reference(self):
        """Test EMA(10) against reference values."""
        # Create indicator and dataset
        ema = ExponentialMovingAverage(period=10)
        data = create_reference_dataset_1()

        # Get reference values
        reference = REFERENCE_VALUES["EMA"]["dataset_1"]["EMA_10"]
        tolerance = TOLERANCES["EMA"]

        # Run validation
        result = validate_indicator_against_reference(
            ema, data, reference, tolerance=tolerance, relative=True
        )

        # Log detailed results
        logger.info(str(result))
        if not result.passed:
            logger.warning(result.get_failure_details())

        # Assert all points pass validation
        assert (
            result.passed
        ), f"EMA(10) failed validation with {result.failed_points} points"

    def test_ema_react_faster_than_sma(self):
        """Test that EMA reacts faster to price changes than SMA."""
        # Create dataset with a sudden price change
        data = create_reference_dataset_4()

        # We'll only test with period 5 and 10 since period 20 might have NaN values
        for period in [5, 10]:
            ema = ExponentialMovingAverage(period=period)
            sma = SimpleMovingAverage(period=period)

            ema_result = ema.compute(data)
            sma_result = sma.compute(data)

            # Find first index after the first pattern change (at index 10)
            # That is also beyond the warmup period
            idx = period + 5

            # If there's a price drop, EMA should be lower than SMA
            if data["close"].iloc[idx] < data["close"].iloc[idx - 5]:
                assert (
                    ema_result.iloc[idx] < sma_result.iloc[idx]
                ), f"EMA({period}) should react faster to price drops than SMA({period})"
            # If there's a price rise, EMA should be higher than SMA
            elif data["close"].iloc[idx] > data["close"].iloc[idx - 5]:
                assert (
                    ema_result.iloc[idx] > sma_result.iloc[idx]
                ), f"EMA({period}) should react faster to price increases than SMA({period})"

    def test_ema_adjusted_vs_non_adjusted(self):
        """Test differences between adjusted and non-adjusted EMA."""
        data = create_reference_dataset_2()

        # Calculate both adjusted and non-adjusted EMAs
        ema_adjusted = ExponentialMovingAverage(period=5, adjust=True)
        ema_non_adjusted = ExponentialMovingAverage(period=5, adjust=False)

        result_adj = ema_adjusted.compute(data)
        result_non_adj = ema_non_adjusted.compute(data)

        # The values should be different but converge over time
        assert not result_adj.equals(result_non_adj)

        # The difference should decrease over time
        first_diff = abs(result_adj.iloc[10] - result_non_adj.iloc[10])
        last_diff = abs(result_adj.iloc[-1] - result_non_adj.iloc[-1])
        assert (
            last_diff < first_diff
        ), "Adjusted and non-adjusted EMA should converge over time"


class TestRSIValidation:
    """Tests for validating RSI indicator against reference values."""

    def test_rsi14_against_reference(self):
        """Test RSI(14) against reference values."""
        # Create indicator and dataset
        rsi = RSIIndicator(period=14)
        data = create_reference_dataset_3()

        # Get reference values
        reference = REFERENCE_VALUES["RSI"]["dataset_3"]["RSI_14"]
        tolerance = TOLERANCES["RSI"]

        # Run validation
        result = validate_indicator_against_reference(
            rsi, data, reference, tolerance=tolerance, relative=True
        )

        # Log detailed results
        logger.info(str(result))
        if not result.passed:
            logger.warning(result.get_failure_details())

        # Assert all points pass validation
        assert (
            result.passed
        ), f"RSI(14) failed validation with {result.failed_points} points"

    def test_rsi7_against_reference(self):
        """Test RSI(7) against reference values."""
        # Create indicator and dataset
        rsi = RSIIndicator(period=7)
        data = create_reference_dataset_3()

        # Get reference values
        reference = REFERENCE_VALUES["RSI"]["dataset_3"]["RSI_7"]
        tolerance = TOLERANCES["RSI"]

        # Run validation
        result = validate_indicator_against_reference(
            rsi, data, reference, tolerance=tolerance, relative=True
        )

        # Log detailed results
        logger.info(str(result))
        if not result.passed:
            logger.warning(result.get_failure_details())

        # Assert all points pass validation
        assert (
            result.passed
        ), f"RSI(7) failed validation with {result.failed_points} points"

    def test_rsi_bounded_values(self):
        """Test that RSI values are always bounded between 0 and 100."""
        # Test with all datasets
        for dataset_func in [
            create_reference_dataset_1,
            create_reference_dataset_2,
            create_reference_dataset_3,
            create_reference_dataset_4,
        ]:
            data = dataset_func()

            for period in [7, 14]:
                # Calculate RSI
                rsi = RSIIndicator(period=period)
                result = rsi.compute(data)

                # Check bounds, ignoring NaN values
                non_nan = result.dropna()
                assert non_nan.min() >= 0, f"RSI({period}) values should be >= 0"
                assert non_nan.max() <= 100, f"RSI({period}) values should be <= 100"

                # Log report
                report = generate_indicator_report(
                    rsi, data, key_points=[period, period * 2, len(data) - 1]
                )
                logger.info(f"RSI({period}) bounds check report: {report}")


class TestAllIndicatorsValidation:
    """Comprehensive tests for all indicators together."""

    def test_all_indicators_base_behavior(self):
        """Test basic behavior requirements for all indicators."""
        # Common test data
        data = create_reference_dataset_1()

        # Define all indicators to test with default parameters
        indicators = [SimpleMovingAverage(), ExponentialMovingAverage(), RSIIndicator()]

        # Test each indicator
        for indicator in indicators:
            # Compute indicator
            result = indicator.compute(data)

            # Basic requirements:
            # 1. Return type is pd.Series
            assert isinstance(
                result, pd.Series
            ), f"{indicator.name} should return a pd.Series"

            # 2. Output has same length as input
            assert len(result) == len(
                data
            ), f"{indicator.name} output should have same length as input"

            # 3. No spurious NaN values after warmup period
            warmup = indicator.params.get("period", 0) + 2  # add buffer
            if warmup < len(data):
                assert not pd.isna(
                    result.iloc[warmup:]
                ).any(), f"{indicator.name} should not have NaN values after warmup"

    def test_all_indicators_on_edge_cases(self):
        """Test all indicators on edge case data."""
        # Edge cases to test
        tests = [
            # Empty DataFrame
            {
                "name": "empty_df",
                "data": pd.DataFrame(),
                "should_raise": True,
                "error_type": DataError,
            },
            # DataFrame with non-required columns
            {
                "name": "missing_columns",
                "data": pd.DataFrame({"some_column": [1, 2, 3]}),
                "should_raise": True,
                "error_type": DataError,
            },
            # DataFrame with too few rows
            {
                "name": "insufficient_data",
                "data": pd.DataFrame({"close": [1, 2]}),
                "should_raise": True,
                "error_type": DataError,
            },
        ]

        # Indicators to test
        indicators = [
            SimpleMovingAverage(period=5),
            ExponentialMovingAverage(period=5),
            RSIIndicator(period=5),
        ]

        # Run edge case tests
        for test in tests:
            for indicator in indicators:
                if test["should_raise"]:
                    with pytest.raises(test["error_type"]) as excinfo:
                        indicator.compute(test["data"])
                    logger.info(
                        f"{indicator.name} correctly raised {test['error_type'].__name__} "
                        f"for {test['name']}: {str(excinfo.value)}"
                    )
                else:
                    try:
                        indicator.compute(test["data"])
                        logger.info(
                            f"{indicator.name} handled {test['name']} correctly"
                        )
                    except Exception as e:
                        pytest.fail(
                            f"{indicator.name} should not raise error for {test['name']}: {e}"
                        )

    def test_indicators_factory_integration(self):
        """Test that indicators can be created through factory and validated."""
        from ktrdr.config.models import IndicatorConfig
        from ktrdr.indicators import IndicatorFactory

        # Create indicator configs (name is the indicator type)
        configs = [
            IndicatorConfig(name="SMA", feature_id="my_sma_5", params={"period": 5}),
            IndicatorConfig(name="EMA", feature_id="my_ema_5", params={"period": 5}),
            IndicatorConfig(name="RSI", feature_id="my_rsi_14", params={"period": 14}),
        ]

        # Create indicators with factory
        factory = IndicatorFactory(configs)
        indicators = factory.build()

        # Ensure we got all the indicators
        assert len(indicators) == 3

        # Ensure indicators were created with correct types
        assert isinstance(indicators[0], SimpleMovingAverage)
        assert isinstance(indicators[1], ExponentialMovingAverage)
        assert isinstance(indicators[2], RSIIndicator)

        # Test all indicators on a dataset
        data = create_reference_dataset_1()

        # Generate reports for all indicators
        for indicator in indicators:
            report = generate_indicator_report(indicator, data)
            logger.info(f"Factory-created {indicator.name} report: {report}")

            # Basic validation
            assert report["success"]
            assert report["length"] == len(data)
            assert "stats" in report

            # Check that indicator produces outputs
            assert report["stats"]["nan_count"] < len(data)
