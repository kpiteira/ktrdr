"""
Performance analysis tools for multi-timeframe fuzzy processing.

This module provides comprehensive performance benchmarking and analysis
tools for the multi-timeframe fuzzy processing pipeline, including
timing analysis, memory usage monitoring, and optimization recommendations.
"""

import gc
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import psutil

from ktrdr import get_logger
from ktrdr.services.fuzzy_pipeline_service import FuzzyPipelineService

# Set up module-level logger
logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """
    Comprehensive performance metrics for fuzzy processing.

    Attributes:
        total_time: Total processing time in seconds
        indicator_time: Time spent on indicator calculation
        fuzzy_time: Time spent on fuzzy processing
        memory_peak_mb: Peak memory usage in MB
        memory_start_mb: Memory usage at start
        memory_end_mb: Memory usage at end
        fuzzy_values_count: Number of fuzzy values generated
        timeframes_processed: Number of timeframes processed
        throughput_fv_per_sec: Fuzzy values generated per second
        cpu_usage_percent: Average CPU usage during processing
        optimization_score: Overall optimization score (0-100)
    """

    total_time: float = 0.0
    indicator_time: float = 0.0
    fuzzy_time: float = 0.0
    memory_peak_mb: float = 0.0
    memory_start_mb: float = 0.0
    memory_end_mb: float = 0.0
    fuzzy_values_count: int = 0
    timeframes_processed: int = 0
    throughput_fv_per_sec: float = 0.0
    cpu_usage_percent: float = 0.0
    optimization_score: float = 0.0

    def __post_init__(self):
        """Calculate derived metrics."""
        if self.total_time > 0 and self.fuzzy_values_count > 0:
            self.throughput_fv_per_sec = self.fuzzy_values_count / self.total_time

        # Calculate optimization score (0-100)
        # Based on throughput, memory efficiency, and processing balance
        throughput_score = min(100, self.throughput_fv_per_sec * 10)  # 10+ FV/sec = 100
        memory_efficiency = max(
            0, 100 - (self.memory_peak_mb - self.memory_start_mb) / 10
        )  # Penalty for high memory usage
        time_balance = 100 if self.total_time > 0 else 0

        self.optimization_score = (
            throughput_score + memory_efficiency + time_balance
        ) / 3


@dataclass
class BenchmarkResult:
    """
    Results from performance benchmarking.

    Attributes:
        test_name: Name of the benchmark test
        metrics: Performance metrics
        configuration: Test configuration used
        recommendations: Optimization recommendations
        raw_data: Raw performance data for detailed analysis
    """

    test_name: str
    metrics: PerformanceMetrics
    configuration: dict[str, Any]
    recommendations: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


