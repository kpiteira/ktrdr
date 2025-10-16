"""
Indicator Engine module for KTRDR.

This module provides the IndicatorEngine class, which is responsible for
applying indicators to OHLCV data based on configuration.
"""

from typing import Optional, Union, cast

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError, ProcessingError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.indicator_factory import IndicatorFactory
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
        self, indicators: Optional[Union[list[dict], list[BaseIndicator]]] = None
    ):
        """
        Initialize the IndicatorEngine with indicator configuration.

        Args:
            indicators: Optional list of indicator configurations or instances.
                If configurations (dicts) are provided, they will be used to create
                indicator instances via IndicatorFactory. If indicator instances are
                provided, they will be used directly.
        """
        self.indicators: list[BaseIndicator] = []
        self.feature_id_map: dict[str, str] = {}  # Maps column_name -> feature_id

        if indicators:
            if isinstance(indicators[0], dict):
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

        logger.info(
            f"Initialized IndicatorEngine with {len(self.indicators)} indicators"
        )

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

    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all configured indicators to the input data.

        Args:
            data: DataFrame containing OHLCV data to compute indicators on.
                Must contain at least 'open', 'high', 'low', 'close' columns.

        Returns:
            DataFrame with original data plus indicator columns.

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

        # Check for duplicate column names in input
        duplicate_cols = [
            col for col in data.columns if list(data.columns).count(col) > 1
        ]
        if duplicate_cols:
            logger.error(
                f"[CRITICAL BUG] Input DataFrame has DUPLICATE column names: {set(duplicate_cols)}"
            )

        # Create a copy of the input data to avoid modifying original
        result_df = data.copy()

        # Apply each indicator
        for indicator in self.indicators:
            try:
                # Compute indicator and add to result DataFrame
                result = indicator.compute(result_df)

                # Handle both Series and DataFrame results
                if isinstance(result, pd.Series):
                    # Single-output indicator: add with technical column name
                    # Use get_column_name() to get technical name (not feature_id)
                    column_name = indicator.get_column_name()

                    # Check if column already exists (would create duplicate)
                    if column_name in result_df.columns:
                        logger.error(
                            f"[CRITICAL BUG] Column '{column_name}' already exists in result_df! This will create a duplicate."
                        )
                        logger.error(
                            f"[CRITICAL BUG]   Existing columns: {list(result_df.columns)}"
                        )
                        continue

                    result_df[column_name] = result
                elif isinstance(result, pd.DataFrame):
                    # Multi-output indicator: add all columns with their technical names
                    # Use pd.concat to avoid DataFrame fragmentation (much faster than repeated assignments)

                    # Check for columns that already exist (would create duplicates)
                    existing_overlap = [
                        col for col in result.columns if col in result_df.columns
                    ]
                    if existing_overlap:
                        logger.error(
                            f"[CRITICAL BUG] These columns already exist and pd.concat will create duplicates: {existing_overlap}"
                        )
                        logger.error(
                            f"[CRITICAL BUG]   result_df columns count before concat: {len(result_df.columns)}"
                        )

                        # TEMPORARY FIX: Filter out overlapping columns to prevent duplicates
                        # This is a workaround - the root cause is that indicators are being computed twice
                        non_overlapping_cols = [
                            col
                            for col in result.columns
                            if col not in result_df.columns
                        ]
                        if non_overlapping_cols:
                            result = result[non_overlapping_cols]
                        else:
                            continue

                    result_df = pd.concat([result_df, result], axis=1)

            except Exception as e:
                logger.error(
                    f"Error computing indicator {indicator.__class__.__name__}: {str(e)}"
                )
                raise ProcessingError(
                    f"Failed to compute indicator {indicator.__class__.__name__}: {str(e)}",
                    "PROC-IndicatorFailed",
                    {"indicator": indicator.__class__.__name__, "error": str(e)},
                ) from e

        # Create feature_id aliases after all indicators are computed
        result_df = self._create_feature_id_aliases(result_df)

        logger.debug(f"Successfully applied {len(self.indicators)} indicators to data")
        return result_df

    def apply_multi_timeframe(
        self,
        multi_timeframe_ohlcv: dict[str, pd.DataFrame],
        indicator_configs: Optional[list[dict]] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Apply indicators across multiple timeframes using the same configuration.

        This method processes indicators on multiple timeframes simultaneously,
        applying the same set of indicators to each timeframe's OHLCV data.
        It leverages the existing apply() method for consistency and reuse.

        Args:
            multi_timeframe_ohlcv: Dictionary mapping timeframes to OHLCV DataFrames
                                 Format: {timeframe: ohlcv_dataframe}
            indicator_configs: Optional list of indicator configurations. If None,
                             uses the indicators configured in this engine instance.

        Returns:
            Dictionary mapping timeframes to DataFrames with computed indicators
            Format: {timeframe: indicators_dataframe}

        Raises:
            ConfigurationError: If no timeframe data or indicator configs provided
            ProcessingError: If indicator computation fails for any timeframe

        Example:
            >>> engine = IndicatorEngine()
            >>> multi_data = {'1h': ohlcv_1h, '4h': ohlcv_4h}
            >>> configs = [{'name': 'rsi', 'period': 14}]
            >>> results = engine.apply_multi_timeframe(multi_data, configs)
            >>> # results = {'1h': indicators_1h, '4h': indicators_4h}
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
