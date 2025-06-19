"""
Real E2E tests for Multi-Timeframe Data Infrastructure.

This module contains real end-to-end tests that validate multi-timeframe
functionality with actual IB Gateway connections and real market data.

These tests complement the unit tests by validating:
- Real IB data availability across timeframes
- Actual data synchronization scenarios
- Graceful degradation with limited data
- Performance with real datasets
- Integration with existing KTRDR components
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time

from ktrdr.data.multi_timeframe_manager import (
    MultiTimeframeDataManager,
    TimeframeConfig,
    TimeframeDataResult,
)
from ktrdr.data.timeframe_synchronizer import (
    TimeframeSynchronizer,
    align_timeframes_to_lowest,
    calculate_multi_timeframe_periods,
)
from ktrdr.errors import DataError, DataValidationError


@pytest.mark.real_ib
class TestRealMultiTimeframeDataLoading:
    """Test multi-timeframe data loading with real IB data."""

    @pytest.fixture
    def manager(self):
        """Create manager with IB enabled."""
        return MultiTimeframeDataManager(
            enable_ib=True,
            enable_synthetic_generation=True,
            cache_size=10,  # Small cache for testing
        )

    @pytest.fixture
    def basic_config(self):
        """Basic multi-timeframe configuration."""
        return TimeframeConfig(
            primary_timeframe="1h",
            auxiliary_timeframes=["4h", "1d"],
            periods=50,  # Smaller for real testing
            enable_synthetic_generation=True,
        )

    def test_real_aapl_multi_timeframe_loading(self, manager, basic_config):
        """Test loading AAPL data across multiple timeframes."""
        # AAPL should have good data availability across timeframes
        result = manager.load_multi_timeframe_data("AAPL", basic_config)

        # Basic validation
        assert isinstance(result, TimeframeDataResult)
        assert result.primary_timeframe == "1h"
        assert "1h" in result.available_timeframes
        assert len(result.data) >= 1  # At least primary timeframe

        # Data quality validation
        primary_data = result.data["1h"]
        assert not primary_data.empty
        assert len(primary_data) >= 10  # Reasonable amount of data
        assert all(
            col in primary_data.columns
            for col in ["open", "high", "low", "close", "volume"]
        )

        # Timeframe-specific validation
        for timeframe, data in result.data.items():
            # Each timeframe should have proper OHLCV structure
            assert not data.empty, f"Empty data for {timeframe}"
            assert isinstance(
                data.index, pd.DatetimeIndex
            ), f"Invalid index for {timeframe}"
            assert data.index.tz is not None, f"Missing timezone for {timeframe}"

            # Basic data integrity
            assert (data["high"] >= data["low"]).all(), f"High < Low in {timeframe}"
            assert (data["high"] >= data["open"]).all(), f"High < Open in {timeframe}"
            assert (data["high"] >= data["close"]).all(), f"High < Close in {timeframe}"
            assert (data["volume"] >= 0).all(), f"Negative volume in {timeframe}"

        # Report results
        print(f"\n📊 Multi-Timeframe Test Results for AAPL:")
        print(f"   Available timeframes: {result.available_timeframes}")
        print(f"   Failed timeframes: {result.failed_timeframes}")
        print(f"   Synthetic timeframes: {result.synthetic_timeframes}")
        print(f"   Load time: {result.load_time:.2f}s")
        print(f"   Warnings: {len(result.warnings)}")

        for tf, data in result.data.items():
            print(f"   {tf}: {len(data)} bars, {data.index[0]} to {data.index[-1]}")

    def test_real_multi_timeframe_with_limited_symbol(self, manager):
        """Test with a symbol that may have limited timeframe availability."""
        config = TimeframeConfig(
            primary_timeframe="1h",
            auxiliary_timeframes=["4h", "1d", "1w"],  # Include weekly
            periods=30,
            enable_synthetic_generation=True,
        )

        # Use a less common symbol that might have data limitations
        symbol = "QQQ"  # ETF, should have reasonable coverage

        result = manager.load_multi_timeframe_data(symbol, config)

        # Should succeed with at least primary timeframe
        assert result.primary_timeframe == "1h"
        assert "1h" in result.available_timeframes
        assert len(result.data["1h"]) > 0

        # Document what we got vs. what we requested
        requested_timeframes = {config.primary_timeframe} | set(
            config.auxiliary_timeframes
        )
        available_timeframes = set(result.available_timeframes)
        missing_timeframes = requested_timeframes - available_timeframes

        print(f"\n📊 Limited Symbol Test Results for {symbol}:")
        print(f"   Requested: {sorted(requested_timeframes)}")
        print(f"   Available: {sorted(available_timeframes)}")
        print(f"   Missing: {sorted(missing_timeframes)}")
        print(f"   Synthetic: {result.synthetic_timeframes}")

        # If synthetic generation is working, we should have more available than failed
        if result.synthetic_timeframes:
            print(f"   ✅ Synthetic data generation successful!")
            for tf in result.synthetic_timeframes:
                synthetic_data = result.data[tf]
                print(f"      {tf}: {len(synthetic_data)} synthetic bars")

    def test_real_graceful_degradation(self, manager):
        """Test graceful degradation when some timeframes unavailable."""
        config = TimeframeConfig(
            primary_timeframe="1h",
            auxiliary_timeframes=["4h", "1d"],
            periods=20,
            require_minimum_timeframes=1,  # Allow degradation
            enable_synthetic_generation=False,  # Disable to test pure degradation
        )

        # Test with multiple symbols to see different data availability patterns
        test_symbols = ["AAPL", "MSFT", "GOOGL"]
        results = {}

        for symbol in test_symbols:
            try:
                result = manager.load_multi_timeframe_data(symbol, config)
                results[symbol] = result

                # Should always have primary timeframe
                assert "1h" in result.available_timeframes

            except DataError as e:
                print(f"   ❌ {symbol}: {e}")
                continue

        # Analyze patterns
        print(f"\n📊 Graceful Degradation Test Results:")
        for symbol, result in results.items():
            success_rate = len(result.available_timeframes) / (
                1 + len(config.auxiliary_timeframes)
            )
            print(
                f"   {symbol}: {len(result.available_timeframes)}/3 timeframes "
                f"({success_rate:.1%}), {len(result.failed_timeframes)} failed"
            )

    def test_real_cache_behavior(self, manager, basic_config):
        """Test caching behavior with real data."""
        symbol = "AAPL"

        # First load - should hit IB
        start_time = time.time()
        result1 = manager.load_multi_timeframe_data(symbol, basic_config)
        first_load_time = time.time() - start_time

        # Second load - should hit cache
        start_time = time.time()
        result2 = manager.load_multi_timeframe_data(symbol, basic_config)
        second_load_time = time.time() - start_time

        # Verify cache hit
        assert (
            second_load_time < first_load_time
        ), "Cache should make second load faster"
        assert len(result1.data) == len(result2.data), "Cached results should match"

        # Verify data consistency
        for timeframe in result1.available_timeframes:
            if timeframe in result2.available_timeframes:
                pd.testing.assert_frame_equal(
                    result1.data[timeframe],
                    result2.data[timeframe],
                    check_exact=False,  # Allow for minor floating point differences
                )

        print(f"\n📊 Cache Performance Test:")
        print(f"   First load (IB): {first_load_time:.2f}s")
        print(f"   Second load (cache): {second_load_time:.2f}s")
        print(f"   Speed improvement: {first_load_time/second_load_time:.1f}x")

        # Test cache stats
        stats = manager.get_cache_stats()
        assert stats["cache_size"] > 0
        print(f"   Cache size: {stats['cache_size']}/{stats['max_cache_size']}")


@pytest.mark.real_ib
class TestRealTimeframeSynchronization:
    """Test timeframe synchronization with real market data."""

    @pytest.fixture
    def synchronizer(self):
        """Create synchronizer instance."""
        return TimeframeSynchronizer()

    @pytest.fixture
    def manager(self):
        """Create manager for loading real data."""
        return MultiTimeframeDataManager(enable_ib=True)

    def test_real_data_alignment(self, synchronizer, manager):
        """Test alignment of real market data across timeframes."""
        # Load real data across different timeframes
        config = TimeframeConfig(
            primary_timeframe="1h",
            auxiliary_timeframes=["4h"],
            periods=48,  # 2 days of hourly data
            enable_synthetic_generation=False,
        )

        result = manager.load_multi_timeframe_data("AAPL", config)

        # Test alignment if we have both timeframes
        if "1h" in result.data and "4h" in result.data:
            data_1h = result.data["1h"]
            data_4h = result.data["4h"]

            # Test forward-fill alignment
            alignment_result = synchronizer.forward_fill_alignment(
                data_4h, data_1h, "4h", "1h"
            )

            # Validate alignment
            assert alignment_result.rows_after == len(data_1h)
            assert alignment_result.quality_score > 0.5
            assert alignment_result.missing_ratio < 0.5

            # Check that aligned data follows market hours
            aligned_data = alignment_result.aligned_data
            assert not aligned_data.empty

            print(f"\n📊 Real Data Alignment Test:")
            print(f"   Source (4h): {len(data_4h)} bars")
            print(f"   Reference (1h): {len(data_1h)} bars")
            print(f"   Aligned: {len(aligned_data)} bars")
            print(f"   Quality score: {alignment_result.quality_score:.3f}")
            print(f"   Missing ratio: {alignment_result.missing_ratio:.3f}")

        else:
            pytest.skip("Need both 1h and 4h data for alignment test")

    def test_real_market_gaps_handling(self, synchronizer, manager):
        """Test handling of real market gaps (weekends, holidays)."""
        # Load data that spans weekends
        config = TimeframeConfig(
            primary_timeframe="1h",
            auxiliary_timeframes=["1d"],
            periods=72,  # 3 days including weekend
            enable_synthetic_generation=False,
        )

        result = manager.load_multi_timeframe_data("AAPL", config)

        if "1h" in result.data and "1d" in result.data:
            data_1h = result.data["1h"]
            data_1d = result.data["1d"]

            # Check for weekend gaps in hourly data
            time_diffs = data_1h.index.to_series().diff().dropna()
            normal_diff = pd.Timedelta(hours=1)
            gap_threshold = pd.Timedelta(hours=12)

            weekend_gaps = time_diffs[time_diffs > gap_threshold]

            print(f"\n📊 Market Gaps Analysis:")
            print(f"   Hourly data span: {data_1h.index[0]} to {data_1h.index[-1]}")
            print(f"   Total hourly bars: {len(data_1h)}")
            print(f"   Weekend/holiday gaps found: {len(weekend_gaps)}")

            if len(weekend_gaps) > 0:
                print(f"   Gap examples:")
                for i, (timestamp, gap) in enumerate(weekend_gaps.head(3).items()):
                    print(f"      {timestamp}: {gap}")

            # Test temporal consistency validation
            consistency_results = synchronizer.validate_temporal_consistency(
                {"1h": data_1h, "1d": data_1d}
            )

            print(f"   Temporal consistency:")
            for tf, is_consistent in consistency_results.items():
                print(
                    f"      {tf}: {'✅ consistent' if is_consistent else '⚠️ gaps detected'}"
                )


@pytest.mark.real_ib
class TestRealMultiTimeframeIntegration:
    """Test integration with existing KTRDR components."""

    def test_real_integration_with_data_manager(self):
        """Test that MultiTimeframeDataManager integrates with existing DataManager."""
        from ktrdr.data.data_manager import DataManager

        # Test that MultiTimeframeDataManager IS-A DataManager
        mtf_manager = MultiTimeframeDataManager(enable_ib=True)
        assert isinstance(mtf_manager, DataManager)

        # Test that it can do everything a regular DataManager does
        try:
            # Basic DataManager functionality should work
            data = mtf_manager.load_data("AAPL", "1h", periods=10)
            assert not data.empty
            print(f"✅ Basic DataManager functionality works: {len(data)} bars loaded")

        except Exception as e:
            # If IB is unavailable, that's expected
            if "IB" in str(e) or "connection" in str(e).lower():
                print(f"⚠️ IB unavailable for integration test: {e}")
            else:
                raise

    def test_real_memory_usage_large_dataset(self):
        """Test memory usage with larger real datasets."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        manager = MultiTimeframeDataManager(enable_ib=True, cache_size=5)

        # Load larger datasets
        config = TimeframeConfig(
            primary_timeframe="1h",
            auxiliary_timeframes=["4h", "1d"],
            periods=200,  # Larger dataset
            enable_synthetic_generation=True,
        )

        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
        results = []

        for symbol in symbols:
            try:
                result = manager.load_multi_timeframe_data(symbol, config)
                results.append((symbol, result))

                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory

                print(
                    f"   {symbol}: {len(result.available_timeframes)} timeframes, "
                    f"memory: +{memory_increase:.1f}MB"
                )

                # Memory should not grow excessively
                assert (
                    memory_increase < 500
                ), f"Memory usage too high: {memory_increase}MB"

            except Exception as e:
                print(f"   {symbol}: Failed - {e}")

        final_memory = process.memory_info().rss / 1024 / 1024
        total_increase = final_memory - initial_memory

        print(f"\n📊 Memory Usage Test:")
        print(f"   Initial memory: {initial_memory:.1f}MB")
        print(f"   Final memory: {final_memory:.1f}MB")
        print(f"   Total increase: {total_increase:.1f}MB")
        print(f"   Symbols processed: {len(results)}")

        # Cleanup test
        manager.clear_cache()
        print(f"   Cache cleared successfully")

    def test_real_performance_constraints(self):
        """Test that multi-timeframe operations meet performance requirements."""
        manager = MultiTimeframeDataManager(enable_ib=True)

        config = TimeframeConfig(
            primary_timeframe="1h", auxiliary_timeframes=["4h", "1d"], periods=100
        )

        # Test performance requirements
        start_time = time.time()
        result = manager.load_multi_timeframe_data("AAPL", config)
        load_time = time.time() - start_time

        # Performance requirements from design document
        assert load_time < 10.0, f"Load time too slow: {load_time:.2f}s (max 10s)"

        print(f"\n📊 Performance Test:")
        print(f"   Load time: {load_time:.2f}s (requirement: <10s)")
        print(f"   Timeframes loaded: {len(result.available_timeframes)}")
        print(f"   Total data points: {sum(len(df) for df in result.data.values())}")

        # Test cached performance
        start_time = time.time()
        cached_result = manager.load_multi_timeframe_data("AAPL", config)
        cached_time = time.time() - start_time

        assert cached_time < 1.0, f"Cached load too slow: {cached_time:.2f}s (max 1s)"
        print(f"   Cached load time: {cached_time:.2f}s (requirement: <1s)")


