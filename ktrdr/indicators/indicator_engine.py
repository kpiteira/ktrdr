"""
Indicator Engine module for KTRDR.

This module provides the IndicatorEngine class, which is responsible for
applying indicators to OHLCV data based on configuration.
"""

from typing import Any, Optional, Union, cast

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError, ProcessingError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS, IndicatorFactory
from ktrdr.indicators.ma_indicators import ExponentialMovingAverage, SimpleMovingAverage
from ktrdr.indicators.rsi_indicator import RSIIndicator

# Create module-level logger
logger = get_logger(__name__)


class IndicatorEngine:
    """
    Engine for computing technical indicators on OHLCV data.

    The IndicatorEngine transforms OHLCV data into computed technical indicators
    that can be used as inputs for fuzzy logic and model training. It accepts
    configuration via a list of indicator specifications or direct indicator instances.

    Attributes:
        indicators (List[BaseIndicator]): List of indicator instances to apply.
    """

    def __init__(
        self,
        indicators: Optional[
            Union[dict[str, Any], list[dict], list[BaseIndicator]]
        ] = None,
    ):
        """
        Initialize the IndicatorEngine with indicator configuration.

        Args:
            indicators: Indicator configuration in one of three formats:
                - V3 format: Dict mapping indicator_id to IndicatorDefinition
                - V2 format: List of indicator config dicts
                - Direct instances: List of BaseIndicator instances
        """
        self.indicators: list[BaseIndicator] = []
        self.feature_id_map: dict[str, str] = {}  # Maps column_name -> feature_id
        self._indicators: dict[str, BaseIndicator] = (
            {}
        )  # V3: Maps indicator_id to instance

        if indicators:
            # V3 format: dict[str, IndicatorDefinition]
            if isinstance(indicators, dict):
                from ..config.models import IndicatorDefinition

                for indicator_id, definition in indicators.items():
                    # Handle both IndicatorDefinition and plain dict
                    if not isinstance(definition, IndicatorDefinition):
                        definition = IndicatorDefinition(**definition)

                    self._indicators[indicator_id] = self._create_indicator(
                        indicator_id, definition
                    )
            # V2 format: list of dicts or BaseIndicator instances
            elif isinstance(indicators[0], dict):
                # Create indicators from config dictionaries
                # Import here to avoid circular dependency
                from ..config.models import IndicatorConfig

                # Convert dict configs to IndicatorConfig objects
                indicator_configs: list[IndicatorConfig] = []
                for ind_dict in indicators:
                    if isinstance(ind_dict, dict):
                        indicator_configs.append(IndicatorConfig(**ind_dict))
                    else:
                        # Already an IndicatorConfig object
                        indicator_configs.append(ind_dict)  # type: ignore[arg-type]

                # Create factory with configs and build all indicators
                factory = IndicatorFactory(indicator_configs)
                self.indicators = factory.build()

                # Build feature_id_map from configs and indicators
                self._build_feature_id_map(indicator_configs, self.indicators)
            elif isinstance(indicators[0], BaseIndicator):
                # Use provided indicator instances directly
                # Type narrowing: if first element is BaseIndicator, assume all are
                self.indicators = cast(list[BaseIndicator], indicators)
            else:
                raise ConfigurationError(
                    "Invalid indicator specification type. Must be dict or BaseIndicator instance.",
                    "CONFIG-InvalidType",
                    {"type": type(indicators[0]).__name__},
                )

        # Log based on which format was used
        indicator_count = (
            len(self._indicators) if self._indicators else len(self.indicators)
        )
        logger.info(f"Initialized IndicatorEngine with {indicator_count} indicators")

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

        # Look up indicator class
        indicator_class = BUILT_IN_INDICATORS.get(definition.type.lower())
        if indicator_class is None:
            raise ValueError(
                f"Unknown indicator type: '{definition.type}'. "
                f"Available types: {sorted(set(BUILT_IN_INDICATORS.keys()))}"
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
            DataFrame with indicator columns:
            - Single-output: {indicator_id}
            - Multi-output: {indicator_id}.{output_name}

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
            else:
                # Single output - name with indicator_id
                result[indicator_id] = output

        return result

    def _build_feature_id_map(
        self, configs: list, indicators: list[BaseIndicator]
    ) -> None:
        """
        Build the feature_id_map mapping column names to feature_ids.

        This method creates the mapping between technical column names (from
        indicator output) and user-facing feature_ids (from config).

        For multi-output indicators, only the primary output (first column) is mapped.
        Uses class methods to determine indicator behavior - NO computation needed.

        Args:
            configs: List of IndicatorConfig objects
            indicators: List of instantiated indicator instances (parallel to configs)
        """
        from ..config.models import IndicatorConfig

        for config, indicator in zip(configs, indicators):
            # Ensure config is IndicatorConfig
            if not isinstance(config, IndicatorConfig):
                continue

            feature_id = config.feature_id
            indicator_class = type(indicator)

            # Use class method - NO COMPUTATION!
            if indicator_class.is_multi_output():
                # Multi-output: get primary column name using suffix
                suffix = indicator_class.get_primary_output_suffix()
                if suffix:
                    column_name = indicator.get_column_name(suffix=suffix)
                else:
                    column_name = indicator.get_column_name()

                self.feature_id_map[column_name] = feature_id
                logger.debug(
                    f"Mapped multi-output indicator primary column '{column_name}' "
                    f"to feature_id '{feature_id}' (indicator: {config.name})"
                )
            else:
                # Single-output indicator: map column_name directly to feature_id
                column_name = self._get_technical_column_name(config, indicator)
                self.feature_id_map[column_name] = feature_id
                logger.debug(
                    f"Mapped column '{column_name}' to feature_id '{feature_id}' "
                    f"(indicator: {config.name})"
                )

    def _get_technical_column_name(self, config, indicator: BaseIndicator) -> str:
        """
        Get the technical column name that an indicator will produce.

        This creates a temporary clean indicator instance to get the column name,
        avoiding any name modifications from IndicatorFactory.

        Args:
            config: IndicatorConfig with the indicator parameters
            indicator: The indicator instance (used for class reference)

        Returns:
            The technical column name (e.g., "rsi_14", "ema_20")
        """
        # Create a fresh instance with just the params to get clean column name
        indicator_class = type(indicator)

        try:
            temp_indicator = indicator_class(**config.params)
            return temp_indicator.get_column_name()
        except Exception as e:
            # Fallback to using the existing indicator's column name
            logger.warning(
                f"Failed to create temp indicator for column name, using existing: {e}"
            )
            return indicator.get_column_name()

    def _create_feature_id_aliases(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create feature_id aliases in the DataFrame.

        For each entry in feature_id_map (column_name -> feature_id), creates an alias
        column with the same values if feature_id differs from column_name.

        Note: Pandas DataFrames don't support true column aliasing at the API level.
        The alias will be a separate column with identical values. While this creates
        a copy in memory, it's acceptable because:
        1. Only one alias per indicator (not multiple copies)
        2. Memory overhead is minimal compared to total data size
        3. Benefit of dual naming (technical + user-facing) outweighs cost

        Args:
            data: DataFrame with indicator columns (technical names)

        Returns:
            DataFrame with feature_id aliases added
        """
        if not self.feature_id_map:
            # No feature_id_map (e.g., indicators created directly without configs)
            return data

        for column_name, feature_id in self.feature_id_map.items():
            # Only create alias if feature_id differs from column name
            if column_name != feature_id:
                # Check if technical column exists
                if column_name in data.columns:
                    selected = data[column_name]

                    # Check for duplicate columns causing DataFrame selection
                    if isinstance(selected, pd.DataFrame):
                        logger.error(
                            f"[CRITICAL BUG] data['{column_name}'] returned DataFrame instead of Series! "
                            f"This means there are duplicate columns named '{column_name}'. "
                            f"Columns in DataFrame: {list(selected.columns)}"
                        )
                        # Take first column as workaround
                        selected = selected.iloc[:, 0]

                    # Create alias column with same values as technical column
                    # Note: This creates a copy in pandas, but provides the dual naming benefit
                    data[feature_id] = selected
                    logger.debug(
                        f"Created feature_id alias: '{column_name}' -> '{feature_id}'"
                    )
                else:
                    logger.warning(
                        f"Cannot create alias for '{feature_id}': "
                        f"technical column '{column_name}' not found in data"
                    )

        return data

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

        Handles both old-format and new-format indicator outputs:
        - Old format: columns include params (e.g., "upper_20_2.0") -> pass through
        - New format: semantic names only (e.g., "upper") -> prefix with indicator_id

        For multi-output indicators, adds alias column for bare indicator_id
        pointing to primary output.

        Args:
            data: OHLCV DataFrame
            indicator: The indicator instance
            indicator_id: Feature identifier string, typically from indicator.get_feature_id().
                Should use the format: {indicator_name}_{param1}[_{param2}...] (e.g., "rsi_14",
                "bbands_20_2", "macd_12_26_9"). This becomes the column name (or column prefix
                for multi-output indicators).

        Returns:
            DataFrame with columns:
            - Single-output: {indicator_id}
            - Multi-output (new): {indicator_id}.{output_name} + {indicator_id} alias
            - Multi-output (old): original columns + {indicator_id} alias
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
            # CLEANUP(v3): Remove old-format handling after v3 migration complete
            # OLD FORMAT: no overlap with expected outputs -> columns have params embedded
            # Pass through columns and add alias for primary output

            # Copy result to avoid modifying original
            result_copy = result.copy()

            primary_suffix = indicator.get_primary_output_suffix()
            primary_col = None

            if primary_suffix:
                # Find column that matches primary suffix
                # Use precise matching: column starts with suffix + "_" (e.g., "upper_20_2.0")
                # This avoids false matches like "super_upper" when looking for "upper"
                for col in result_copy.columns:
                    if col.startswith(primary_suffix + "_"):
                        primary_col = col
                        break
            else:
                # No suffix means primary is the "base" column (e.g., MACD_12_26)
                # Find column without underscore-separated suffix
                for col in result_copy.columns:
                    if col == indicator.get_column_name():
                        primary_col = col
                        break

            if primary_col:
                # Add backward-compatible alias for the primary output
                result_copy[indicator_id] = result_copy[primary_col]
            else:
                # No primary column found - this can happen for some legacy indicators
                # during the v2->v3 migration. Log a warning to aid debugging.
                logger.warning(
                    f"Could not determine primary output column for indicator '{indicator_id}' "
                    f"({indicator.__class__.__name__}) in old-format output. "
                    f"Available columns: {list(result_copy.columns)}. "
                    f"No alias column will be created."
                )

            return result_copy

    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all configured indicators to the input data.

        Routes all indicator computation through compute_indicator() adapter (M2).
        The adapter handles both old-format and new-format indicator outputs
        during the v2->v3 migration.

        Args:
            data: DataFrame containing OHLCV data to compute indicators on.
                Must contain at least 'open', 'high', 'low', 'close' columns.

        Returns:
            DataFrame with original data plus indicator columns.
            Column names use feature_ids (from indicator.get_feature_id()).

        Raises:
            ConfigurationError: If required columns are missing.
            ProcessingError: If indicator computation fails.
        """
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
        # (helps debug data quality issues upstream)
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

        # Create a copy of the input data to avoid modifying original
        result_df = data.copy()

        # Apply each indicator through compute_indicator() adapter
        for indicator in self.indicators:
            try:
                # Get indicator_id from feature_id or fall back to column name
                indicator_id = indicator.get_feature_id()

                # Compute indicator using adapter (handles both old/new formats)
                # Use result_df to support indicator chaining (indicators that depend on previous indicators)
                computed = self.compute_indicator(result_df, indicator, indicator_id)

                # Merge computed columns into result
                result_df = pd.concat([result_df, computed], axis=1)

            except Exception as e:
                logger.error(
                    f"Error computing indicator {indicator.__class__.__name__}: {str(e)}"
                )
                raise ProcessingError(
                    f"Failed to compute indicator {indicator.__class__.__name__}: {str(e)}",
                    "PROC-IndicatorFailed",
                    {"indicator": indicator.__class__.__name__, "error": str(e)},
                ) from e

        # CLEANUP(v3): Remove _create_feature_id_aliases() after v3 migration
        # The adapter now creates aliases automatically, but keep this for backward compatibility
        # during transition (in case feature_id_map is used elsewhere)
        result_df = self._create_feature_id_aliases(result_df)

        logger.debug(f"Successfully applied {len(self.indicators)} indicators to data")
        return result_df

    def apply_multi_timeframe(
        self,
        multi_timeframe_ohlcv: dict[str, pd.DataFrame],
        indicator_configs: Optional[list[dict]] = None,
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
            indicator_configs: Optional list of indicator configurations. If None,
                             uses the indicators configured in this engine instance.
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
            >>> engine = IndicatorEngine()
            >>> multi_data = {'1h': ohlcv_1h, '4h': ohlcv_4h}
            >>> configs = [{'name': 'rsi', 'period': 14}]
            >>> results = engine.apply_multi_timeframe(multi_data, configs)
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
            # Create temporary engine with the provided configs
            processing_engine = IndicatorEngine(indicators=indicator_configs)
        else:
            if not self.indicators:
                raise ConfigurationError(
                    "No indicators configured in engine and no configs provided",
                    error_code="MTIND-NoIndicators",
                    details={"engine_indicators": len(self.indicators)},
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
                    f"Processing {len(processing_engine.indicators)} indicators for timeframe: {timeframe}"
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