class FuzzyPerformanceAnalyzer:
    """
    Performance analyzer for multi-timeframe fuzzy processing.

    This class provides comprehensive performance analysis including
    benchmarking, profiling, and optimization recommendations.
    """

    def __init__(self, enable_detailed_profiling: bool = True):
        """
        Initialize the performance analyzer.

        Args:
            enable_detailed_profiling: Enable detailed profiling (may impact performance)
        """
        self.enable_detailed_profiling = enable_detailed_profiling
        self.benchmark_results: list[BenchmarkResult] = []

        logger.info("Initialized FuzzyPerformanceAnalyzer")

    def benchmark_pipeline_performance(
        self,
        service: FuzzyPipelineService,
        test_configurations: list[dict[str, Any]],
        symbol: str = "AAPL",
        data_period_days: int = 30,
        warmup_runs: int = 1,
        benchmark_runs: int = 3,
    ) -> list[BenchmarkResult]:
        """
        Benchmark pipeline performance across different configurations.

        Args:
            service: FuzzyPipelineService instance to benchmark
            test_configurations: List of test configurations
            symbol: Symbol to use for testing
            data_period_days: Days of data to load
            warmup_runs: Number of warmup runs (discarded)
            benchmark_runs: Number of benchmark runs to average

        Returns:
            List of BenchmarkResult objects
        """
        logger.info(
            f"Starting performance benchmark with {len(test_configurations)} configurations"
        )

        results = []

        for i, config in enumerate(test_configurations):
            logger.info(
                f"Benchmarking configuration {i+1}/{len(test_configurations)}: {config.get('name', 'Unnamed')}"
            )

            # Extract indicator and fuzzy configs
            indicator_config = config.get("indicator_config", {})
            fuzzy_config = config.get("fuzzy_config", {})
            timeframes = config.get("timeframes")

            # Warmup runs
            for warmup in range(warmup_runs):
                try:
                    service.process_symbol_fuzzy(
                        symbol=symbol,
                        indicator_config=indicator_config,
                        fuzzy_config=fuzzy_config,
                        timeframes=timeframes,
                        data_period_days=data_period_days,
                    )
                except Exception as e:
                    logger.warning(f"Warmup run {warmup+1} failed: {e}")

            # Benchmark runs
            run_metrics = []
            for run in range(benchmark_runs):
                try:
                    metrics = self._measure_single_run(
                        service,
                        symbol,
                        indicator_config,
                        fuzzy_config,
                        timeframes,
                        data_period_days,
                    )
                    run_metrics.append(metrics)
                    logger.debug(
                        f"Run {run+1}: {metrics.total_time:.3f}s, {metrics.fuzzy_values_count} FV"
                    )

                except Exception as e:
                    logger.error(f"Benchmark run {run+1} failed: {e}")

            if run_metrics:
                # Average the metrics
                avg_metrics = self._average_metrics(run_metrics)

                # Generate recommendations
                recommendations = self._generate_recommendations(avg_metrics, config)

                # Create benchmark result
                result = BenchmarkResult(
                    test_name=config.get("name", f"Config_{i+1}"),
                    metrics=avg_metrics,
                    configuration=config,
                    recommendations=recommendations,
                    raw_data={"individual_runs": run_metrics},
                )

                results.append(result)
                self.benchmark_results.append(result)

                logger.info(
                    f"Configuration {i+1} average: {avg_metrics.total_time:.3f}s, "
                    f"score: {avg_metrics.optimization_score:.1f}"
                )

        return results

    def _measure_single_run(
        self,
        service: FuzzyPipelineService,
        symbol: str,
        indicator_config: dict[str, Any],
        fuzzy_config: dict[str, Any],
        timeframes: Optional[list[str]],
        data_period_days: int,
    ) -> PerformanceMetrics:
        """Measure performance metrics for a single run."""
        # Clear garbage collection
        gc.collect()

        # Record initial state
        process = psutil.Process()
        memory_start = process.memory_info().rss / 1024 / 1024  # MB
        cpu_start = process.cpu_percent()
        start_time = time.time()

        # Track peak memory
        memory_peak = memory_start

        # Run the processing
        result = service.process_symbol_fuzzy(
            symbol=symbol,
            indicator_config=indicator_config,
            fuzzy_config=fuzzy_config,
            timeframes=timeframes,
            data_period_days=data_period_days,
        )

        # Record final state
        end_time = time.time()
        memory_end = process.memory_info().rss / 1024 / 1024  # MB
        cpu_end = process.cpu_percent()

        # Update peak memory (rough approximation)
        memory_peak = max(memory_start, memory_end)

        # Extract timing information from result
        total_time = end_time - start_time
        indicator_time = result.processing_metadata.get("indicator_processing_time", 0)
        fuzzy_time = result.processing_metadata.get("fuzzy_processing_time", 0)

        # Count fuzzy values and timeframes
        fuzzy_values_count = len(result.fuzzy_result.fuzzy_values)
        timeframes_processed = len(result.fuzzy_result.timeframe_results)

        return PerformanceMetrics(
            total_time=total_time,
            indicator_time=indicator_time,
            fuzzy_time=fuzzy_time,
            memory_peak_mb=memory_peak,
            memory_start_mb=memory_start,
            memory_end_mb=memory_end,
            fuzzy_values_count=fuzzy_values_count,
            timeframes_processed=timeframes_processed,
            cpu_usage_percent=(cpu_start + cpu_end) / 2,
        )

    def _average_metrics(
        self, metrics_list: list[PerformanceMetrics]
    ) -> PerformanceMetrics:
        """Average multiple performance metrics."""
        if not metrics_list:
            return PerformanceMetrics()

        n = len(metrics_list)

        return PerformanceMetrics(
            total_time=sum(m.total_time for m in metrics_list) / n,
            indicator_time=sum(m.indicator_time for m in metrics_list) / n,
            fuzzy_time=sum(m.fuzzy_time for m in metrics_list) / n,
            memory_peak_mb=sum(m.memory_peak_mb for m in metrics_list) / n,
            memory_start_mb=sum(m.memory_start_mb for m in metrics_list) / n,
            memory_end_mb=sum(m.memory_end_mb for m in metrics_list) / n,
            fuzzy_values_count=int(sum(m.fuzzy_values_count for m in metrics_list) / n),
            timeframes_processed=int(
                sum(m.timeframes_processed for m in metrics_list) / n
            ),
            cpu_usage_percent=sum(m.cpu_usage_percent for m in metrics_list) / n,
        )

    def _generate_recommendations(
        self, metrics: PerformanceMetrics, config: dict[str, Any]
    ) -> list[str]:
        """Generate optimization recommendations based on metrics."""
        recommendations = []

        # Performance thresholds
        SLOW_PROCESSING_THRESHOLD = 5.0  # seconds
        HIGH_MEMORY_THRESHOLD = 500.0  # MB
        LOW_THROUGHPUT_THRESHOLD = 1.0  # FV/sec

        # Processing time analysis
        if metrics.total_time > SLOW_PROCESSING_THRESHOLD:
            recommendations.append(
                f"Processing time ({metrics.total_time:.2f}s) is high. "
                "Consider reducing data period or number of indicators."
            )

            # Analyze time distribution
            if metrics.indicator_time > metrics.fuzzy_time * 2:
                recommendations.append(
                    "Indicator calculation is the bottleneck. "
                    "Consider optimizing indicator parameters or reducing timeframes."
                )
            elif metrics.fuzzy_time > metrics.indicator_time * 2:
                recommendations.append(
                    "Fuzzy processing is the bottleneck. "
                    "Consider simplifying fuzzy sets or reducing membership functions."
                )

        # Memory usage analysis
        memory_delta = metrics.memory_peak_mb - metrics.memory_start_mb
        if memory_delta > HIGH_MEMORY_THRESHOLD:
            recommendations.append(
                f"High memory usage ({memory_delta:.1f}MB increase). "
                "Consider processing data in smaller chunks or reducing data volume."
            )

        # Throughput analysis
        if metrics.throughput_fv_per_sec < LOW_THROUGHPUT_THRESHOLD:
            recommendations.append(
                f"Low throughput ({metrics.throughput_fv_per_sec:.2f} FV/sec). "
                "Consider enabling caching or optimizing configuration."
            )

        # Configuration-specific recommendations
        timeframes_count = len(config.get("timeframes", []))
        if timeframes_count > 3:
            recommendations.append(
                f"Many timeframes ({timeframes_count}) may impact performance. "
                "Consider focusing on most important timeframes."
            )

        # Positive feedback for good performance
        if metrics.optimization_score > 80:
            recommendations.append(
                f"Excellent performance (score: {metrics.optimization_score:.1f}). "
                "Configuration is well-optimized."
            )
        elif metrics.optimization_score > 60:
            recommendations.append(
                f"Good performance (score: {metrics.optimization_score:.1f}). "
                "Minor optimizations possible."
            )

        return recommendations

    def analyze_scalability(
        self,
        service: FuzzyPipelineService,
        indicator_config: dict[str, Any],
        fuzzy_config: dict[str, Any],
        data_sizes: Optional[list[int]] = None,
        symbol: str = "AAPL",
    ) -> dict[str, Any]:
        """
        Analyze how performance scales with data size.

        Args:
            service: FuzzyPipelineService instance
            indicator_config: Indicator configuration
            fuzzy_config: Fuzzy configuration
            data_sizes: List of data period days to test
            symbol: Symbol to test with

        Returns:
            Scalability analysis results
        """
        if data_sizes is None:
            data_sizes = [10, 30, 90, 180, 365]
        logger.info(f"Analyzing scalability across {len(data_sizes)} data sizes")

        scalability_data = []

        for data_days in data_sizes:
            logger.debug(f"Testing with {data_days} days of data")

            try:
                metrics = self._measure_single_run(
                    service, symbol, indicator_config, fuzzy_config, None, data_days
                )

                scalability_data.append(
                    {
                        "data_days": data_days,
                        "total_time": metrics.total_time,
                        "memory_usage": metrics.memory_peak_mb
                        - metrics.memory_start_mb,
                        "fuzzy_values": metrics.fuzzy_values_count,
                        "throughput": metrics.throughput_fv_per_sec,
                    }
                )

            except Exception as e:
                logger.error(f"Scalability test failed for {data_days} days: {e}")

        if len(scalability_data) < 2:
            return {"error": "Insufficient data for scalability analysis"}

        # Analyze trends
        df = pd.DataFrame(scalability_data)

        # Calculate growth rates
        time_growth_rate = self._calculate_growth_rate(
            df["data_days"], df["total_time"]
        )
        memory_growth_rate = self._calculate_growth_rate(
            df["data_days"], df["memory_usage"]
        )

        # Determine scalability characteristics
        scalability_rating = "excellent"
        if time_growth_rate > 2.0:  # More than quadratic growth
            scalability_rating = "poor"
        elif time_growth_rate > 1.5:  # Between linear and quadratic
            scalability_rating = "moderate"
        elif time_growth_rate > 1.0:  # Linear growth
            scalability_rating = "good"

        return {
            "scalability_rating": scalability_rating,
            "time_growth_rate": time_growth_rate,
            "memory_growth_rate": memory_growth_rate,
            "data_points": scalability_data,
            "recommendations": self._generate_scalability_recommendations(
                time_growth_rate, memory_growth_rate
            ),
        }

    def _calculate_growth_rate(self, x_values: pd.Series, y_values: pd.Series) -> float:
        """Calculate growth rate using linear regression in log space."""
        if len(x_values) < 2:
            return 1.0

        # Use log-log regression to find power law relationship
        log_x = np.log(x_values)
        log_y = np.log(y_values + 1e-10)  # Avoid log(0)

        # Linear regression: log(y) = slope * log(x) + intercept
        slope, intercept = np.polyfit(log_x, log_y, 1)

        return slope

    def _generate_scalability_recommendations(
        self, time_growth_rate: float, memory_growth_rate: float
    ) -> list[str]:
        """Generate recommendations based on scalability analysis."""
        recommendations = []

        if time_growth_rate > 2.0:
            recommendations.append(
                "Time complexity is worse than quadratic. "
                "Consider implementing data streaming or chunked processing."
            )
        elif time_growth_rate > 1.5:
            recommendations.append(
                "Time complexity is high. "
                "Consider optimizing indicator calculations or fuzzy processing."
            )

        if memory_growth_rate > 1.5:
            recommendations.append(
                "Memory usage grows rapidly with data size. "
                "Consider implementing incremental processing or data cleanup."
            )

        if time_growth_rate <= 1.2 and memory_growth_rate <= 1.2:
            recommendations.append(
                "Excellent scalability characteristics. "
                "System should handle large datasets well."
            )

        return recommendations

    def generate_performance_report(
        self, output_file: Optional[Path] = None
    ) -> dict[str, Any]:
        """
        Generate comprehensive performance report.

        Args:
            output_file: Optional file to save the report

        Returns:
            Performance report dictionary
        """
        if not self.benchmark_results:
            return {"error": "No benchmark results available"}

        # Calculate summary statistics
        all_scores = [r.metrics.optimization_score for r in self.benchmark_results]
        all_times = [r.metrics.total_time for r in self.benchmark_results]
        all_throughputs = [
            r.metrics.throughput_fv_per_sec for r in self.benchmark_results
        ]

        report: dict[str, Any] = {
            "summary": {
                "total_benchmarks": len(self.benchmark_results),
                "avg_optimization_score": np.mean(all_scores),
                "best_optimization_score": np.max(all_scores),
                "avg_processing_time": np.mean(all_times),
                "fastest_processing_time": np.min(all_times),
                "avg_throughput": np.mean(all_throughputs),
                "best_throughput": np.max(all_throughputs),
            },
            "benchmark_results": [],
            "top_performers": [],
            "optimization_opportunities": [],
        }

        # Add detailed results
        for result in self.benchmark_results:
            report["benchmark_results"].append(
                {
                    "test_name": result.test_name,
                    "optimization_score": result.metrics.optimization_score,
                    "total_time": result.metrics.total_time,
                    "fuzzy_values_count": result.metrics.fuzzy_values_count,
                    "throughput": result.metrics.throughput_fv_per_sec,
                    "memory_usage": result.metrics.memory_peak_mb
                    - result.metrics.memory_start_mb,
                    "recommendations": result.recommendations,
                }
            )

        # Identify top performers
        sorted_results = sorted(
            self.benchmark_results,
            key=lambda r: r.metrics.optimization_score,
            reverse=True,
        )

        report["top_performers"] = [
            {
                "test_name": r.test_name,
                "score": r.metrics.optimization_score,
                "time": r.metrics.total_time,
                "config_summary": self._summarize_config(r.configuration),
            }
            for r in sorted_results[:3]
        ]

        # Aggregate optimization opportunities
        all_recommendations = []
        for result in self.benchmark_results:
            all_recommendations.extend(result.recommendations)

        # Count common recommendations
        recommendation_counts: dict[str, int] = {}
        for rec in all_recommendations:
            key = rec.split(".")[0]  # Use first sentence as key
            recommendation_counts[key] = recommendation_counts.get(key, 0) + 1

        report["optimization_opportunities"] = [
            {"recommendation": rec, "frequency": count}
            for rec, count in sorted(
                recommendation_counts.items(), key=lambda x: x[1], reverse=True
            )
        ][:5]

        # Save to file if requested
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Performance report saved to {output_file}")

        return report

    def _summarize_config(self, config: dict[str, Any]) -> str:
        """Create a brief summary of a configuration."""
        summary_parts = []

        if "timeframes" in config:
            timeframes = (
                list(config["timeframes"].keys())
                if isinstance(config["timeframes"], dict)
                else config["timeframes"]
            )
            if timeframes:
                summary_parts.append(f"TF: {','.join(timeframes)}")

        if "indicator_config" in config:
            ind_config = config["indicator_config"]
            if "timeframes" in ind_config:
                total_indicators = sum(
                    len(tf_config.get("indicators", []))
                    for tf_config in ind_config["timeframes"].values()
                    if isinstance(tf_config, dict)
                )
                summary_parts.append(f"Indicators: {total_indicators}")

        return " | ".join(summary_parts) if summary_parts else "Custom config"


def create_performance_analyzer(**kwargs) -> FuzzyPerformanceAnalyzer:
    """
    Factory function to create a performance analyzer.

    Args:
        **kwargs: Configuration options for the analyzer

    Returns:
        Configured FuzzyPerformanceAnalyzer instance
    """
    return FuzzyPerformanceAnalyzer(**kwargs)
