"""
Multi-timeframe fuzzy-indicator integration pipeline.

This module provides the complete integration between the MultiTimeframeIndicatorEngine
and MultiTimeframeFuzzyEngine, enabling end-to-end processing from raw market data
to fuzzy logical outputs across multiple timeframes.
"""

from typing import Dict, Any, List, Optional, Union
import pandas as pd
import time
from dataclasses import dataclass, field

from ktrdr import get_logger
from ktrdr.indicators.multi_timeframe_indicator_engine import (
    MultiTimeframeIndicatorEngine,
    TimeframeIndicatorConfig,
)
from ktrdr.fuzzy.multi_timeframe_engine import (
    MultiTimeframeFuzzyEngine,
    MultiTimeframeFuzzyResult,
)
from ktrdr.errors import ProcessingError, DataValidationError, ConfigurationError

# Set up module-level logger
logger = get_logger(__name__)


@dataclass
class IntegratedFuzzyResult:
    """
    Result from integrated multi-timeframe fuzzy processing.

    Attributes:
        fuzzy_result: The fuzzy processing result
        indicator_data: The processed indicator data used for fuzzy processing
        processing_metadata: Metadata about the processing pipeline
        errors: Any errors encountered during processing
        warnings: Non-fatal warnings during processing
        total_processing_time: Total time taken for the entire pipeline
    """

    fuzzy_result: MultiTimeframeFuzzyResult
    indicator_data: Dict[str, Dict[str, float]]
    processing_metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    total_processing_time: float = 0.0


