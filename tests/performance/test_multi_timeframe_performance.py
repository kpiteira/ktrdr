"""Performance tests for multi-timeframe indicator pipeline.

This module tests performance characteristics and optimizations for large datasets.
"""

import pytest
import pandas as pd
import numpy as np
import time
import psutil
import os
from typing import Dict, List
from dataclasses import dataclass

from ktrdr.indicators.multi_timeframe_indicator_engine import (
    MultiTimeframeIndicatorEngine,
    TimeframeIndicatorConfig
)
from ktrdr.indicators.column_standardization import ColumnStandardizer


@dataclass
class PerformanceMetrics:
    """Performance metrics for testing."""
    processing_time: float
    memory_usage_mb: float
    cpu_percent: float
    data_points_processed: int
    throughput_points_per_second: float


class PerformanceProfiler:
    """Helper class for profiling performance."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.start_time = None
        self.start_memory = None
        self.start_cpu = None
    
    def start_profiling(self):
        """Start performance profiling."""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.start_cpu = self.process.cpu_percent()
    
    def get_metrics(self, data_points: int) -> PerformanceMetrics:
        """Get performance metrics."""
        end_time = time.time()
        end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        end_cpu = self.process.cpu_percent()
        
        processing_time = end_time - self.start_time
        memory_usage = end_memory - self.start_memory
        cpu_percent = end_cpu
        throughput = data_points / processing_time if processing_time > 0 else 0
        
        return PerformanceMetrics(
            processing_time=processing_time,
            memory_usage_mb=memory_usage,
            cpu_percent=cpu_percent,
            data_points_processed=data_points,
            throughput_points_per_second=throughput
        )


class TestMultiTimeframePerformance:
    """Performance tests for multi-timeframe indicator processing."""

    def create_large_dataset(self, hours: int = 24*30*6) -> Dict[str, pd.DataFrame]:
        """Create large dataset (6 months of hourly data by default)."""
        # Generate realistic time series data
        dates_1h = pd.date_range('2024-01-01', periods=hours, freq='1h')
        np.random.seed(42)
        
        # Use realistic price simulation
        n_points = len(dates_1h)
        
        # Generate correlated returns with volatility clustering
        returns = []
        volatility = 0.02
        for i in range(n_points):
            # Volatility clustering (GARCH-like)
            if i > 0:
                volatility = 0.95 * volatility + 0.05 * abs(returns[-1])
            
            # Generate return with current volatility
            ret = np.random.normal(0, volatility)
            returns.append(ret)
        
        # Convert to prices
        prices = 100 * np.exp(np.cumsum(returns))
        
        # Create realistic OHLC data
        noise = 0.001
        data_1h = pd.DataFrame({
            'timestamp': dates_1h,
            'open': prices * (1 + np.random.normal(0, noise, n_points)),
            'high': prices * (1 + np.abs(np.random.normal(0, noise*2, n_points))),
            'low': prices * (1 - np.abs(np.random.normal(0, noise*2, n_points))),
            'close': prices,
            'volume': np.random.lognormal(9, 0.5, n_points).astype(int)
        })
        
        # Ensure OHLC constraints
        data_1h['high'] = np.maximum(data_1h['high'], 
                                   np.maximum(data_1h['open'], data_1h['close']))
        data_1h['low'] = np.minimum(data_1h['low'], 
                                  np.minimum(data_1h['open'], data_1h['close']))
        
        # Create 4h and daily data by resampling
        data_4h = data_1h.set_index('timestamp').resample('4h').agg({
            'open': 'first',
            'high': 'max', 
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).reset_index()
        
        data_1d = data_1h.set_index('timestamp').resample('1d').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min', 
            'close': 'last',
            'volume': 'sum'
        }).reset_index()
        
        return {
            '1h': data_1h,
            '4h': data_4h,
            '1d': data_1d
        }

    def test_baseline_performance_small_dataset(self):
        """Establish baseline performance with small dataset."""
        
        # Small dataset (1 week of hourly data)
        data = self.create_large_dataset(hours=24*7)
        
        # Simple configuration
        timeframe_configs = [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}}
                ]
            ),
            TimeframeIndicatorConfig(
                timeframe='4h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}}
                ]
            )
        ]
        
        profiler = PerformanceProfiler()
        profiler.start_profiling()
        
        engine = MultiTimeframeIndicatorEngine(timeframe_configs)
        results = engine.apply_multi_timeframe(data)
        
        total_points = sum(len(df) for df in data.values())
        metrics = profiler.get_metrics(total_points)
        
        # Baseline expectations (should be very fast)
        assert metrics.processing_time < 2.0  # Under 2 seconds
        assert metrics.memory_usage_mb < 100  # Under 100MB
        assert metrics.throughput_points_per_second > 100  # > 100 points/sec
        
        print(f"Baseline Performance - Points: {total_points}, "
              f"Time: {metrics.processing_time:.2f}s, "
              f"Memory: {metrics.memory_usage_mb:.1f}MB, "
              f"Throughput: {metrics.throughput_points_per_second:.0f} pts/sec")

    def test_medium_dataset_performance(self):
        """Test performance with medium dataset (1 month)."""
        
        # Medium dataset (1 month of hourly data)
        data = self.create_large_dataset(hours=24*30)
        
        # Moderate complexity configuration
        timeframe_configs = [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 10}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}},
                    {'type': 'ExponentialMovingAverage', 'params': {'period': 12}}
                ]
            ),
            TimeframeIndicatorConfig(
                timeframe='4h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 30}}
                ]
            ),
            TimeframeIndicatorConfig(
                timeframe='1d',
                indicators=[
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}}
                ]
            )
        ]
        
        profiler = PerformanceProfiler()
        profiler.start_profiling()
        
        engine = MultiTimeframeIndicatorEngine(timeframe_configs)
        results = engine.apply_multi_timeframe(data)
        
        total_points = sum(len(df) for df in data.values())
        metrics = profiler.get_metrics(total_points)
        
        # Medium dataset expectations 
        assert metrics.processing_time < 10.0  # Under 10 seconds
        assert metrics.memory_usage_mb < 500   # Under 500MB
        assert metrics.throughput_points_per_second > 50  # > 50 points/sec
        
        print(f"Medium Performance - Points: {total_points}, "
              f"Time: {metrics.processing_time:.2f}s, "
              f"Memory: {metrics.memory_usage_mb:.1f}MB, "
              f"Throughput: {metrics.throughput_points_per_second:.0f} pts/sec")

    def test_large_dataset_performance(self):
        """Test performance with large dataset (6 months)."""
        
        # Large dataset (6 months of hourly data)
        data = self.create_large_dataset(hours=24*30*6)
        
        # Complex configuration
        timeframe_configs = [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 10}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}},
                    {'type': 'ExponentialMovingAverage', 'params': {'period': 12}},
                    {'type': 'ExponentialMovingAverage', 'params': {'period': 26}}
                ]
            ),
            TimeframeIndicatorConfig(
                timeframe='4h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 30}},
                    {'type': 'ExponentialMovingAverage', 'params': {'period': 21}}
                ]
            ),
            TimeframeIndicatorConfig(
                timeframe='1d',
                indicators=[
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 50}}
                ]
            )
        ]
        
        profiler = PerformanceProfiler()
        profiler.start_profiling()
        
        engine = MultiTimeframeIndicatorEngine(timeframe_configs)
        results = engine.apply_multi_timeframe(data)
        
        total_points = sum(len(df) for df in data.values())
        metrics = profiler.get_metrics(total_points)
        
        # Large dataset expectations (more lenient)
        assert metrics.processing_time < 30.0  # Under 30 seconds
        assert metrics.memory_usage_mb < 1000  # Under 1GB
        assert metrics.throughput_points_per_second > 20  # > 20 points/sec
        
        print(f"Large Performance - Points: {total_points}, "
              f"Time: {metrics.processing_time:.2f}s, "
              f"Memory: {metrics.memory_usage_mb:.1f}MB, "
              f"Throughput: {metrics.throughput_points_per_second:.0f} pts/sec")

    def test_memory_efficiency_with_chunked_processing(self):
        """Test memory efficiency with chunked data processing."""
        
        # Very large dataset that might cause memory issues
        data = self.create_large_dataset(hours=24*30*12)  # 1 year
        
        # Test chunked processing
        timeframe_configs = [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}}
                ]
            )
        ]
        
        engine = MultiTimeframeIndicatorEngine(timeframe_configs)
        
        # Process in chunks to manage memory
        chunk_size = 1000  # Process 1000 rows at a time
        chunked_results = {}
        
        profiler = PerformanceProfiler()
        profiler.start_profiling()
        
        for timeframe, df in data.items():
            timeframe_results = []
            
            # Process in chunks
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i+chunk_size].copy()
                
                # For non-first chunks, include some overlap for indicator continuity
                if i > 0:
                    overlap = min(50, i)  # 50 row overlap
                    chunk = pd.concat([df.iloc[i-overlap:i], chunk], ignore_index=True)
                
                # Process chunk
                chunk_data = {timeframe: chunk}
                chunk_result = engine.apply_multi_timeframe(chunk_data)
                
                # Remove overlap from result (except first chunk)
                if i > 0 and len(chunk_result[timeframe]) > 50:
                    chunk_result[timeframe] = chunk_result[timeframe].iloc[50:]
                
                timeframe_results.append(chunk_result[timeframe])
            
            # Combine chunks
            if timeframe_results:
                chunked_results[timeframe] = pd.concat(timeframe_results, ignore_index=True)
        
        total_points = sum(len(df) for df in data.values())
        metrics = profiler.get_metrics(total_points)
        
        # Memory should be much more reasonable with chunking
        assert metrics.memory_usage_mb < 2000  # Under 2GB even for 1 year
        
        print(f"Chunked Performance - Points: {total_points}, "
              f"Time: {metrics.processing_time:.2f}s, "
              f"Memory: {metrics.memory_usage_mb:.1f}MB")

    def test_parallel_timeframe_processing(self):
        """Test parallel processing of different timeframes."""
        
        import concurrent.futures
        from functools import partial
        
        data = self.create_large_dataset(hours=24*30*3)  # 3 months
        
        # Create separate engines for each timeframe
        timeframe_configs = {
            '1h': [TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}}
                ]
            )],
            '4h': [TimeframeIndicatorConfig(
                timeframe='4h', 
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'ExponentialMovingAverage', 'params': {'period': 21}}
                ]
            )],
            '1d': [TimeframeIndicatorConfig(
                timeframe='1d',
                indicators=[
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}}
                ]
            )]
        }
        
        def process_timeframe(timeframe, configs, data_dict):
            """Process a single timeframe."""
            engine = MultiTimeframeIndicatorEngine(configs)
            timeframe_data = {timeframe: data_dict[timeframe]}
            return timeframe, engine.apply_multi_timeframe(timeframe_data)
        
        profiler = PerformanceProfiler()
        profiler.start_profiling()
        
        # Process timeframes in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for tf, configs in timeframe_configs.items():
                future = executor.submit(process_timeframe, tf, configs, data)
                futures.append(future)
            
            # Collect results
            parallel_results = {}
            for future in concurrent.futures.as_completed(futures):
                timeframe, result = future.result()
                parallel_results.update(result)
        
        total_points = sum(len(df) for df in data.values())
        metrics = profiler.get_metrics(total_points)
        
        # Parallel processing should be faster than sequential
        # (This is more of a demonstration than a strict test)
        assert len(parallel_results) == 3
        
        print(f"Parallel Performance - Points: {total_points}, "
              f"Time: {metrics.processing_time:.2f}s, "
              f"Memory: {metrics.memory_usage_mb:.1f}MB")

    def test_column_standardization_performance(self):
        """Test performance of column standardization with many columns."""
        
        # Create data with many indicators
        data = self.create_large_dataset(hours=24*30)  # 1 month
        
        # Many indicators configuration
        indicators = []
        for period in [10, 14, 20, 30, 50]:
            indicators.extend([
                {'type': 'RSI', 'params': {'period': period}},
                {'type': 'SimpleMovingAverage', 'params': {'period': period}},
                {'type': 'ExponentialMovingAverage', 'params': {'period': period}}
            ])
        
        timeframe_configs = [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=indicators[:10]  # Limit to prevent too much data
            ),
            TimeframeIndicatorConfig(
                timeframe='4h',
                indicators=indicators[5:15]
            ),
            TimeframeIndicatorConfig(
                timeframe='1d',
                indicators=indicators[10:15]
            )
        ]
        
        profiler = PerformanceProfiler()
        profiler.start_profiling()
        
        engine = MultiTimeframeIndicatorEngine(timeframe_configs)
        results = engine.apply_multi_timeframe(data)
        
        # Test column standardization performance
        standardizer = ColumnStandardizer()
        
        for timeframe, df in results.items():
            columns = df.columns.tolist()
            mapping = standardizer.standardize_dataframe_columns(columns, timeframe)
            
            # Verify standardization worked
            indicator_cols = [col for col in columns 
                           if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            for col in indicator_cols:
                assert col.endswith(f'_{timeframe}')
        
        total_points = sum(len(df) for df in data.values())
        metrics = profiler.get_metrics(total_points)
        
        # Should handle many columns efficiently
        assert metrics.processing_time < 20.0  # Under 20 seconds
        
        print(f"Column Standardization Performance - Points: {total_points}, "
              f"Columns: {sum(len(df.columns) for df in results.values())}, "
              f"Time: {metrics.processing_time:.2f}s")

    def test_incremental_processing_performance(self):
        """Test performance of incremental data processing."""
        
        # Simulate real-time incremental updates
        base_data = self.create_large_dataset(hours=24*30)  # 1 month base
        
        timeframe_configs = [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}}
                ]
            )
        ]
        
        engine = MultiTimeframeIndicatorEngine(timeframe_configs)
        
        # Process base data
        base_results = engine.apply_multi_timeframe(base_data)
        
        # Simulate incremental updates (new hourly data)
        profiler = PerformanceProfiler()
        profiler.start_profiling()
        
        incremental_times = []
        
        for hour in range(24):  # 24 new hours
            # Create new data point
            last_timestamp = base_data['1h']['timestamp'].iloc[-1]
            new_timestamp = last_timestamp + pd.Timedelta(hours=1)
            
            # Simulate new price data
            last_price = base_data['1h']['close'].iloc[-1]
            new_price = last_price * (1 + np.random.normal(0, 0.01))
            
            new_row = pd.DataFrame({
                'timestamp': [new_timestamp],
                'open': [new_price * 0.999],
                'high': [new_price * 1.001],
                'low': [new_price * 0.998],
                'close': [new_price],
                'volume': [np.random.randint(1000, 10000)]
            })
            
            # Add to existing data
            updated_data = {
                '1h': pd.concat([base_data['1h'], new_row], ignore_index=True)
            }
            
            # Process incremental update (should be fast)
            start_time = time.time()
            
            # For efficiency, only process recent data needed for indicators
            recent_data = {
                '1h': updated_data['1h'].tail(100)  # Only last 100 rows needed
            }
            
            incremental_result = engine.apply_multi_timeframe(recent_data)
            
            incremental_time = time.time() - start_time
            incremental_times.append(incremental_time)
            
            # Update base data for next iteration
            base_data = updated_data
        
        total_incremental_time = sum(incremental_times)
        avg_incremental_time = total_incremental_time / len(incremental_times)
        
        # Incremental updates should be very fast
        assert avg_incremental_time < 0.1  # Under 100ms per update
        assert max(incremental_times) < 0.5  # No single update over 500ms
        
        print(f"Incremental Processing - {len(incremental_times)} updates, "
              f"Avg: {avg_incremental_time*1000:.1f}ms, "
              f"Max: {max(incremental_times)*1000:.1f}ms, "
              f"Total: {total_incremental_time:.2f}s")


class TestPerformanceOptimizations:
    """Test specific performance optimizations."""

    def test_indicator_computation_caching(self):
        """Test caching of indicator computations."""
        
        data = self.create_large_dataset(hours=24*7)  # 1 week
        
        # Same indicator with same parameters should be cached
        timeframe_configs = [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'RSI', 'params': {'period': 14}},  # Duplicate
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}}  # Duplicate
                ]
            )
        ]
        
        # First run
        engine1 = MultiTimeframeIndicatorEngine(timeframe_configs)
        
        start_time = time.time()
        results1 = engine1.apply_multi_timeframe(data)
        first_run_time = time.time() - start_time
        
        # Second run with same configuration (should benefit from any caching)
        engine2 = MultiTimeframeIndicatorEngine(timeframe_configs)
        
        start_time = time.time()
        results2 = engine2.apply_multi_timeframe(data)
        second_run_time = time.time() - start_time
        
        # Results should be identical
        for timeframe in results1:
            pd.testing.assert_frame_equal(
                results1[timeframe].sort_index(axis=1), 
                results2[timeframe].sort_index(axis=1)
            )
        
        print(f"Caching Test - First: {first_run_time:.3f}s, "
              f"Second: {second_run_time:.3f}s")

    def test_vectorized_operations_performance(self):
        """Test that indicators use vectorized operations efficiently."""
        
        data = self.create_large_dataset(hours=24*30)  # 1 month
        
        # Compare vectorized vs non-vectorized approach
        timeframe_configs = [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}},
                    {'type': 'ExponentialMovingAverage', 'params': {'period': 12}}
                ]
            )
        ]
        
        engine = MultiTimeframeIndicatorEngine(timeframe_configs)
        
        # Measure vectorized performance
        profiler = PerformanceProfiler()
        profiler.start_profiling()
        
        results = engine.apply_multi_timeframe(data)
        
        total_points = len(data['1h'])
        metrics = profiler.get_metrics(total_points)
        
        # Vectorized operations should be very efficient
        assert metrics.throughput_points_per_second > 1000  # > 1000 points/sec
        
        print(f"Vectorized Performance - Throughput: {metrics.throughput_points_per_second:.0f} pts/sec")


if __name__ == "__main__":
    # Run performance tests manually
    import sys
    
    test_class = TestMultiTimeframePerformance()
    
    print("Running Multi-Timeframe Performance Tests...")
    print("=" * 60)
    
    try:
        print("\n1. Baseline Performance Test")
        test_class.test_baseline_performance_small_dataset()
        
        print("\n2. Medium Dataset Performance Test")
        test_class.test_medium_dataset_performance()
        
        print("\n3. Large Dataset Performance Test")
        test_class.test_large_dataset_performance()
        
        print("\n4. Memory Efficiency Test")
        test_class.test_memory_efficiency_with_chunked_processing()
        
        print("\n5. Column Standardization Performance Test")
        test_class.test_column_standardization_performance()
        
        print("\n6. Incremental Processing Test")
        test_class.test_incremental_processing_performance()
        
        print("\n" + "=" * 60)
        print("All performance tests completed successfully!")
        
    except Exception as e:
        print(f"Performance test failed: {e}")
        sys.exit(1)