"""Performance optimizations for multi-timeframe indicator processing.

This module provides optimized processing methods for large datasets and
high-frequency scenarios.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Callable, Any
from dataclasses import dataclass
from functools import lru_cache
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ktrdr import get_logger
from ktrdr.indicators.multi_timeframe_indicator_engine import (
    MultiTimeframeIndicatorEngine,
)
from ktrdr.indicators.indicator_engine import IndicatorEngine

logger = get_logger(__name__)


@dataclass
class ProcessingMetrics:
    """Metrics for processing performance."""

    total_time: float
    rows_processed: int
    indicators_computed: int
    throughput_rows_per_second: float
    memory_usage_mb: Optional[float] = None


class ChunkedProcessor:
    """Optimized processor for large datasets using chunking."""

    def __init__(self, chunk_size: int = 1000, overlap_size: int = 50):
        """
        Initialize chunked processor.

        Args:
            chunk_size: Number of rows to process per chunk
            overlap_size: Number of rows to overlap between chunks for indicator continuity
        """
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.logger = get_logger(__name__)

    def process_timeframe_chunked(
        self, data: pd.DataFrame, engine: IndicatorEngine, timeframe: str
    ) -> pd.DataFrame:
        """
        Process a single timeframe in chunks to manage memory usage.

        Args:
            data: DataFrame to process
            engine: IndicatorEngine for this timeframe
            timeframe: Timeframe identifier

        Returns:
            Processed DataFrame with indicators
        """
        if len(data) <= self.chunk_size:
            # Small dataset, process normally
            return engine.apply(data)

        results = []
        total_chunks = (len(data) + self.chunk_size - 1) // self.chunk_size

        self.logger.info(
            f"Processing {len(data)} rows in {total_chunks} chunks for {timeframe}"
        )

        for i in range(0, len(data), self.chunk_size):
            chunk_start = max(0, i - self.overlap_size) if i > 0 else 0
            chunk_end = min(len(data), i + self.chunk_size)

            # Get chunk with overlap
            chunk = data.iloc[chunk_start:chunk_end].copy()

            # Process chunk
            processed_chunk = engine.apply(chunk)

            # Remove overlap from result (except for first chunk)
            if i > 0 and len(processed_chunk) > self.overlap_size:
                # Remove overlap rows
                overlap_to_remove = i - chunk_start
                processed_chunk = processed_chunk.iloc[overlap_to_remove:]

            results.append(processed_chunk)

            # Log progress for large datasets
            if (
                total_chunks > 10
                and (i // self.chunk_size + 1) % (total_chunks // 10) == 0
            ):
                progress = ((i // self.chunk_size + 1) / total_chunks) * 100
                self.logger.debug(
                    f"Progress: {progress:.0f}% ({i // self.chunk_size + 1}/{total_chunks})"
                )

        # Combine all chunks
        if results:
            return pd.concat(results, ignore_index=True)
        else:
            return pd.DataFrame()

    def process_multi_timeframe_chunked(
        self, data: Dict[str, pd.DataFrame], engine: MultiTimeframeIndicatorEngine
    ) -> Dict[str, pd.DataFrame]:
        """
        Process multi-timeframe data using chunked processing.

        Args:
            data: Dictionary of timeframe data
            engine: MultiTimeframeIndicatorEngine

        Returns:
            Dictionary of processed timeframe data
        """
        results = {}

        for timeframe, df in data.items():
            if timeframe in engine.engines:
                timeframe_engine = engine.engines[timeframe]
                results[timeframe] = self.process_timeframe_chunked(
                    df, timeframe_engine, timeframe
                )
            else:
                self.logger.warning(f"No engine configured for timeframe {timeframe}")

        return results


class ParallelProcessor:
    """Processor that handles different timeframes in parallel."""

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize parallel processor.

        Args:
            max_workers: Maximum number of worker threads (None for default)
        """
        self.max_workers = max_workers
        self.logger = get_logger(__name__)

    def process_timeframe_parallel(
        self, timeframe: str, data: pd.DataFrame, engine: IndicatorEngine
    ) -> tuple[str, pd.DataFrame]:
        """
        Process a single timeframe (for parallel execution).

        Args:
            timeframe: Timeframe identifier
            data: DataFrame to process
            engine: IndicatorEngine for this timeframe

        Returns:
            Tuple of (timeframe, processed_data)
        """
        try:
            start_time = time.time()
            result = engine.apply(data)
            processing_time = time.time() - start_time

            self.logger.debug(
                f"Processed {timeframe}: {len(data)} rows in {processing_time:.2f}s"
            )
            return timeframe, result

        except Exception as e:
            self.logger.error(f"Error processing timeframe {timeframe}: {e}")
            raise

    def process_multi_timeframe_parallel(
        self, data: Dict[str, pd.DataFrame], engine: MultiTimeframeIndicatorEngine
    ) -> Dict[str, pd.DataFrame]:
        """
        Process multiple timeframes in parallel.

        Args:
            data: Dictionary of timeframe data
            engine: MultiTimeframeIndicatorEngine

        Returns:
            Dictionary of processed timeframe data
        """
        if len(data) <= 1:
            # Single timeframe, no need for parallelization
            return engine.apply_multi_timeframe(data)

        results = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all timeframe processing tasks
            futures = {}

            for timeframe, df in data.items():
                if timeframe in engine.engines:
                    future = executor.submit(
                        self.process_timeframe_parallel,
                        timeframe,
                        df,
                        engine.engines[timeframe],
                    )
                    futures[future] = timeframe
                else:
                    self.logger.warning(
                        f"No engine configured for timeframe {timeframe}"
                    )

            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    timeframe, result = future.result()

                    # Apply column standardization
                    standardized_result = engine._standardize_column_names(
                        result, timeframe, data[timeframe].columns.tolist()
                    )
                    results[timeframe] = standardized_result

                except Exception as e:
                    failed_timeframe = futures[future]
                    self.logger.error(
                        f"Failed to process timeframe {failed_timeframe}: {e}"
                    )
                    raise

        self.logger.info(f"Processed {len(results)} timeframes in parallel")
        return results


