"""
Fuzzy logic service for the KTRDR API.

This module provides services for accessing fuzzy logic functionality
through the API, including listing available fuzzy sets and
fuzzifying indicator values.

NOTE: This service needs refactoring to work with v3 FuzzyEngine.
V2 config classes have been removed. Some endpoints may not work until
this service is updated to use v3 FuzzySetDefinition format.
"""

from typing import Any, Optional

import pandas as pd

from ktrdr import get_logger
from ktrdr.api.services.base import BaseService
from ktrdr.config.models import FuzzySetDefinition
from ktrdr.data.repository import DataRepository
from ktrdr.errors import (
    ConfigurationError,
    DataError,
    ProcessingError,
)
from ktrdr.fuzzy.batch_calculator import BatchFuzzyCalculator
from ktrdr.fuzzy.engine import FuzzyEngine
from ktrdr.indicators import IndicatorEngine
from ktrdr.monitoring.service_telemetry import trace_service_method

# Create module-level logger
logger = get_logger(__name__)


class FuzzyService(BaseService):
    """
    Service for fuzzy logic operations.

    This service bridges the API layer with the core fuzzy logic functionality,
    providing methods for fuzzifying indicator values and managing fuzzy sets.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the fuzzy service.

        Args:
            config_path: Optional path to the fuzzy configuration file
        """
        super().__init__()  # Initialize BaseService
        self.repository = DataRepository()
        self.indicator_engine = IndicatorEngine()

        # Declare types for attributes that may be None in error cases
        self.fuzzy_engine: Optional[FuzzyEngine] = None
        self.batch_calculator: Optional[BatchFuzzyCalculator] = None

        # Load fuzzy configuration (v3 format)
        # NOTE: YAML loading has been removed. Use v3 FuzzySetDefinition format.
        try:
            # Create a minimal v3 configuration
            # TODO: Implement proper v3 config loading from strategy files
            self.config: dict[str, FuzzySetDefinition] = {
                "rsi_default": FuzzySetDefinition(
                    indicator="rsi",
                    low={"type": "triangular", "parameters": [0, 25, 40]},
                    neutral={"type": "triangular", "parameters": [30, 50, 70]},
                    high={"type": "triangular", "parameters": [60, 75, 100]},
                )
            }

            self.fuzzy_engine = FuzzyEngine(self.config)
            self.batch_calculator = BatchFuzzyCalculator(self.fuzzy_engine)
            self.logger.info(
                "FuzzyService initialized with v3 configuration and batch calculator"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize fuzzy engine: {str(e)}")
            self.config = {}
            self.fuzzy_engine = None
            self.batch_calculator = None

    @trace_service_method("fuzzy.list_indicators")
    async def get_available_indicators(self) -> list[dict[str, Any]]:
        """
        Get a list of indicators available for fuzzy operations.

        Returns:
            List of dictionaries containing indicator information

        Raises:
            ProcessingError: If there is an error retrieving fuzzy indicator information

        NOTE: This method needs refactoring for v3 FuzzyEngine.
        V3 uses fuzzy_set_ids instead of indicator names as keys.
        """
        try:
            perf_metrics = self.track_performance("get_available_indicators")

            if not self.fuzzy_engine:
                return []

            # V3: Use _fuzzy_sets keys (fuzzy_set_ids) instead of indicator names
            indicators = []
            for fuzzy_set_id in self.fuzzy_engine._fuzzy_sets.keys():
                try:
                    # Get membership names for this fuzzy set
                    membership_names = self.fuzzy_engine.get_membership_names(
                        fuzzy_set_id
                    )
                    indicator_name = self.fuzzy_engine.get_indicator_for_fuzzy_set(
                        fuzzy_set_id
                    )

                    # Create indicator metadata
                    indicator_info = {
                        "id": fuzzy_set_id,
                        "name": indicator_name.upper(),
                        "fuzzy_sets": membership_names,
                        "output_columns": [
                            f"{fuzzy_set_id}_{m}" for m in membership_names
                        ],
                    }

                    indicators.append(indicator_info)

                except Exception as e:
                    self.logger.warning(
                        f"Failed to get fuzzy sets for {fuzzy_set_id}: {str(e)}"
                    )

            end_tracking = perf_metrics["end_tracking"]
            end_tracking()

            self.logger.info(f"Retrieved {len(indicators)} fuzzy indicators")
            return indicators

        except Exception as e:
            self.logger.error(f"Error retrieving available fuzzy indicators: {str(e)}")
            raise ProcessingError(
                message="Failed to retrieve available fuzzy indicators",
                error_code="PROC-FuzzyIndicatorRetrievalFailed",
                details={"error": str(e)},
            ) from e

    @trace_service_method("fuzzy.get_sets")
    async def get_fuzzy_sets(self, indicator: str) -> dict[str, dict[str, Any]]:
        """
        Get detailed information about fuzzy sets for an indicator.

        Args:
            indicator: Name of the indicator (or fuzzy_set_id in v3)

        Returns:
            Dictionary mapping fuzzy set names to their configuration

        Raises:
            ProcessingError: If there is an error retrieving fuzzy set information
            ConfigurationError: If the indicator is not found in the configuration

        NOTE: This method needs refactoring for v3. The 'indicator' parameter
        is now interpreted as fuzzy_set_id.
        """
        try:
            perf_metrics = self.track_performance("get_fuzzy_sets")

            if not self.fuzzy_engine:
                raise ConfigurationError(
                    message="Fuzzy engine is not initialized",
                    error_code="CONFIG-FuzzyEngineNotInitialized",
                    details={},
                )

            # V3: 'indicator' is now interpreted as fuzzy_set_id
            fuzzy_set_id = indicator
            if fuzzy_set_id not in self.fuzzy_engine._fuzzy_sets:
                raise ConfigurationError(
                    message=f"Unknown fuzzy set: {fuzzy_set_id}",
                    error_code="CONFIG-UnknownFuzzySet",
                    details={"fuzzy_set_id": fuzzy_set_id},
                )

            # V3: Get membership function info from engine
            fuzzy_sets: dict[str, dict[str, Any]] = {}
            for mf_name, mf in self.fuzzy_engine._fuzzy_sets[fuzzy_set_id].items():
                # Extract type and parameters from the MF instance
                mf_type = type(mf).__name__.lower()
                if mf_type.endswith("mf"):
                    mf_type = mf_type[:-2]  # Remove "mf" suffix
                fuzzy_sets[mf_name] = {
                    "type": mf_type,
                    "parameters": repr(mf),  # Best we can do without storing config
                }

            end_tracking = perf_metrics["end_tracking"]
            end_tracking()

            self.logger.info(
                f"Retrieved {len(fuzzy_sets)} fuzzy sets for indicator {indicator}"
            )
            return fuzzy_sets

        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except Exception as e:
            self.logger.error(
                f"Error retrieving fuzzy sets for indicator {indicator}: {str(e)}"
            )
            raise ProcessingError(
                message=f"Failed to retrieve fuzzy sets for indicator {indicator}",
                error_code="PROC-FuzzySetRetrievalFailed",
                details={"indicator": indicator, "error": str(e)},
            ) from e

    @trace_service_method("fuzzy.fuzzify_indicator")
    async def fuzzify_indicator(
        self, indicator: str, values: list[float], dates: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        Fuzzify indicator values using the configured membership functions.

        Args:
            indicator: Name of the indicator
            values: List of indicator values to fuzzify
            dates: Optional list of dates corresponding to the values

        Returns:
            Dictionary containing fuzzified values for each fuzzy set

        Raises:
            ProcessingError: If there is an error during fuzzification
            ConfigurationError: If the indicator is not found in the configuration
        """
        try:
            perf_metrics = self.track_performance("fuzzify_indicator")

            if not self.fuzzy_engine:
                raise ConfigurationError(
                    message="Fuzzy engine is not initialized",
                    error_code="CONFIG-FuzzyEngineNotInitialized",
                    details={},
                )

            # V3: Check if the fuzzy_set_id exists (indicator param is now fuzzy_set_id)
            fuzzy_set_id = indicator
            if fuzzy_set_id not in self.fuzzy_engine._fuzzy_sets:
                raise ConfigurationError(
                    message=f"Unknown fuzzy set: {fuzzy_set_id}",
                    error_code="CONFIG-UnknownFuzzySet",
                    details={"fuzzy_set_id": fuzzy_set_id},
                )

            # Create pandas Series from the values
            if dates:
                series = pd.Series(values, index=pd.to_datetime(dates))
            else:
                series = pd.Series(values)

            # Fuzzify the values
            result = self.fuzzy_engine.fuzzify(indicator, series)

            # Convert result to dictionary
            fuzzified_values = {}
            if hasattr(result, "columns"):  # It's a DataFrame
                for col in result.columns:
                    col_data = result[col]
                    if hasattr(col_data, "tolist"):
                        fuzzified_values[col] = col_data.tolist()
                    else:
                        fuzzified_values[col] = (
                            [col_data] if not isinstance(col_data, list) else col_data
                        )
            else:  # It's already a dict
                for key, value in result.items():
                    if hasattr(value, "tolist"):
                        fuzzified_values[key] = value.tolist()
                    else:
                        fuzzified_values[key] = (
                            [value] if not isinstance(value, list) else value
                        )

            end_tracking = perf_metrics["end_tracking"]
            performance_metrics = end_tracking()

            self.logger.info(
                f"Fuzzified {len(values)} values for indicator {indicator} "
                f"in {performance_metrics.get('duration_ms', 0):.2f}ms"
            )

            # Create response with metadata
            response = {
                "indicator": indicator,
                "fuzzy_sets": self.fuzzy_engine.get_membership_names(fuzzy_set_id),
                "values": fuzzified_values,
                "points": len(values),
            }

            return response

        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except Exception as e:
            self.logger.error(
                f"Error fuzzifying values for indicator {indicator}: {str(e)}"
            )
            raise ProcessingError(
                message=f"Failed to fuzzify values for indicator {indicator}",
                error_code="PROC-FuzzificationFailed",
                details={"indicator": indicator, "error": str(e)},
            ) from e

    @trace_service_method("fuzzy.fuzzify_data")
    async def fuzzify_data(
        self,
        symbol: str,
        timeframe: str,
        indicator_configs: list[dict[str, Any]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Load data, calculate indicators, and fuzzify the indicator values.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            indicator_configs: List of indicator configurations to calculate and fuzzify
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            Dictionary containing fuzzified values for each indicator and fuzzy set

        Raises:
            DataError: If there is an error loading the required data
            ConfigurationError: If there is an error in the configuration
            ProcessingError: If there is an error during processing
        """
        try:
            overall_perf = self.track_performance("fuzzify_data")

            if not self.fuzzy_engine:
                raise ConfigurationError(
                    message="Fuzzy engine is not initialized",
                    error_code="CONFIG-FuzzyEngineNotInitialized",
                    details={},
                )

            self.log_operation(
                "fuzzify_data",
                symbol=symbol,
                timeframe=timeframe,
                indicators=len(indicator_configs),
                start_date=start_date,
                end_date=end_date,
            )

            # Load data
            load_perf = self.track_performance("load_data")
            try:
                df = self.repository.load_from_cache(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception as e:
                self.logger.error(f"Error loading data: {str(e)}")
                raise DataError(
                    message=f"Failed to load data for {symbol} ({timeframe})",
                    error_code="DATA-LoadFailed",
                    details={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_date": start_date,
                        "end_date": end_date,
                        "error": str(e),
                    },
                ) from e

            if df is None or df.empty:
                raise DataError(
                    message=f"No data available for {symbol} ({timeframe})",
                    error_code="DATA-NoData",
                    details={"symbol": symbol, "timeframe": timeframe},
                )

            load_perf["end_tracking"]()
            self.logger.info(f"Loaded {len(df)} data points for {symbol} ({timeframe})")

            # Extract dates for later use
            dates = [dt.strftime("%Y-%m-%d %H:%M:%S") for dt in df.index]

            # Create response structure
            response: dict[str, Any] = {
                "symbol": symbol,
                "timeframe": timeframe,
                "dates": dates,
                "indicators": {},
                "metadata": {
                    "start_date": dates[0] if dates else None,
                    "end_date": dates[-1] if dates else None,
                    "points": len(dates),
                },
            }

            # Process each indicator configuration
            for config in indicator_configs:
                indicator_name = config.get("name")
                if not indicator_name:
                    self.logger.warning("Skipping indicator config without name")
                    continue

                # Get source column or calculate indicator
                source_column = config.get("source_column", indicator_name)

                # Check if the source is a direct column in the dataframe (like 'close')
                if source_column in df.columns:
                    indicator_values = df[source_column].values
                else:
                    # TODO: Calculate the indicator if it's not a direct column
                    # This would require integration with the IndicatorService
                    self.logger.warning(
                        f"Source column {source_column} not found in dataframe"
                    )
                    continue

                # Fuzzify the indicator values
                try:
                    fuzzy_perf = self.track_performance(f"fuzzify_{indicator_name}")
                    fuzzified = await self.fuzzify_indicator(
                        indicator_name, indicator_values.tolist(), dates
                    )
                    if hasattr(fuzzy_perf, "__getitem__"):  # It's dict-like
                        fuzzy_perf["end_tracking"]()
                    else:
                        # Handle non-dict return case
                        pass

                    # Add to response
                    response["indicators"][indicator_name] = fuzzified["values"]

                except (ConfigurationError, ProcessingError) as e:
                    self.logger.warning(f"Failed to fuzzify {indicator_name}: {str(e)}")
                    # Continue with other indicators rather than failing the whole request

            end_tracking = overall_perf["end_tracking"]
            performance_metrics = end_tracking()

            self.logger.info(
                f"Completed fuzzification for {len(indicator_configs)} indicators "
                f"in {performance_metrics.get('duration_ms', 0):.2f}ms"
            )

            return response

        except (DataError, ConfigurationError):
            # Re-raise known error types
            raise
        except Exception as e:
            self.logger.error(f"Data fuzzification failed unexpectedly: {str(e)}")
            raise ProcessingError(
                message="An unexpected error occurred during data fuzzification",
                error_code="PROC-UnexpectedFuzzificationError",
                details={"error": str(e)},
            ) from e

    @trace_service_method("fuzzy.get_overlays")
    async def get_fuzzy_overlays(
        self,
        symbol: str,
        timeframe: str,
        indicators: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get fuzzy membership overlays for indicators over time.

        This is the main method for the new /fuzzy/data endpoint that provides
        time series fuzzy membership values for chart overlays.

        Args:
            symbol: Trading symbol (e.g., "AAPL")
            timeframe: Data timeframe (e.g., "1h", "1d")
            indicators: List of indicator names (if None, return all configured indicators)
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            Dictionary containing fuzzy overlay data structured for frontend consumption

        Raises:
            DataError: If there is an error loading the required data
            ConfigurationError: If there is an error in the configuration
            ProcessingError: If there is an error during processing
        """
        try:
            overall_perf = self.track_performance("get_fuzzy_overlays")

            if not self.fuzzy_engine or not self.batch_calculator:
                raise ConfigurationError(
                    message="Fuzzy engine is not initialized",
                    error_code="CONFIG-FuzzyEngineNotInitialized",
                    details={},
                )

            self.log_operation(
                "get_fuzzy_overlays",
                symbol=symbol,
                timeframe=timeframe,
                requested_indicators=len(indicators) if indicators else "all",
                start_date=start_date,
                end_date=end_date,
            )

            # V3: Use fuzzy_set_ids instead of indicator names
            available_indicators = list(self.fuzzy_engine._fuzzy_sets.keys())
            if indicators is None:
                # Return all configured indicators
                target_indicators = available_indicators
                self.logger.debug(
                    f"Using all available indicators: {target_indicators}"
                )
            else:
                # Validate requested indicators and filter out unknown ones
                target_indicators = []
                warnings = []

                for indicator in indicators:
                    if indicator in available_indicators:
                        target_indicators.append(indicator)
                    else:
                        warning_msg = f"Unknown indicator '{indicator}' - skipping"
                        warnings.append(warning_msg)
                        self.logger.warning(warning_msg)

                if not target_indicators:
                    self.logger.warning("No valid indicators found after filtering")

            # Load OHLCV data
            load_perf = self.track_performance("load_ohlcv_data")
            try:
                df = self.repository.load_from_cache(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception as e:
                self.logger.error(f"Error loading OHLCV data: {str(e)}")
                raise DataError(
                    message=f"Failed to load data for {symbol} ({timeframe})",
                    error_code="DATA-LoadFailed",
                    details={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "start_date": start_date,
                        "end_date": end_date,
                        "error": str(e),
                    },
                ) from e

            if df is None or df.empty:
                raise DataError(
                    message=f"No data available for {symbol} ({timeframe})",
                    error_code="DATA-NoData",
                    details={"symbol": symbol, "timeframe": timeframe},
                )

            load_perf["end_tracking"]()
            self.logger.info(
                f"Loaded {len(df)} OHLCV data points for {symbol} ({timeframe})"
            )

            # Apply default range logic (e.g., most recent 10000 bars)
            max_bars = 10000
            if len(df) > max_bars:
                df = df.tail(max_bars)
                self.logger.debug(f"Limited data to most recent {max_bars} bars")

            # Calculate indicators and compute fuzzy memberships
            fuzzy_overlay_data = {}
            processing_warnings = []

            for indicator_name in target_indicators:
                try:
                    indicator_perf = self.track_performance(f"process_{indicator_name}")

                    # Calculate or get indicator values
                    indicator_series = await self._get_indicator_values(
                        df, indicator_name
                    )

                    if indicator_series is None:
                        warning_msg = f"Failed to calculate indicator '{indicator_name}' - skipping"
                        processing_warnings.append(warning_msg)
                        self.logger.warning(warning_msg)
                        continue

                    # Compute fuzzy memberships using batch calculator
                    membership_results = self.batch_calculator.calculate_memberships(
                        indicator_name, indicator_series
                    )

                    # Structure results for frontend consumption
                    # V3: indicator_name is actually fuzzy_set_id
                    indicator_fuzzy_sets = []
                    fuzzy_sets = self.fuzzy_engine.get_membership_names(indicator_name)

                    for set_name in fuzzy_sets:
                        output_name = f"{indicator_name}_{set_name}"
                        if output_name in membership_results:
                            membership_series = membership_results[output_name]

                            # Convert to list of timestamp/value pairs
                            membership_points = []
                            for timestamp, value in membership_series.items():
                                membership_points.append(
                                    {
                                        "timestamp": (
                                            timestamp.isoformat()
                                            if hasattr(timestamp, "isoformat")
                                            else str(timestamp)
                                        ),
                                        "value": (
                                            float(value) if pd.notna(value) else None
                                        ),
                                    }
                                )

                            indicator_fuzzy_sets.append(
                                {"set": set_name, "membership": membership_points}
                            )

                    fuzzy_overlay_data[indicator_name] = indicator_fuzzy_sets

                    indicator_perf["end_tracking"]()
                    self.logger.debug(
                        f"Processed fuzzy memberships for {indicator_name}"
                    )

                except Exception as e:
                    warning_msg = (
                        f"Error processing indicator '{indicator_name}': {str(e)}"
                    )
                    processing_warnings.append(warning_msg)
                    self.logger.warning(warning_msg)
                    # Continue with other indicators

            # Prepare response
            response = {
                "symbol": symbol,
                "timeframe": timeframe,
                "data": fuzzy_overlay_data,
            }

            # Add warnings if any occurred
            all_warnings = (
                warnings if "warnings" in locals() else []
            ) + processing_warnings
            if all_warnings:
                response["warnings"] = all_warnings

            end_tracking = overall_perf["end_tracking"]
            performance_metrics = end_tracking()

            self.logger.info(
                f"Generated fuzzy overlays for {len(fuzzy_overlay_data)} indicators "
                f"with {len(df)} data points in {performance_metrics.get('duration_ms', 0):.2f}ms"
            )

            return response

        except (DataError, ConfigurationError):
            # Re-raise known error types
            raise
        except Exception as e:
            self.logger.error(f"Fuzzy overlay generation failed unexpectedly: {str(e)}")
            raise ProcessingError(
                message="An unexpected error occurred during fuzzy overlay generation",
                error_code="PROC-UnexpectedFuzzyOverlayError",
                details={"error": str(e)},
            ) from e

    async def _get_indicator_values(
        self, df: pd.DataFrame, indicator_name: str
    ) -> Optional[pd.Series]:
        """
        Get or calculate indicator values from the OHLCV dataframe.

        Args:
            df: OHLCV dataframe
            indicator_name: Name of the indicator

        Returns:
            Series with indicator values or None if calculation fails
        """
        try:
            # Check if it's a direct OHLCV column first
            if indicator_name.lower() in ["open", "high", "low", "close", "volume"]:
                column_name = indicator_name.lower()
                if column_name in df.columns:
                    return df[column_name]

            # Use IndicatorEngine to calculate the indicator
            indicator_perf = self.track_performance(f"calculate_{indicator_name}")

            try:
                # Map indicator names to their calculation methods
                if indicator_name.lower() == "rsi":
                    result_df = self.indicator_engine.compute_rsi(data=df)
                    # RSI calculation returns a dataframe with an 'RSI_14' column (or similar)
                    rsi_columns = [
                        col for col in result_df.columns if "rsi" in col.lower()
                    ]
                    if rsi_columns:
                        indicator_series = result_df[
                            rsi_columns[0]
                        ]  # Use first RSI column found
                        indicator_perf["end_tracking"]()
                        return indicator_series
                    else:
                        self.logger.warning("No RSI column found in result")
                        return None

                elif indicator_name.lower() == "macd":
                    result_df = self.indicator_engine.compute_macd(data=df)
                    # MACD calculation returns multiple columns, use the main MACD line
                    macd_columns = [
                        col
                        for col in result_df.columns
                        if "macd" in col.lower()
                        and "signal" not in col.lower()
                        and "histogram" not in col.lower()
                    ]
                    if macd_columns:
                        indicator_series = result_df[
                            macd_columns[0]
                        ]  # Use main MACD line
                        indicator_perf["end_tracking"]()
                        return indicator_series
                    else:
                        self.logger.warning("No MACD column found in result")
                        return None

                elif indicator_name.lower() == "ema":
                    result_df = self.indicator_engine.compute_ema(data=df)
                    # EMA calculation returns a dataframe with an EMA column
                    ema_columns = [
                        col for col in result_df.columns if "ema" in col.lower()
                    ]
                    if ema_columns:
                        indicator_series = result_df[
                            ema_columns[0]
                        ]  # Use first EMA column found
                        indicator_perf["end_tracking"]()
                        return indicator_series
                    else:
                        self.logger.warning("No EMA column found in result")
                        return None

                elif indicator_name.lower() == "sma":
                    result_df = self.indicator_engine.compute_sma(data=df)
                    # SMA calculation returns a dataframe with an SMA column
                    sma_columns = [
                        col for col in result_df.columns if "sma" in col.lower()
                    ]
                    if sma_columns:
                        indicator_series = result_df[
                            sma_columns[0]
                        ]  # Use first SMA column found
                        indicator_perf["end_tracking"]()
                        return indicator_series
                    else:
                        self.logger.warning("No SMA column found in result")
                        return None

                else:
                    self.logger.warning(f"Unknown indicator: {indicator_name}")
                    return None

            except Exception as e:
                self.logger.warning(
                    f"Failed to calculate indicator {indicator_name}: {str(e)}"
                )
                return None
            finally:
                indicator_perf["end_tracking"]()

        except Exception as e:
            self.logger.error(
                f"Error getting indicator values for {indicator_name}: {str(e)}"
            )
            return None

    @trace_service_method("fuzzy.health_check")
    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the fuzzy service.

        Returns:
            Dict[str, Any]: Health check information
        """
        try:
            status = "healthy"
            message = "Fuzzy service is functioning normally"

            # Check if fuzzy engine is initialized
            if not self.fuzzy_engine:
                status = "degraded"
                message = "Fuzzy engine is not initialized"

                return {"status": status, "message": message, "initialized": False}

            # V3: Get available fuzzy_set_ids
            available_indicators = list(self.fuzzy_engine._fuzzy_sets.keys())

            # Get a sample fuzzy set for testing if available
            sample_fuzzy_sets: list[str] = []
            if available_indicators:
                sample_fuzzy_set_id = available_indicators[0]
                sample_fuzzy_sets = self.fuzzy_engine.get_membership_names(
                    sample_fuzzy_set_id
                )

            return {
                "status": status,
                "initialized": True,
                "available_indicators": len(available_indicators),
                "indicator_names": available_indicators[:5],  # First 5 indicators
                "sample_fuzzy_sets": sample_fuzzy_sets[:5],  # First 5 fuzzy sets
                "message": message,
            }
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"Fuzzy service health check failed: {str(e)}",
                "initialized": False,
            }
