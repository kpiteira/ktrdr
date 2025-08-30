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

        # Create a copy of the input data to avoid modifying original
        result_df = data.copy()

        # Apply each indicator
        for indicator in self.indicators:
            try:
                # Get indicator name for better logging
                indicator_name = getattr(
                    indicator, "name", str(indicator.__class__.__name__)
                )
                logger.debug(f"Computing indicator: {indicator_name}")

                # Compute indicator and add to result DataFrame
                result = indicator.compute(result_df)

                # Handle both Series and DataFrame results
                if isinstance(result, pd.Series):
                    # If a name is provided, use it; otherwise, use indicator name
                    name = result.name if result.name else indicator_name
                    result_df[name] = result
                elif isinstance(result, pd.DataFrame):
                    # Merge the result DataFrame with our result_df
                    for col in result.columns:
                        result_df[col] = result[col]

                logger.debug(f"Successfully computed {indicator_name}")

            except Exception as e:
                logger.error(
                    f"Error computing indicator {indicator.__class__.__name__}: {str(e)}"
                )
                raise ProcessingError(
                    f"Failed to compute indicator {indicator.__class__.__name__}: {str(e)}",
                    "PROC-IndicatorFailed",
                    {"indicator": indicator.__class__.__name__, "error": str(e)},
                ) from e

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