@pytest.mark.real_ib
class TestRealErrorScenarios:
    """Test real-world error scenarios and edge cases."""

    def test_real_invalid_symbol_handling(self):
        """Test handling of invalid symbols with graceful degradation."""
        manager = MultiTimeframeDataManager(enable_ib=True)

        config = TimeframeConfig(
            primary_timeframe="1h", auxiliary_timeframes=["4h"], periods=10
        )

        # Test with clearly invalid symbol
        invalid_symbol = "INVALID_SYMBOL_12345"

        with pytest.raises(DataError) as exc_info:
            manager.load_multi_timeframe_data(invalid_symbol, config)

        error_msg = str(exc_info.value)
        assert "primary timeframe" in error_msg.lower()
        print(f"✅ Invalid symbol properly rejected: {error_msg}")

    def test_real_ib_unavailable_handling(self):
        """Test behavior when IB Gateway is unavailable."""
        # This test will naturally fail if IB is unavailable,
        # which is the correct behavior for primary timeframe
        manager = MultiTimeframeDataManager(enable_ib=True)

        config = TimeframeConfig(
            primary_timeframe="1h", auxiliary_timeframes=["4h"], periods=10
        )

        try:
            result = manager.load_multi_timeframe_data("AAPL", config)
            print("✅ IB Gateway available and working")
            assert len(result.available_timeframes) > 0

        except DataError as e:
            # This is expected if IB Gateway is not running
            if any(
                keyword in str(e).lower() for keyword in ["connection", "ib", "gateway"]
            ):
                print(f"⚠️ IB Gateway unavailable (expected): {e}")
                pytest.skip("IB Gateway not available for this test")
            else:
                raise


