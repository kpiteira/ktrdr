"""
Service layer for multi-timeframe fuzzy processing pipeline.

This service provides a high-level interface for integrating multi-timeframe
fuzzy logic processing into the KTRDR trading system. It handles configuration
loading, data management, and result processing.
"""

from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
import yaml  # type: ignore[import-untyped]

from ktrdr import get_logger
from ktrdr.data.data_manager import DataManager
from ktrdr.errors import ConfigurationError, DataError, ProcessingError
from ktrdr.fuzzy.indicator_integration import (
    IntegratedFuzzyResult,
    MultiTimeframeFuzzyIndicatorPipeline,
    create_integrated_pipeline,
)

# Set up module-level logger
logger = get_logger(__name__)


class FuzzyPipelineService:
    """
    High-level service for multi-timeframe fuzzy processing.

    This service provides a clean interface for the trading system to perform
    multi-timeframe fuzzy analysis. It handles all the coordination between
    data loading, indicator calculation, and fuzzy processing.
    """

    def __init__(
        self,
        data_manager: Optional[DataManager] = None,
        enable_caching: bool = True,
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize the fuzzy pipeline service.

        Args:
            data_manager: Optional DataManager instance (will create if not provided)
            enable_caching: Enable result caching for performance
            cache_ttl_seconds: Cache time-to-live in seconds
        """
        self.data_manager = data_manager or DataManager()
        self.enable_caching = enable_caching
        self.cache_ttl_seconds = cache_ttl_seconds
        self._pipeline_cache: dict[str, Any] = {}
        self._result_cache: dict[str, Any] = {}

        logger.info("Initialized FuzzyPipelineService")

    def process_symbol_fuzzy(
        self,
        symbol: str,
        indicator_config: Union[dict[str, Any], str, Path],
        fuzzy_config: Union[dict[str, Any], str, Path],
        timeframes: Optional[list[str]] = None,
        data_period_days: int = 30,
        fail_fast: bool = False,
    ) -> IntegratedFuzzyResult:
        """
        Process fuzzy analysis for a symbol across multiple timeframes.

        Args:
            symbol: Trading symbol (e.g., "AAPL")
            indicator_config: Indicator configuration (dict, file path, or config object)
            fuzzy_config: Fuzzy configuration (dict, file path, or config object)
            timeframes: Optional list of timeframes to process
            data_period_days: Number of days of historical data to load
            fail_fast: If True, fail immediately on first error

        Returns:
            IntegratedFuzzyResult with complete processing results

        Raises:
            ProcessingError: If processing fails and fail_fast is True
        """
        logger.info(f"Processing fuzzy analysis for symbol: {symbol}")

        try:
            # Load and validate configurations
            indicator_config_dict = self._load_configuration(
                indicator_config, "indicator"
            )
            fuzzy_config_dict = self._load_configuration(fuzzy_config, "fuzzy")

            # Get or create pipeline
            pipeline = self._get_or_create_pipeline(
                indicator_config_dict, fuzzy_config_dict
            )

            # Load market data for all required timeframes
            required_timeframes = timeframes or pipeline.get_supported_timeframes()
            market_data = self._load_market_data(
                symbol, required_timeframes, data_period_days
            )

            # Process through pipeline
            result = pipeline.process_market_data(
                market_data=market_data,
                timeframe_filter=timeframes,
                fail_fast=fail_fast,
            )

            # Add service-level metadata
            result.processing_metadata.update(
                {
                    "symbol": symbol,
                    "service_version": "1.0.0",
                    "data_period_days": data_period_days,
                    "requested_timeframes": timeframes,
                    "actual_timeframes": list(market_data.keys()),
                }
            )

            logger.info(
                f"Completed fuzzy analysis for {symbol}: {len(result.fuzzy_result.fuzzy_values)} fuzzy values"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to process fuzzy analysis for {symbol}: {e}")
            raise ProcessingError(
                message=f"Fuzzy analysis failed for symbol {symbol}",
                error_code="SERVICE-FuzzyProcessingFailed",
                details={"symbol": symbol, "original_error": str(e)},
            ) from e

    def process_multiple_symbols(
        self,
        symbols: list[str],
        indicator_config: Union[dict[str, Any], str, Path],
        fuzzy_config: Union[dict[str, Any], str, Path],
        timeframes: Optional[list[str]] = None,
        data_period_days: int = 30,
        continue_on_error: bool = True,
    ) -> dict[str, IntegratedFuzzyResult]:
        """
        Process fuzzy analysis for multiple symbols.

        Args:
            symbols: List of trading symbols
            indicator_config: Indicator configuration
            fuzzy_config: Fuzzy configuration
            timeframes: Optional list of timeframes to process
            data_period_days: Number of days of historical data to load
            continue_on_error: Continue processing other symbols if one fails

        Returns:
            Dictionary mapping symbol to IntegratedFuzzyResult
        """
        logger.info(f"Processing fuzzy analysis for {len(symbols)} symbols")

        results = {}
        errors = []

        for symbol in symbols:
            try:
                result = self.process_symbol_fuzzy(
                    symbol=symbol,
                    indicator_config=indicator_config,
                    fuzzy_config=fuzzy_config,
                    timeframes=timeframes,
                    data_period_days=data_period_days,
                    fail_fast=not continue_on_error,
                )
                results[symbol] = result

            except Exception as e:
                error_msg = f"Failed to process {symbol}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

                if not continue_on_error:
                    raise ProcessingError(
                        message=f"Multi-symbol processing failed at symbol {symbol}",
                        error_code="SERVICE-MultiSymbolFailed",
                        details={
                            "failed_symbol": symbol,
                            "processed_symbols": list(results.keys()),
                            "original_error": str(e),
                        },
                    ) from e

        if errors:
            logger.warning(f"Completed with {len(errors)} errors: {errors}")

        logger.info(f"Processed {len(results)}/{len(symbols)} symbols successfully")
        return results

    def create_fuzzy_summary_report(
        self,
        results: Union[IntegratedFuzzyResult, dict[str, IntegratedFuzzyResult]],
        include_performance_metrics: bool = True,
    ) -> dict[str, Any]:
        """
        Create a summary report from fuzzy processing results.

        Args:
            results: Single result or dictionary of results by symbol
            include_performance_metrics: Include performance timing information

        Returns:
            Summary report dictionary
        """
        if isinstance(results, IntegratedFuzzyResult):
            # Single result
            return self._create_single_symbol_report(
                results, include_performance_metrics
            )
        else:
            # Multiple results
            return self._create_multi_symbol_report(
                results, include_performance_metrics
            )

    def _load_configuration(
        self, config: Union[dict[str, Any], str, Path], config_type: str
    ) -> dict[str, Any]:
        """Load and validate configuration from various sources."""
        if isinstance(config, dict):
            return config

        elif isinstance(config, (str, Path)):
            config_path = Path(config)
            if not config_path.exists():
                raise ConfigurationError(
                    message=f"{config_type} configuration file not found",
                    error_code="SERVICE-ConfigFileNotFound",
                    details={"file_path": str(config_path)},
                )

            try:
                with open(config_path) as f:
                    return yaml.safe_load(f)
            except Exception as e:
                raise ConfigurationError(
                    message=f"Failed to load {config_type} configuration",
                    error_code="SERVICE-ConfigLoadFailed",
                    details={"file_path": str(config_path), "original_error": str(e)},
                ) from e

        else:
            raise ConfigurationError(
                message=f"Invalid {config_type} configuration type",
                error_code="SERVICE-InvalidConfigType",
                details={"config_type": type(config).__name__},
            )

    def _get_or_create_pipeline(
        self, indicator_config: dict[str, Any], fuzzy_config: dict[str, Any]
    ) -> MultiTimeframeFuzzyIndicatorPipeline:
        """Get existing pipeline from cache or create new one."""
        # Create cache key from configuration hashes
        cache_key = f"{hash(str(indicator_config))}_{hash(str(fuzzy_config))}"

        if self.enable_caching and cache_key in self._pipeline_cache:
            logger.debug("Using cached pipeline")
            return self._pipeline_cache[cache_key]

        # Create new pipeline
        logger.debug("Creating new pipeline")
        pipeline = create_integrated_pipeline(
            indicator_config=indicator_config,
            fuzzy_config=fuzzy_config,
            enable_error_recovery=True,
            enable_performance_monitoring=True,
        )

        if self.enable_caching:
            self._pipeline_cache[cache_key] = pipeline

        return pipeline

    def _load_market_data(
        self, symbol: str, timeframes: list[str], period_days: int
    ) -> dict[str, pd.DataFrame]:
        """Load market data for all required timeframes."""
        market_data = {}

        for timeframe in timeframes:
            try:
                # Use data manager to load data
                data = self.data_manager.load_data(
                    symbol=symbol, timeframe=timeframe
                )

                if data is not None and not data.empty:
                    market_data[timeframe] = data
                    logger.debug(f"Loaded {len(data)} rows for {symbol} {timeframe}")
                else:
                    logger.warning(f"No data available for {symbol} {timeframe}")

            except Exception as e:
                logger.error(f"Failed to load data for {symbol} {timeframe}: {e}")
                # Continue with other timeframes unless critical

        if not market_data:
            raise DataError(
                message=f"No market data available for symbol {symbol}",
                error_code="SERVICE-NoMarketData",
                details={
                    "symbol": symbol,
                    "requested_timeframes": timeframes,
                    "period_days": period_days,
                },
            )

        return market_data

    def _create_single_symbol_report(
        self, result: IntegratedFuzzyResult, include_performance: bool
    ) -> dict[str, Any]:
        """Create summary report for single symbol result."""
        fuzzy_values = result.fuzzy_result.fuzzy_values

        report: dict[str, Any] = {
            "summary": {
                "total_fuzzy_values": len(fuzzy_values),
                "processed_timeframes": len(result.fuzzy_result.timeframe_results),
                "success": len(result.errors) == 0,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
            },
            "timeframe_breakdown": {},
            "top_fuzzy_values": {},
        }

        # Timeframe breakdown
        for timeframe, tf_result in result.fuzzy_result.timeframe_results.items():
            report["timeframe_breakdown"][timeframe] = {
                "fuzzy_value_count": len(tf_result),
                "indicators": list({key.split("_")[0] for key in tf_result.keys()}),
            }

        # Top fuzzy values (sorted by value)
        if fuzzy_values:
            # Filter to only numeric values for sorting
            numeric_values = {
                k: float(v) for k, v in fuzzy_values.items() 
                if isinstance(v, (int, float))
            }
            if numeric_values:
                sorted_values = sorted(
                    numeric_values.items(), key=lambda x: x[1], reverse=True
                )
                report["top_fuzzy_values"] = dict(sorted_values[:10])

        # Performance metrics
        if include_performance and result.processing_metadata:
            report["performance"] = {
                "total_time": result.total_processing_time,
                "indicator_time": result.processing_metadata.get(
                    "indicator_processing_time", 0
                ),
                "fuzzy_time": result.processing_metadata.get(
                    "fuzzy_processing_time", 0
                ),
            }

        # Errors and warnings
        if result.errors:
            report["errors"] = result.errors
        if result.warnings:
            report["warnings"] = result.warnings

        return report

    def _create_multi_symbol_report(
        self, results: dict[str, IntegratedFuzzyResult], include_performance: bool
    ) -> dict[str, Any]:
        """Create summary report for multiple symbol results."""
        total_symbols = len(results)
        successful_symbols = sum(1 for r in results.values() if len(r.errors) == 0)

        report = {
            "summary": {
                "total_symbols": total_symbols,
                "successful_symbols": successful_symbols,
                "failed_symbols": total_symbols - successful_symbols,
                "success_rate": (
                    successful_symbols / total_symbols if total_symbols > 0 else 0
                ),
            },
            "symbol_results": {},
            "aggregated_metrics": {},
        }

        # Individual symbol summaries
        for symbol, result in results.items():
            report["symbol_results"][symbol] = self._create_single_symbol_report(
                result, include_performance=False
            )

        # Aggregated metrics
        if results:
            all_fuzzy_counts = [
                len(r.fuzzy_result.fuzzy_values) for r in results.values()
            ]
            all_processing_times = [r.total_processing_time for r in results.values()]

            report["aggregated_metrics"] = {
                "avg_fuzzy_values_per_symbol": sum(all_fuzzy_counts)
                / len(all_fuzzy_counts),
                "total_fuzzy_values": sum(all_fuzzy_counts),
                "avg_processing_time": sum(all_processing_times)
                / len(all_processing_times),
                "total_processing_time": sum(all_processing_times),
            }

        return report

    def get_service_health(self) -> dict[str, Any]:
        """Get service health and status information."""
        return {
            "data_manager": {
                "initialized": self.data_manager is not None,
                "type": type(self.data_manager).__name__,
            },
            "caching": {
                "enabled": self.enable_caching,
                "pipeline_cache_size": len(self._pipeline_cache),
                "result_cache_size": len(self._result_cache),
                "cache_ttl_seconds": self.cache_ttl_seconds,
            },
            "status": "healthy",
        }


def create_fuzzy_pipeline_service(**kwargs) -> FuzzyPipelineService:
    """
    Factory function to create a fuzzy pipeline service.

    Args:
        **kwargs: Configuration options for the service

    Returns:
        Configured FuzzyPipelineService instance
    """
    return FuzzyPipelineService(**kwargs)