class IncrementalProcessor:
    """Optimized processor for incremental/streaming data updates."""

    def __init__(self, lookback_window: int = 200):
        """
        Initialize incremental processor.

        Args:
            lookback_window: Number of historical rows to maintain for indicator computation
        """
        self.lookback_window = lookback_window
        self.cached_data: Dict[str, pd.DataFrame] = {}
        self.cached_results: Dict[str, pd.DataFrame] = {}
        self.logger = get_logger(__name__)

    def update_incremental(
        self, new_data: Dict[str, pd.DataFrame], engine: MultiTimeframeIndicatorEngine
    ) -> Dict[str, pd.DataFrame]:
        """
        Process incremental data updates efficiently.

        Args:
            new_data: Dictionary of new data for each timeframe
            engine: MultiTimeframeIndicatorEngine

        Returns:
            Dictionary of updated results (only new/changed rows)
        """
        incremental_results = {}

        for timeframe, new_df in new_data.items():
            if timeframe not in engine.engines:
                continue

            # Combine with cached data
            if timeframe in self.cached_data:
                # Append new data to cached data
                combined_data = pd.concat(
                    [self.cached_data[timeframe], new_df], ignore_index=True
                )

                # Keep only lookback window
                if len(combined_data) > self.lookback_window:
                    combined_data = combined_data.tail(self.lookback_window)
            else:
                combined_data = new_df

            # Process combined data
            full_result = engine.engines[timeframe].apply(combined_data)

            # Apply column standardization
            standardized_result = engine._standardize_column_names(
                full_result, timeframe, combined_data.columns.tolist()
            )

            # Determine which rows are new
            if timeframe in self.cached_results:
                # Only return new rows
                cached_len = len(self.cached_results[timeframe])
                new_rows = standardized_result.tail(len(new_df))
                incremental_results[timeframe] = new_rows
            else:
                # All rows are new
                incremental_results[timeframe] = standardized_result

            # Update cache
            self.cached_data[timeframe] = combined_data
            self.cached_results[timeframe] = standardized_result

        return incremental_results

    def clear_cache(self):
        """Clear cached data and results."""
        self.cached_data.clear()
        self.cached_results.clear()
        self.logger.debug("Incremental processor cache cleared")