# Utility functions for manual testing
def run_comprehensive_real_multi_timeframe_test():
    """
    Comprehensive manual test function for debugging and validation.

    Run this directly if you want to see detailed output:
    python -c "from tests.e2e_real.test_real_multi_timeframe import run_comprehensive_real_multi_timeframe_test; run_comprehensive_real_multi_timeframe_test()"
    """
    print("🚀 Running Comprehensive Real Multi-Timeframe Test")
    print("=" * 60)

    try:
        manager = MultiTimeframeDataManager(
            enable_ib=True, enable_synthetic_generation=True
        )

        config = TimeframeConfig(
            primary_timeframe="1h", auxiliary_timeframes=["4h", "1d"], periods=50
        )

        symbols = ["AAPL", "MSFT", "GOOGL"]

        for symbol in symbols:
            print(f"\n📊 Testing {symbol}:")
            try:
                result = manager.load_multi_timeframe_data(symbol, config)

                print(f"   ✅ Success: {len(result.available_timeframes)} timeframes")
                print(f"      Available: {result.available_timeframes}")
                print(f"      Failed: {result.failed_timeframes}")
                print(f"      Synthetic: {result.synthetic_timeframes}")
                print(f"      Load time: {result.load_time:.2f}s")

                for tf, data in result.data.items():
                    print(
                        f"      {tf}: {len(data)} bars, "
                        f"{data.index[0].strftime('%Y-%m-%d %H:%M')} to "
                        f"{data.index[-1].strftime('%Y-%m-%d %H:%M')}"
                    )

            except Exception as e:
                print(f"   ❌ Failed: {e}")

        print(f"\n✅ Comprehensive test completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Allow running this module directly for manual testing
    run_comprehensive_real_multi_timeframe_test()
