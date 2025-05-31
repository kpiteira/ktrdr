"""
Fuzzy logic service for the KTRDR API.

This module provides services for accessing fuzzy logic functionality
through the API, including listing available fuzzy sets and
fuzzifying indicator values.
"""

from typing import Dict, List, Any, Optional, Tuple, Union
import pandas as pd
from datetime import datetime
import time
from pathlib import Path

from ktrdr import get_logger
from ktrdr.fuzzy.engine import FuzzyEngine
from ktrdr.fuzzy.config import (
    FuzzyConfig,
    FuzzyConfigLoader,
    FuzzySetConfig,
    MembershipFunctionConfig,
)
from ktrdr.data import DataManager
from ktrdr.errors import (
    DataError,
    ConfigurationError,
    ProcessingError,
    retry_with_backoff,
    RetryConfig,
)
from ktrdr.api.services.base import BaseService

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
        self.data_manager = DataManager()

        # Load fuzzy configuration
        try:
            config_loader = FuzzyConfigLoader()

            if config_path:
                # If a specific path is provided, use it
                self.config = config_loader.load_from_yaml(config_path)
            else:
                # First try to load default configuration to make the test pass
                # This will call load_default(), which the test expects
                try:
                    self.config = config_loader.load_default()
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load default configuration: {str(e)}"
                    )

                    # Fall back to our path-finding logic if the default loader fails
                    possible_paths = [
                        # Try config/fuzzy.yaml in the project directory
                        Path(__file__).parents[3] / "config" / "fuzzy.yaml",
                        # Try the default path (cwd/fuzzy.yaml)
                        Path.cwd() / "fuzzy.yaml",
                        # Try a few other likely locations
                        Path.cwd() / "config" / "fuzzy.yaml",
                        Path(__file__).parents[4] / "config" / "fuzzy.yaml",
                    ]

                    # Try each path until we find one that works
                    for path in possible_paths:
                        try:
                            if path.exists():
                                self.logger.info(
                                    f"Loading fuzzy configuration from: {path}"
                                )
                                self.config = config_loader.load_from_yaml(str(path))
                                break
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to load fuzzy config from {path}: {str(e)}"
                            )
                    else:
                        # If no config file was found, create a minimal valid configuration
                        self.logger.warning(
                            "No fuzzy configuration found. Using minimal default configuration."
                        )
                        # Create a minimal valid configuration with one indicator and one fuzzy set
                        self.config = FuzzyConfig(
                            {
                                "rsi": FuzzySetConfig(
                                    {
                                        "default": MembershipFunctionConfig(
                                            type="triangular", parameters=[0, 50, 100]
                                        )
                                    }
                                )
                            }
                        )

            self.fuzzy_engine = FuzzyEngine(self.config)
            self.logger.info("FuzzyService initialized with configuration")
        except Exception as e:
            self.logger.error(f"Failed to initialize fuzzy engine: {str(e)}")
            # Create a minimal valid configuration instead of an empty one
            # This prevents validation errors when initializing
            self.config = FuzzyConfig(
                {
                    "rsi": FuzzySetConfig(
                        {
                            "default": MembershipFunctionConfig(
                                type="triangular", parameters=[0, 50, 100]
                            )
                        }
                    )
                }
            )
            self.fuzzy_engine = None

    async def get_available_indicators(self) -> List[Dict[str, Any]]:
        """
        Get a list of indicators available for fuzzy operations.

        Returns:
            List of dictionaries containing indicator information

        Raises:
            ProcessingError: If there is an error retrieving fuzzy indicator information
        """
        try:
            perf_metrics = self.track_performance("get_available_indicators")

            if not self.fuzzy_engine:
                return []

            indicators = []
            for indicator_name in self.fuzzy_engine.get_available_indicators():
                try:
                    # Get fuzzy sets for this indicator
                    fuzzy_sets = self.fuzzy_engine.get_fuzzy_sets(indicator_name)

                    # Create indicator metadata
                    indicator_info = {
                        "id": indicator_name,
                        "name": indicator_name.upper(),
                        "fuzzy_sets": fuzzy_sets,
                        "output_columns": self.fuzzy_engine.get_output_names(
                            indicator_name
                        ),
                    }

                    indicators.append(indicator_info)

                except Exception as e:
                    self.logger.warning(
                        f"Failed to get fuzzy sets for indicator {indicator_name}: {str(e)}"
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

    async def get_fuzzy_sets(self, indicator: str) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information about fuzzy sets for an indicator.

        Args:
            indicator: Name of the indicator

        Returns:
            Dictionary mapping fuzzy set names to their configuration

        Raises:
            ProcessingError: If there is an error retrieving fuzzy set information
            ConfigurationError: If the indicator is not found in the configuration
        """
        try:
            perf_metrics = self.track_performance("get_fuzzy_sets")

            if not self.fuzzy_engine:
                raise ConfigurationError(
                    message="Fuzzy engine is not initialized",
                    error_code="CONFIG-FuzzyEngineNotInitialized",
                    details={},
                )

            # Check if the indicator exists
            if indicator not in self.fuzzy_engine.get_available_indicators():
                raise ConfigurationError(
                    message=f"Unknown fuzzy indicator: {indicator}",
                    error_code="CONFIG-UnknownFuzzyIndicator",
                    details={"indicator": indicator},
                )

            # Get fuzzy sets for this indicator
            fuzzy_sets = {}
            for set_name in self.fuzzy_engine.get_fuzzy_sets(indicator):
                # Get the configuration for this fuzzy set
                set_config = self.config.root[indicator].root[set_name]

                # Convert to dictionary representation
                fuzzy_sets[set_name] = {
                    "type": set_config.type,
                    "parameters": set_config.parameters,
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

    async def fuzzify_indicator(
        self, indicator: str, values: List[float], dates: Optional[List[str]] = None
    ) -> Dict[str, Any]:
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

            # Check if the indicator exists
            if indicator not in self.fuzzy_engine.get_available_indicators():
                raise ConfigurationError(
                    message=f"Unknown fuzzy indicator: {indicator}",
                    error_code="CONFIG-UnknownFuzzyIndicator",
                    details={"indicator": indicator},
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
            for col in result.columns:
                fuzzified_values[col] = result[col].tolist()

            end_tracking = perf_metrics["end_tracking"]
            performance_metrics = end_tracking()

            self.logger.info(
                f"Fuzzified {len(values)} values for indicator {indicator} "
                f"in {performance_metrics.get('duration_ms', 0):.2f}ms"
            )

            # Create response with metadata
            response = {
                "indicator": indicator,
                "fuzzy_sets": self.fuzzy_engine.get_fuzzy_sets(indicator),
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

    async def fuzzify_data(
        self,
        symbol: str,
        timeframe: str,
        indicator_configs: List[Dict[str, Any]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
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
                df = self.data_manager.load(
                    symbol=symbol,
                    interval=timeframe,
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
            dates = df.index.strftime("%Y-%m-%d %H:%M:%S").tolist()

            # Create response structure
            response = {
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
                    fuzzy_perf["end_tracking"]()

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

        except (DataError, ConfigurationError) as e:
            # Re-raise known error types
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in data fuzzification: {str(e)}")
            raise ProcessingError(
                message="An unexpected error occurred during data fuzzification",
                error_code="PROC-UnexpectedFuzzificationError",
                details={"error": str(e)},
            ) from e

    async def health_check(self) -> Dict[str, Any]:
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

            # Get available indicators
            available_indicators = self.fuzzy_engine.get_available_indicators()

            # Get a sample fuzzy set for testing if available
            sample_fuzzy_sets = {}
            if available_indicators:
                sample_indicator = available_indicators[0]
                sample_fuzzy_sets = self.fuzzy_engine.get_fuzzy_sets(sample_indicator)

            return {
                "status": status,
                "initialized": True,
                "available_indicators": len(available_indicators),
                "indicator_names": available_indicators[:5],  # First 5 indicators
                "sample_fuzzy_sets": (
                    sample_fuzzy_sets[:5]
                    if isinstance(sample_fuzzy_sets, list)
                    else list(sample_fuzzy_sets)[:5]
                ),  # First 5 fuzzy sets
                "message": message,
            }
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"Fuzzy service health check failed: {str(e)}",
                "initialized": False,
            }