class MultiTimeframeFuzzyIndicatorPipeline:
    """
    Integrated pipeline for multi-timeframe indicator calculation and fuzzy processing.

    This class coordinates between the MultiTimeframeIndicatorEngine and
    MultiTimeframeFuzzyEngine to provide a complete processing pipeline from
    raw market data to fuzzy logical outputs.
    """

    def __init__(
        self,
        indicator_config: Dict[str, Any],
        fuzzy_config: Dict[str, Any],
        enable_error_recovery: bool = True,
        enable_performance_monitoring: bool = True,
    ):
        """
        Initialize the integrated pipeline.

        Args:
            indicator_config: Configuration for multi-timeframe indicators
            fuzzy_config: Configuration for multi-timeframe fuzzy engine
            enable_error_recovery: Enable graceful error recovery
            enable_performance_monitoring: Enable detailed performance tracking
        """
        self.enable_error_recovery = enable_error_recovery
        self.enable_performance_monitoring = enable_performance_monitoring

        logger.info("Initializing MultiTimeframeFuzzyIndicatorPipeline")

        try:
            # Initialize the indicator engine
            self.indicator_engine = self._create_indicator_engine(indicator_config)
            timeframes_count = len(indicator_config.get("timeframes", {}))
            logger.debug(
                f"Initialized indicator engine with {timeframes_count} timeframes"
            )

            # Initialize the fuzzy engine
            self.fuzzy_engine = MultiTimeframeFuzzyEngine(fuzzy_config)
            logger.debug(
                f"Initialized fuzzy engine with {len(self.fuzzy_engine.get_supported_timeframes())} timeframes"
            )

            # Validate configuration compatibility
            self._validate_configuration_compatibility()

        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            raise ConfigurationError(
                message="Failed to initialize multi-timeframe fuzzy-indicator pipeline",
                error_code="PIPELINE-InitializationFailed",
                details={"original_error": str(e)},
            ) from e

    def _validate_configuration_compatibility(self) -> None:
        """Validate that indicator and fuzzy configurations are compatible."""
        # Get timeframes from both configurations
        indicator_timeframes = set(self.indicator_engine.get_supported_timeframes())
        fuzzy_timeframes = set(self.fuzzy_engine.get_supported_timeframes())

        if not indicator_timeframes.intersection(fuzzy_timeframes):
            raise ConfigurationError(
                message="No common timeframes between indicator and fuzzy configurations",
                error_code="PIPELINE-IncompatibleTimeframes",
                details={
                    "indicator_timeframes": list(indicator_timeframes),
                    "fuzzy_timeframes": list(fuzzy_timeframes),
                },
            )

        logger.info(
            f"Validated compatibility: {len(indicator_timeframes.intersection(fuzzy_timeframes))} common timeframes"
        )

    def _create_indicator_engine(
        self, indicator_config: Dict[str, Any]
    ) -> MultiTimeframeIndicatorEngine:
        """
        Create MultiTimeframeIndicatorEngine from configuration dictionary.

        Args:
            indicator_config: Dictionary configuration for indicators

        Returns:
            Configured MultiTimeframeIndicatorEngine instance
        """
        if "timeframes" not in indicator_config:
            raise ConfigurationError(
                message="Indicator configuration missing 'timeframes' key",
                error_code="PIPELINE-MissingTimeframes",
                details={"config_keys": list(indicator_config.keys())},
            )

        timeframe_configs = []
        for timeframe, config in indicator_config["timeframes"].items():
            if not isinstance(config, dict):
                raise ConfigurationError(
                    message=f"Invalid configuration for timeframe {timeframe}",
                    error_code="PIPELINE-InvalidTimeframeConfig",
                    details={
                        "timeframe": timeframe,
                        "config_type": type(config).__name__,
                    },
                )

            indicators = config.get("indicators", [])
            enabled = config.get("enabled", True)
            weight = config.get("weight", 1.0)

            timeframe_config = TimeframeIndicatorConfig(
                timeframe=timeframe,
                indicators=indicators,
                enabled=enabled,
                weight=weight,
            )
            timeframe_configs.append(timeframe_config)

        return MultiTimeframeIndicatorEngine(timeframe_configs)

    def process_market_data(
        self,
        market_data: Dict[str, pd.DataFrame],
        timeframe_filter: Optional[List[str]] = None,
        fail_fast: bool = False,
    ) -> IntegratedFuzzyResult:
        """
        Process market data through the complete indicator-fuzzy pipeline.

        Args:
            market_data: Raw market data for multiple timeframes
            timeframe_filter: Optional list of timeframes to process
            fail_fast: If True, fail immediately on first error

        Returns:
            IntegratedFuzzyResult with complete processing results

        Raises:
            ProcessingError: If processing fails and fail_fast is True
        """
        start_time = time.time()
        errors = []
        warnings = []
        processing_metadata = {
            "start_time": start_time,
            "input_timeframes": list(market_data.keys()),
            "timeframe_filter": timeframe_filter,
        }

        logger.info(
            f"Starting integrated pipeline processing for {len(market_data)} timeframes"
        )

        try:
            # Step 1: Process indicators
            logger.debug("Step 1: Processing indicators")
            indicator_start = time.time()

            try:
                indicator_results = self.indicator_engine.apply_multi_timeframe(
                    market_data
                )
                indicator_processing_time = time.time() - indicator_start

                processing_metadata["indicator_processing_time"] = (
                    indicator_processing_time
                )
                processing_metadata["processed_indicator_timeframes"] = list(
                    indicator_results.keys()
                )

                logger.debug(
                    f"Indicator processing completed in {indicator_processing_time:.3f}s"
                )

            except Exception as e:
                error_msg = f"Indicator processing failed: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

                if fail_fast or not self.enable_error_recovery:
                    raise ProcessingError(
                        message="Indicator processing failed in pipeline",
                        error_code="PIPELINE-IndicatorFailed",
                        details={"original_error": str(e)},
                    ) from e

                # Return minimal result with error
                return IntegratedFuzzyResult(
                    fuzzy_result=MultiTimeframeFuzzyResult({}, {}, {}, errors, 0.0),
                    indicator_data={},
                    processing_metadata=processing_metadata,
                    errors=errors,
                    warnings=warnings,
                    total_processing_time=time.time() - start_time,
                )

            # Step 2: Convert indicators to fuzzy input format
            logger.debug("Step 2: Converting indicators to fuzzy input format")

            try:
                fuzzy_input_data = self._convert_indicators_to_fuzzy_input(
                    indicator_results, timeframe_filter
                )
                processing_metadata["fuzzy_input_timeframes"] = list(
                    fuzzy_input_data.keys()
                )

            except Exception as e:
                error_msg = f"Indicator-to-fuzzy conversion failed: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

                if fail_fast or not self.enable_error_recovery:
                    raise ProcessingError(
                        message="Indicator-to-fuzzy conversion failed",
                        error_code="PIPELINE-ConversionFailed",
                        details={"original_error": str(e)},
                    ) from e

                fuzzy_input_data = {}

            # Step 3: Process fuzzy logic
            logger.debug("Step 3: Processing fuzzy logic")
            fuzzy_start = time.time()

            try:
                fuzzy_result = self.fuzzy_engine.fuzzify_multi_timeframe(
                    fuzzy_input_data, timeframe_filter=timeframe_filter
                )
                fuzzy_processing_time = time.time() - fuzzy_start

                processing_metadata["fuzzy_processing_time"] = fuzzy_processing_time

                # Merge warnings from fuzzy processing
                warnings.extend(fuzzy_result.warnings)

                logger.debug(
                    f"Fuzzy processing completed in {fuzzy_processing_time:.3f}s"
                )

            except Exception as e:
                error_msg = f"Fuzzy processing failed: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

                if fail_fast or not self.enable_error_recovery:
                    raise ProcessingError(
                        message="Fuzzy processing failed in pipeline",
                        error_code="PIPELINE-FuzzyFailed",
                        details={"original_error": str(e)},
                    ) from e

                # Create empty fuzzy result
                fuzzy_result = MultiTimeframeFuzzyResult({}, {}, {}, errors, 0.0)
                fuzzy_input_data = {}

            # Step 4: Finalize results
            total_processing_time = time.time() - start_time
            processing_metadata["total_processing_time"] = total_processing_time
            processing_metadata["success"] = len(errors) == 0

            logger.info(
                f"Pipeline processing completed in {total_processing_time:.3f}s with {len(errors)} errors"
            )

            return IntegratedFuzzyResult(
                fuzzy_result=fuzzy_result,
                indicator_data=fuzzy_input_data,
                processing_metadata=processing_metadata,
                errors=errors,
                warnings=warnings,
                total_processing_time=total_processing_time,
            )

        except Exception as e:
            total_processing_time = time.time() - start_time
            logger.error(
                f"Pipeline processing failed after {total_processing_time:.3f}s: {e}"
            )

            # Re-raise ProcessingError exceptions when fail_fast=True
            if fail_fast and isinstance(e, ProcessingError):
                raise

            processing_metadata["total_processing_time"] = total_processing_time
            processing_metadata["success"] = False
            processing_metadata["final_error"] = str(e)

            # Return error result
            return IntegratedFuzzyResult(
                fuzzy_result=MultiTimeframeFuzzyResult(
                    {}, {}, processing_metadata, [str(e)], 0.0
                ),
                indicator_data={},
                processing_metadata=processing_metadata,
                errors=[str(e)],
                warnings=warnings,
                total_processing_time=total_processing_time,
            )

    def _convert_indicators_to_fuzzy_input(
        self,
        indicator_results: Dict[str, pd.DataFrame],
        timeframe_filter: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Convert indicator results to fuzzy engine input format.

        Args:
            indicator_results: Results from indicator engine
            timeframe_filter: Optional timeframe filter

        Returns:
            Dictionary in format expected by fuzzy engine
        """
        fuzzy_input = {}

        for timeframe, df in indicator_results.items():
            # Apply timeframe filter if specified
            if timeframe_filter and timeframe not in timeframe_filter:
                continue

            if df.empty:
                logger.warning(f"Empty indicator data for timeframe {timeframe}")
                continue

            # Get the latest (most recent) values
            latest_row = df.iloc[-1]

            # Convert to dictionary format expected by fuzzy engine
            timeframe_data = {}
            for column in df.columns:
                if pd.notna(latest_row[column]):
                    # Remove timeframe suffix from column name for fuzzy processing
                    indicator_name = self._extract_base_indicator_name(
                        column, timeframe
                    )
                    timeframe_data[indicator_name] = float(latest_row[column])

            if timeframe_data:
                fuzzy_input[timeframe] = timeframe_data
                logger.debug(
                    f"Converted {len(timeframe_data)} indicators for timeframe {timeframe}"
                )

        return fuzzy_input

    def _extract_base_indicator_name(self, column_name: str, timeframe: str) -> str:
        """
        Extract base indicator name from standardized column name.

        Args:
            column_name: Standardized column name (e.g., "RSI_14_1h")
            timeframe: Timeframe (e.g., "1h")

        Returns:
            Base indicator name (e.g., "rsi")
        """
        # Remove timeframe suffix
        if column_name.endswith(f"_{timeframe}"):
            base_name = column_name[: -len(f"_{timeframe}")]
        else:
            base_name = column_name

        # Extract indicator name (before parameters)
        parts = base_name.split("_")
        if parts:
            return parts[0].lower()

        return base_name.lower()

    def get_supported_timeframes(self) -> List[str]:
        """Get timeframes supported by both indicator and fuzzy engines."""
        indicator_timeframes = set(self.indicator_engine.get_supported_timeframes())
        fuzzy_timeframes = set(self.fuzzy_engine.get_supported_timeframes())
        return list(indicator_timeframes.intersection(fuzzy_timeframes))

    def get_pipeline_health(self) -> Dict[str, Any]:
        """
        Get health status of the pipeline components.

        Returns:
            Dictionary with health information for each component
        """
        return {
            "indicator_engine": {
                "initialized": self.indicator_engine is not None,
                "supported_timeframes": (
                    len(self.indicator_engine.get_supported_timeframes())
                    if self.indicator_engine
                    else 0
                ),
            },
            "fuzzy_engine": {
                "initialized": self.fuzzy_engine is not None,
                "multi_timeframe_enabled": (
                    self.fuzzy_engine.is_multi_timeframe_enabled()
                    if self.fuzzy_engine
                    else False
                ),
                "supported_timeframes": (
                    len(self.fuzzy_engine.get_supported_timeframes())
                    if self.fuzzy_engine
                    else 0
                ),
            },
            "common_timeframes": len(self.get_supported_timeframes()),
            "error_recovery_enabled": self.enable_error_recovery,
            "performance_monitoring_enabled": self.enable_performance_monitoring,
        }


def create_integrated_pipeline(
    indicator_config: Dict[str, Any], fuzzy_config: Dict[str, Any], **kwargs
) -> MultiTimeframeFuzzyIndicatorPipeline:
    """
    Factory function to create an integrated fuzzy-indicator pipeline.

    Args:
        indicator_config: Configuration for multi-timeframe indicators
        fuzzy_config: Configuration for multi-timeframe fuzzy engine
        **kwargs: Additional configuration options

    Returns:
        Configured MultiTimeframeFuzzyIndicatorPipeline instance
    """
    return MultiTimeframeFuzzyIndicatorPipeline(
        indicator_config=indicator_config, fuzzy_config=fuzzy_config, **kwargs
    )