class OptimizedMultiTimeframeEngine:
    """High-performance multi-timeframe indicator engine with optimizations."""

    def __init__(
        self,
        base_engine: MultiTimeframeIndicatorEngine,
        enable_chunking: bool = True,
        enable_parallel: bool = True,
        chunk_size: int = 1000,
        max_workers: Optional[int] = None,
    ):
        """
        Initialize optimized engine.

        Args:
            base_engine: Base MultiTimeframeIndicatorEngine
            enable_chunking: Whether to use chunked processing for large datasets
            enable_parallel: Whether to use parallel processing for multiple timeframes
            chunk_size: Size of chunks for chunked processing
            max_workers: Maximum number of worker threads for parallel processing
        """
        self.base_engine = base_engine
        self.enable_chunking = enable_chunking
        self.enable_parallel = enable_parallel

        # Initialize processors
        self.chunked_processor = (
            ChunkedProcessor(chunk_size=chunk_size) if enable_chunking else None
        )
        self.parallel_processor = (
            ParallelProcessor(max_workers=max_workers) if enable_parallel else None
        )
        self.incremental_processor = IncrementalProcessor()

        self.logger = get_logger(__name__)

    def apply_multi_timeframe_optimized(
        self,
        data: Dict[str, pd.DataFrame],
        force_chunking: bool = False,
        force_parallel: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """
        Apply indicators with automatic optimization selection.

        Args:
            data: Dictionary of timeframe data
            force_chunking: Force chunked processing regardless of data size
            force_parallel: Force parallel processing regardless of timeframe count

        Returns:
            Dictionary of processed timeframe data
        """
        start_time = time.time()
        total_rows = sum(len(df) for df in data.values())

        self.logger.info(
            f"Processing {total_rows} total rows across {len(data)} timeframes"
        )

        # Determine processing strategy
        use_chunking = force_chunking or (self.enable_chunking and total_rows > 10000)

        use_parallel = force_parallel or (
            self.enable_parallel and len(data) > 1 and total_rows > 1000
        )

        # Apply processing strategy
        if use_chunking and use_parallel:
            self.logger.info("Using chunked + parallel processing")
            results = self._process_chunked_parallel(data)
        elif use_chunking:
            self.logger.info("Using chunked processing")
            results = self.chunked_processor.process_multi_timeframe_chunked(
                data, self.base_engine
            )
        elif use_parallel:
            self.logger.info("Using parallel processing")
            results = self.parallel_processor.process_multi_timeframe_parallel(
                data, self.base_engine
            )
        else:
            self.logger.info("Using standard processing")
            results = self.base_engine.apply_multi_timeframe(data)

        processing_time = time.time() - start_time
        throughput = total_rows / processing_time if processing_time > 0 else 0

        self.logger.info(
            f"Completed processing in {processing_time:.2f}s "
            f"({throughput:.0f} rows/sec)"
        )

        return results

    def _process_chunked_parallel(
        self, data: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """Process data using both chunking and parallel processing."""

        # Process each timeframe in parallel, using chunking within each timeframe
        def process_timeframe_chunked_parallel(
            timeframe: str, df: pd.DataFrame
        ) -> tuple[str, pd.DataFrame]:
            if timeframe in self.base_engine.engines:
                engine = self.base_engine.engines[timeframe]
                result = self.chunked_processor.process_timeframe_chunked(
                    df, engine, timeframe
                )

                # Apply standardization
                standardized = self.base_engine._standardize_column_names(
                    result, timeframe, df.columns.tolist()
                )
                return timeframe, standardized
            else:
                return timeframe, pd.DataFrame()

        results = {}

        with ThreadPoolExecutor(
            max_workers=self.parallel_processor.max_workers
        ) as executor:
            futures = {
                executor.submit(process_timeframe_chunked_parallel, tf, df): tf
                for tf, df in data.items()
            }

            for future in as_completed(futures):
                timeframe, result = future.result()
                if not result.empty:
                    results[timeframe] = result

        return results

    def apply_incremental(
        self, new_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """
        Apply indicators to incremental data updates.

        Args:
            new_data: Dictionary of new data for each timeframe

        Returns:
            Dictionary of incremental results
        """
        return self.incremental_processor.update_incremental(new_data, self.base_engine)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics and recommendations."""
        metrics = {
            "optimizations_enabled": {
                "chunking": self.enable_chunking,
                "parallel": self.enable_parallel,
            },
            "processors": {
                "chunked": self.chunked_processor is not None,
                "parallel": self.parallel_processor is not None,
                "incremental": self.incremental_processor is not None,
            },
        }

        if self.chunked_processor:
            metrics["chunk_size"] = self.chunked_processor.chunk_size
            metrics["overlap_size"] = self.chunked_processor.overlap_size

        if self.parallel_processor:
            metrics["max_workers"] = self.parallel_processor.max_workers

        return metrics


@lru_cache(maxsize=128)
def _cached_indicator_computation(
    indicator_type: str, parameters: tuple, data_hash: int
) -> Any:
    """
    Cache indicator computations to avoid redundant calculations.

    Note: This is a placeholder for more sophisticated caching.
    In practice, you'd need to implement proper hashing of data
    and more complex cache management.
    """
    # This would contain the actual caching logic
    pass


def create_optimized_engine(
    base_engine: MultiTimeframeIndicatorEngine, optimization_level: str = "auto"
) -> OptimizedMultiTimeframeEngine:
    """
    Create an optimized multi-timeframe engine with recommended settings.

    Args:
        base_engine: Base MultiTimeframeIndicatorEngine
        optimization_level: "minimal", "balanced", "maximum", or "auto"

    Returns:
        OptimizedMultiTimeframeEngine with appropriate settings
    """

    if optimization_level == "minimal":
        return OptimizedMultiTimeframeEngine(
            base_engine, enable_chunking=False, enable_parallel=False
        )
    elif optimization_level == "balanced":
        return OptimizedMultiTimeframeEngine(
            base_engine,
            enable_chunking=True,
            enable_parallel=True,
            chunk_size=1000,
            max_workers=2,
        )
    elif optimization_level == "maximum":
        return OptimizedMultiTimeframeEngine(
            base_engine,
            enable_chunking=True,
            enable_parallel=True,
            chunk_size=500,
            max_workers=None,  # Use all available cores
        )
    else:  # auto
        # Auto-detect based on system capabilities
        import os

        cpu_count = os.cpu_count() or 1

        return OptimizedMultiTimeframeEngine(
            base_engine,
            enable_chunking=True,
            enable_parallel=cpu_count > 1,
            chunk_size=1000,
            max_workers=min(4, cpu_count),  # Reasonable default
        )
