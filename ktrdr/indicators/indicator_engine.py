"""
Indicator Engine module for KTRDR.

This module provides the IndicatorEngine class, which is responsible for
applying indicators to OHLCV data based on configuration.
"""

from typing import Any, Optional

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError, ProcessingError
from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY, BaseIndicator
from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS
from ktrdr.indicators.ma_indicators import ExponentialMovingAverage, SimpleMovingAverage
from ktrdr.indicators.rsi_indicator import RSIIndicator

# Create module-level logger
logger = get_logger(__name__)


class IndicatorEngine:
    """
    Engine for computing technical indicators on OHLCV data.

    The IndicatorEngine transforms OHLCV data into computed technical indicators
    that can be used as inputs for fuzzy logic and model training.

    Accepts v3 dict format: {"indicator_id": {"type": "...", ...params}}

    Attributes:
        _indicators: Dict mapping indicator_id to BaseIndicator instance.
    """

    def __init__(
        self,
        indicators: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize the IndicatorEngine with indicator configuration.

        Args:
            indicators: V3 format dict mapping indicator_id to IndicatorDefinition.
                Example: {"rsi_14": {"type": "rsi", "period": 14}}
        """
        self._indicators: dict[str, BaseIndicator] = {}

        if indicators:
            if not isinstance(indicators, dict):
                raise ConfigurationError(
                    "IndicatorEngine requires v3 dict format. "
                    "Example: {'rsi_14': {'type': 'rsi', 'period': 14}}",
                    "CONFIG-V2FormatRemoved",
                    {"received_type": type(indicators).__name__},
                )

            from ..config.models import IndicatorDefinition

            for indicator_id, definition in indicators.items():
                # Handle both IndicatorDefinition and plain dict
                if not isinstance(definition, IndicatorDefinition):
                    definition = IndicatorDefinition(**definition)

                self._indicators[indicator_id] = self._create_indicator(
                    indicator_id, definition
                )

        logger.info(
            f"Initialized IndicatorEngine with {len(self._indicators)} indicators"
        )

    def _create_indicator(self, indicator_id: str, definition: Any) -> BaseIndicator:
        """
        Create an indicator instance from a v3 IndicatorDefinition.

        Args:
            indicator_id: The indicator identifier (e.g., "rsi_14")
            definition: IndicatorDefinition with type and params

        Returns:
            Instantiated indicator instance

        Raises:
            ValueError: If indicator type is unknown
        """
        from ..config.models import IndicatorDefinition

        # Ensure definition is IndicatorDefinition
        if not isinstance(definition, IndicatorDefinition):
            definition = IndicatorDefinition(**definition)

        # Look up indicator class - try registry first, then fallback
        indicator_class = INDICATOR_REGISTRY.get(definition.type)
        if indicator_class is None:
            # Fallback to BUILT_IN_INDICATORS during migration
            indicator_class = BUILT_IN_INDICATORS.get(definition.type.lower())

        if indicator_class is None:
            # Combine available types from both sources
            available = sorted(
                set(INDICATOR_REGISTRY.list_types()) | set(BUILT_IN_INDICATORS.keys())
            )
            raise ValueError(
                f"Unknown indicator type: '{definition.type}'. "
                f"Available types: {available}"
            )

        # Get extra params from model_extra (all fields except 'type')
        params = definition.model_extra or {}

        # Create and return indicator instance
        try:
            return indicator_class(**params)
        except TypeError as e:
            raise ValueError(
                f"Failed to create indicator '{indicator_id}' of type '{definition.type}': {e}"
            ) from e

    def compute(self, data: pd.DataFrame, indicator_ids: set[str]) -> pd.DataFrame:
        """
        Compute specified indicators on data.

        Args:
            data: OHLCV DataFrame
            indicator_ids: Which indicators to compute

        Returns:
            DataFrame with OHLCV + indicator columns:
            - Single-output: {indicator_id}
            - Multi-output: {indicator_id}.{output_name} + {indicator_id} alias

        NOTE: No timeframe prefix added here - caller handles that.
        """
        result = data.copy()

        for indicator_id in indicator_ids:
            if indicator_id not in self._indicators:
                raise ValueError(f"Unknown indicator: {indicator_id}")

            indicator = self._indicators[indicator_id]
            output = indicator.compute(data)

            if indicator.is_multi_output():
                # Validate outputs match expected
                expected = set(indicator.get_output_names())
                actual = set(output.columns)
                if expected != actual:
                    raise ValueError(
                        f"Indicator {indicator_id} output mismatch: "
                        f"expected {expected}, got {actual}"
                    )

                # Rename columns with indicator_id prefix
                for col in output.columns:
                    result[f"{indicator_id}.{col}"] = output[col]

                # Add alias for primary output (for backward compatibility)
                primary = indicator.get_primary_output()
                if primary:
                    result[indicator_id] = result[f"{indicator_id}.{primary}"]
            else:
                # Single output - name with indicator_id
                result[indicator_id] = output

        return result

    def compute_for_timeframe(
        self, data: pd.DataFrame, timeframe: str, indicator_ids: set[str]
    ) -> pd.DataFrame:
        """
        Compute indicators and prefix columns with timeframe.

        This is a convenience method for pipelines that need
        timeframe-prefixed columns.

        Args:
            data: OHLCV DataFrame
            timeframe: Timeframe string (e.g., "5m", "1h")
            indicator_ids: Which indicators to compute

        Returns:
            DataFrame with columns like "5m_rsi_14", "5m_bbands_20_2.upper"
        """
        result = self.compute(data, indicator_ids)
        return self._prefix_indicator_columns(result, timeframe)

    def _prefix_indicator_columns(
        self, data: pd.DataFrame, timeframe: str
    ) -> pd.DataFrame:
        """
        Prefix indicator columns with timeframe to prevent collisions.

        OHLCV columns (open, high, low, close, volume) are NOT prefixed.
        All other columns (indicator outputs) are prefixed with '{timeframe}_'.

        This enables combining data from multiple timeframes without column
        name collisions (e.g., both 5m and 1h having 'rsi_14' would collide).

        Args:
            data: DataFrame with OHLCV and indicator columns
            timeframe: Timeframe string to use as prefix (e.g., '1h', '5m')

        Returns:
            DataFrame with indicator columns prefixed
        """
        ohlcv_columns = {"open", "high", "low", "close", "volume"}

        # Build rename mapping: only rename non-OHLCV columns
        rename_map = {}
        for col in data.columns:
            if col.lower() not in ohlcv_columns:
                rename_map[col] = f"{timeframe}_{col}"

        if rename_map:
            data = data.rename(columns=rename_map)
            logger.debug(
                f"Prefixed {len(rename_map)} indicator columns with '{timeframe}_'"
            )

        return data

    def compute_indicator(
        self,
        data: pd.DataFrame,
        indicator: BaseIndicator,
        indicator_id: str,
    ) -> pd.DataFrame:
        """
        Compute an indicator and return properly named columns.

        Indicators must return columns matching get_output_names():
        - Single-output: Returns Series or single-column DataFrame
        - Multi-output: Returns DataFrame with semantic column names (e.g., "upper", "lower")

        For multi-output indicators, adds alias column for bare indicator_id
        pointing to primary output.

        Args:
            data: OHLCV DataFrame
            indicator: The indicator instance
            indicator_id: Feature identifier string.
                Should use the format: {indicator_name}_{param1}[_{param2}...] (e.g., "rsi_14",
                "bbands_20_2", "macd_12_26_9"). This becomes the column name (or column prefix
                for multi-output indicators).

        Returns:
            DataFrame with columns:
            - Single-output: {indicator_id}
            - Multi-output: {indicator_id}.{output_name} + {indicator_id} alias

        Raises:
            ValueError: If multi-output indicator returns columns not matching get_output_names()
        """
        result = indicator.compute(data)

        if not indicator.is_multi_output():
            # Single-output: wrap Series in DataFrame with indicator_id column
            if isinstance(result, pd.Series):
                return pd.DataFrame({indicator_id: result}, index=data.index)
            else:
                # Already DataFrame (shouldn't happen for single-output)
                result = result.copy()
                result.columns = [indicator_id]
                # Ensure index alignment with input data
                if not result.index.equals(data.index):
                    result = result.reindex(data.index)
                return result

        # Multi-output indicator
        # At this point, result must be a DataFrame (multi-output returns DataFrame)
        if not isinstance(result, pd.DataFrame):
            expected_columns = list(indicator.get_output_names())
            raise ProcessingError(
                f"Multi-output indicator {indicator.__class__.__name__} must return a pandas.DataFrame "
                f"with columns matching get_output_names() {expected_columns}, "
                f"but returned {type(result).__name__} instead.",
                "PROC-InvalidOutputType",
                {
                    "indicator": indicator.__class__.__name__,
                    "type": type(result).__name__,
                    "expected_type": "pandas.DataFrame",
                    "expected_columns": expected_columns,
                },
            )

        expected_outputs = set(indicator.get_output_names())
        actual_columns = set(result.columns)

        if expected_outputs == actual_columns:
            # NEW FORMAT: semantic names only -> prefix with indicator_id
            # Copy result to avoid modifying original
            prefixed = result.copy()
            prefixed = prefixed.rename(
                columns={name: f"{indicator_id}.{name}" for name in prefixed.columns}
            )

            # Add alias for bare indicator_id -> primary output
            primary = indicator.get_primary_output()
            if primary:
                prefixed[indicator_id] = prefixed[f"{indicator_id}.{primary}"]

            return prefixed
        elif expected_outputs & actual_columns:
            # PARTIAL OVERLAP detected: some expected columns present, but not all
            # This likely indicates a bug in the indicator implementation
            # rather than a legitimate old-format indicator
            missing = expected_outputs - actual_columns
            extra = actual_columns - expected_outputs

            logger.error(
                f"Indicator {indicator.__class__.__name__} returned unexpected output columns "
                f"(partial overlap with get_output_names())"
            )
            raise ProcessingError(
                f"Indicator {indicator.__class__.__name__} returned unexpected output columns. "
                f"Expected all of {sorted(expected_outputs)} but got {sorted(actual_columns)}. "
                f"This suggests a bug in the indicator implementation.",
                "PROC-InvalidIndicatorOutputs",
                {
                    "indicator": indicator.__class__.__name__,
                    "indicator_id": indicator_id,
                    "expected_outputs": sorted(expected_outputs),
                    "actual_columns": sorted(actual_columns),
                    "missing_expected": sorted(missing),
                    "unexpected_extra": sorted(extra),
                },
            )
        else:
            # No overlap with expected outputs - columns don't match get_output_names()
            # This indicates an indicator that hasn't been migrated to v3 format
            raise ValueError(
                f"Indicator {indicator.__class__.__name__} output mismatch: "
                f"expected columns {sorted(expected_outputs)}, "
                f"got {sorted(actual_columns)}. "
                f"Indicator must return columns matching get_output_names()."
            )

    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all configured indicators to the input data.

        This method requires the engine to be initialized with v3 dict format.
        It delegates to compute() internally.

        Args:
            data: DataFrame containing OHLCV data to compute indicators on.
                Must contain at least 'open', 'high', 'low', 'close' columns.

        Returns:
            DataFrame with original data plus indicator columns.

        Raises:
            ConfigurationError: If engine not initialized with v3 format,
                or if required columns are missing.
            ProcessingError: If indicator computation fails.
        """
        # Require v3 format - engine must have _indicators populated
        if not self._indicators:
            raise ConfigurationError(
                "apply() requires v3 dict format. Initialize IndicatorEngine with "
                "dict[str, IndicatorDefinition] instead of list.",
                "CONFIG-V2FormatDeprecated",
                {
                    "hint": "Use IndicatorEngine({'rsi_14': {'type': 'rsi', 'period': 14}})"
                },
            )

        if data is None or data.empty:
            raise ConfigurationError(
                "Cannot compute indicators on empty data.", "CONFIG-EmptyData", {}
            )

        # Check for required columns
        required_cols = ["close"]
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            raise ConfigurationError(
                f"Missing required columns: {', '.join(missing_cols)}",
                "CONFIG-MissingColumns",
                {"missing_columns": missing_cols},
            )

        # Warn if duplicate column names are present in input
        if data.columns.duplicated().any():
            duplicate_columns = [
                col
                for col, is_dup in zip(data.columns, data.columns.duplicated())
                if is_dup
            ]
            logger.warning(
                f"Duplicate column names detected in input data: {duplicate_columns}. "
                f"This may cause unexpected behavior."
            )

        # Delegate to v3 compute() with all indicator_ids
        indicator_ids = set(self._indicators.keys())
        result = self.compute(data, indicator_ids)

        logger.debug(f"Successfully applied {len(indicator_ids)} indicators to data")
        return result

    def apply_multi_timeframe(
        self,
        multi_timeframe_ohlcv: dict[str, pd.DataFrame],
        indicator_configs: Optional[dict[str, dict]] = None,
        prefix_columns: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """
        Apply indicators across multiple timeframes using the same configuration.

        This method processes indicators on multiple timeframes simultaneously,
        applying the same set of indicators to each timeframe's OHLCV data.
        It leverages the existing apply() method for consistency and reuse.

        By default, indicator columns are prefixed with the timeframe name to prevent
        collisions when the same indicator is computed on multiple timeframes
        (e.g., 'rsi_14' becomes '1h_rsi_14' and '5m_rsi_14').

        Args:
            multi_timeframe_ohlcv: Dictionary mapping timeframes to OHLCV DataFrames
                                 Format: {timeframe: ohlcv_dataframe}
            indicator_configs: Optional v3 dict mapping indicator_id to definition.
                             If None, uses the indicators configured in this engine.
                             Example: {"rsi_14": {"type": "rsi", "period": 14}}
            prefix_columns: If True (default), prefix indicator column names with
                          timeframe to prevent collisions. OHLCV columns are not
                          prefixed. Set to False for backward compatibility.

        Returns:
            Dictionary mapping timeframes to DataFrames with computed indicators
            Format: {timeframe: indicators_dataframe}
            With prefix_columns=True, indicator columns will be named like '1h_rsi_14'.

        Raises:
            ConfigurationError: If no timeframe data or indicator configs provided
            ProcessingError: If indicator computation fails for any timeframe

        Example:
            >>> engine = IndicatorEngine({"rsi_14": {"type": "rsi", "period": 14}})
            >>> multi_data = {'1h': ohlcv_1h, '4h': ohlcv_4h}
            >>> results = engine.apply_multi_timeframe(multi_data)
            >>> # results = {'1h': df with '1h_rsi_14', '4h': df with '4h_rsi_14'}
        """
        # Validate inputs
        if not multi_timeframe_ohlcv:
            raise ConfigurationError(
                "No timeframe data provided for multi-timeframe indicator processing",
                error_code="MTIND-NoTimeframes",
                details={"timeframes_provided": list(multi_timeframe_ohlcv.keys())},
            )

        # Use provided configs or fall back to existing indicators
        if indicator_configs is not None:
            if not indicator_configs:
                raise ConfigurationError(
                    "Empty indicator configurations provided",
                    error_code="MTIND-NoConfigs",
                    details={"configs_provided": indicator_configs},
                )
            # Create temporary engine with the provided configs (v3 dict format)
            processing_engine = IndicatorEngine(indicators=indicator_configs)
        else:
            if not self._indicators:
                raise ConfigurationError(
                    "No indicators configured in engine and no configs provided. "
                    "Initialize engine with v3 dict format.",
                    error_code="MTIND-NoIndicators",
                    details={"engine_indicators": len(self._indicators)},
                )
            # Use current engine
            processing_engine = self

        logger.info(
            f"Processing indicators for {len(multi_timeframe_ohlcv)} timeframes: "
            f"{list(multi_timeframe_ohlcv.keys())}"
        )

        results = {}
        processing_errors = {}

        # Process each timeframe
        for timeframe, ohlcv_data in multi_timeframe_ohlcv.items():
            try:
                logger.debug(
                    f"Processing {len(processing_engine._indicators)} indicators for timeframe: {timeframe}"
                )

                # Validate timeframe data
                if ohlcv_data is None or ohlcv_data.empty:
                    logger.warning(
                        f"Empty OHLCV data for timeframe {timeframe}, skipping"
                    )
                    processing_errors[timeframe] = "Empty OHLCV data"
                    continue

                # Apply indicators using existing apply() method
                timeframe_result = processing_engine.apply(ohlcv_data)

                # Prefix indicator columns with timeframe if requested (default)
                if prefix_columns:
                    timeframe_result = self._prefix_indicator_columns(
                        timeframe_result, timeframe
                    )

                results[timeframe] = timeframe_result

                logger.debug(
                    f"Successfully processed {len(timeframe_result.columns)} indicator columns "
                    f"for {timeframe} ({len(timeframe_result)} rows)"
                )

            except Exception as e:
                error_msg = (
                    f"Failed to process indicators for timeframe {timeframe}: {str(e)}"
                )
                logger.error(error_msg)
                processing_errors[timeframe] = str(e)

                # Continue processing other timeframes unless this is critical
                continue

        # Check if we got any results
        if not results:
            raise ProcessingError(
                "Failed to process indicators for any timeframe",
                error_code="MTIND-AllTimeframesFailed",
                details={
                    "requested_timeframes": list(multi_timeframe_ohlcv.keys()),
                    "processing_errors": processing_errors,
                },
            )

        # Log summary
        successful_timeframes = len(results)
        failed_timeframes = len(processing_errors)
        total_timeframes = len(multi_timeframe_ohlcv)

        if failed_timeframes > 0:
            logger.warning(
                f"Multi-timeframe indicator processing completed with warnings: "
                f"{successful_timeframes}/{total_timeframes} timeframes successful"
            )
            for tf, error in processing_errors.items():
                logger.warning(f"  {tf}: {error}")
        else:
            logger.info(
                f"Successfully processed indicators for all {successful_timeframes} timeframes"
            )

        return results

    def compute_rsi(
        self, data: pd.DataFrame, period: int = 14, source: str = "close"
    ) -> pd.DataFrame:
        """
        Compute RSI indicator on the data.

        Args:
            data: DataFrame with OHLCV data.
            period: RSI period.
            source: Column to use for computation.

        Returns:
            DataFrame with RSI column added.
        """
        indicator = RSIIndicator(period=period, source=source)
        result_df = data.copy()
        result_df[f"RSI_{period}"] = indicator.compute(data)
        return result_df

    def compute_sma(
        self, data: pd.DataFrame, period: int = 20, source: str = "close"
    ) -> pd.DataFrame:
        """
        Compute Simple Moving Average indicator on the data.

        Args:
            data: DataFrame with OHLCV data.
            period: SMA period.
            source: Column to use for computation.

        Returns:
            DataFrame with SMA column added.
        """
        indicator = SimpleMovingAverage(period=period, source=source)
        result_df = data.copy()
        result_df[f"SMA_{period}"] = indicator.compute(data)
        return result_df

    def compute_ema(
        self, data: pd.DataFrame, period: int = 20, source: str = "close"
    ) -> pd.DataFrame:
        """
        Compute Exponential Moving Average indicator on the data.

        Args:
            data: DataFrame with OHLCV data.
            period: EMA period.
            source: Column to use for computation.

        Returns:
            DataFrame with EMA column added.
        """
        indicator = ExponentialMovingAverage(period=period, source=source)
        result_df = data.copy()
        result_df[f"EMA_{period}"] = indicator.compute(data)
        return result_df

    def compute_macd(
        self,
        data: pd.DataFrame,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        source: str = "close",
    ) -> pd.DataFrame:
        """
        Compute MACD indicator on the data.

        Args:
            data: DataFrame with OHLCV data.
            fast_period: Period for the fast EMA.
            slow_period: Period for the slow EMA.
            signal_period: Period for the signal line (EMA of MACD line).
            source: Column to use for computation.

        Returns:
            DataFrame with MACD columns added:
            - MACD_{fast}_{slow}: The MACD line
            - MACD_signal_{fast}_{slow}_{signal}: The signal line
            - MACD_hist_{fast}_{slow}_{signal}: The histogram (MACD - signal)
        """
        from ktrdr.indicators.macd_indicator import MACDIndicator

        indicator = MACDIndicator(
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            source=source,
        )

        result_df = data.copy()
        macd_result = indicator.compute(data)

        # Add the MACD columns to the result DataFrame
        for col in macd_result.columns:
            result_df[col] = macd_result[col]

        return result_df
