"""
Indicator service for the KTRDR API.

This module provides services for accessing indicator functionality
through the API, including listing available indicators and calculating
indicator values for given data.
"""

from datetime import datetime
from typing import Any

import pandas as pd

from ktrdr import get_logger
from ktrdr.api.models.indicators import (
    IndicatorCalculateRequest,
    IndicatorMetadata,
    IndicatorParameter,
    IndicatorType,
)
from ktrdr.api.services.base import BaseService
from ktrdr.data.repository import DataRepository
from ktrdr.errors import ConfigurationError, DataError, ProcessingError
from ktrdr.indicators.categories import get_indicator_category
from ktrdr.indicators.indicator_engine import IndicatorEngine
from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS
from ktrdr.monitoring.service_telemetry import trace_service_method

# Create module-level logger
logger = get_logger(__name__)


class IndicatorService(BaseService):
    """
    Service for indicator-related operations.

    This service bridges the API layer with the core indicator functionality,
    providing methods to list available indicators and calculate indicator values.
    """

    def __init__(self):
        """Initialize the indicator service."""
        super().__init__()  # Initialize BaseService
        self.repository = DataRepository()
        self.logger.info("Initialized IndicatorService")

    @trace_service_method("indicator.list")
    async def get_available_indicators(self) -> list[IndicatorMetadata]:
        """
        Get a list of all available indicators with their metadata.

        Returns:
            List of IndicatorMetadata objects containing information about
            each available indicator.

        Raises:
            ProcessingError: If there is an error retrieving indicator information.
        """
        try:
            indicators: list[IndicatorMetadata] = []

            # Process built-in indicators
            for id_name, indicator_class in BUILT_IN_INDICATORS.items():
                # Skip aliases (shorter names for the same indicator)
                if (
                    id_name != indicator_class.__name__
                    and id_name in BUILT_IN_INDICATORS
                ):
                    continue

                # Create a temporary instance to get default parameters
                try:
                    # Instantiate without parameters to get defaults
                    # Each indicator sets its own name via super().__init__()
                    # Note: type ignore needed because indicator_class has type[BaseIndicator]
                    # but concrete classes have their own __init__ signatures
                    temp_instance = indicator_class()  # type: ignore[call-arg]

                    # Get indicator type from categorization system
                    try:
                        category = get_indicator_category(indicator_class.__name__)
                        indicator_type = IndicatorType(category.value)
                    except (KeyError, ValueError):
                        # Default to multi-purpose for unknown indicators
                        indicator_type = IndicatorType.MULTI_PURPOSE

                    # Extract parameters from the indicator's __init__ method
                    params = []

                    # Use inspection to determine default parameters
                    # For simplicity, we'll use hardcoded common parameters
                    # that most indicators have
                    common_params = {"period": 14, "source": "close"}

                    # Check if any of these parameters exist in the instance
                    for param_name, default_value in common_params.items():
                        if hasattr(temp_instance, param_name):
                            param_value = getattr(temp_instance, param_name)
                        else:
                            param_value = default_value

                        # Determine parameter type
                        param_type = "str"
                        if isinstance(param_value, int):
                            param_type = "int"
                        elif isinstance(param_value, float):
                            param_type = "float"
                        elif isinstance(param_value, bool):
                            param_type = "bool"
                        elif isinstance(param_value, list):
                            param_type = "list"
                        elif isinstance(param_value, dict):
                            param_type = "dict"

                        # Extract constraints if available
                        min_value = None
                        max_value = None
                        options = None

                        if hasattr(temp_instance, f"_{param_name}_min"):
                            min_value = getattr(temp_instance, f"_{param_name}_min")
                        if hasattr(temp_instance, f"_{param_name}_max"):
                            max_value = getattr(temp_instance, f"_{param_name}_max")
                        if hasattr(temp_instance, f"_{param_name}_options"):
                            options = getattr(temp_instance, f"_{param_name}_options")

                        # Add parameter metadata
                        params.append(
                            IndicatorParameter(
                                name=param_name,
                                type=param_type,
                                description=f"{param_name.replace('_', ' ').title()} parameter",
                                default=param_value,
                                min_value=min_value,
                                max_value=max_value,
                                options=options if param_name == "source" else None,
                            )
                        )

                    # If source is not already added, add it as a common parameter
                    if not any(p.name == "source" for p in params):
                        params.append(
                            IndicatorParameter(
                                name="source",
                                type="str",
                                description="Source price data to use",
                                default="close",
                                min_value=None,
                                max_value=None,
                                options=["close", "open", "high", "low"],
                            )
                        )

                    # Create indicator metadata
                    metadata = IndicatorMetadata(
                        id=indicator_class.__name__,
                        name=getattr(temp_instance, "name", indicator_class.__name__),
                        description=(
                            indicator_class.__doc__.split("\n\n")[0]
                            if indicator_class.__doc__
                            else ""
                        ),
                        type=indicator_type,
                        parameters=params,
                        resources={},  # Empty resources dict for now
                    )

                    indicators.append(metadata)

                except Exception as e:
                    logger.warning(
                        f"Failed to extract metadata for indicator {id_name}: {str(e)}"
                    )

            logger.info(f"Retrieved metadata for {len(indicators)} indicators")
            return indicators

        except Exception as e:
            logger.error(f"Error retrieving available indicators: {str(e)}")
            raise ProcessingError(
                message="Failed to retrieve available indicators",
                error_code="PROC-IndicatorRetrievalFailed",
                details={"error": str(e)},
            ) from e

    @trace_service_method("indicator.calculate")
    async def calculate_indicators(
        self, request: IndicatorCalculateRequest
    ) -> tuple[list[str], dict[str, list[float]], dict[str, Any]]:
        """
        Calculate indicators based on the provided request.

        Args:
            request: IndicatorCalculateRequest containing the calculation parameters.

        Returns:
            Tuple containing:
            - List of date strings
            - Dictionary mapping indicator names to their calculated values
            - Metadata dictionary with additional information

        Raises:
            DataError: If there is an error loading the required data.
            ConfigurationError: If there is an error in the indicator configuration.
            ProcessingError: If there is an error during indicator calculation.
        """
        try:
            # Load data
            start_date = None
            end_date = None

            if request.start_date:
                start_date = datetime.fromisoformat(request.start_date)
            if request.end_date:
                end_date = datetime.fromisoformat(request.end_date)

            logger.info(
                f"Loading data for {request.symbol} ({request.timeframe}) "
                f"from {start_date or 'beginning'} to {end_date or 'end'}"
            )

            try:
                # Load data from cache using DataRepository
                df = self.repository.load_from_cache(
                    symbol=request.symbol,
                    timeframe=request.timeframe,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception as e:
                logger.error(f"Error loading data: {str(e)}")
                raise DataError(
                    message=f"Failed to load data for {request.symbol} ({request.timeframe})",
                    error_code="DATA-LoadFailed",
                    details={
                        "symbol": request.symbol,
                        "timeframe": request.timeframe,
                        "start_date": request.start_date,
                        "end_date": request.end_date,
                        "error": str(e),
                    },
                ) from e

            if df is None or df.empty:
                raise DataError(
                    message=f"No data available for {request.symbol} ({request.timeframe})",
                    error_code="DATA-NoData",
                    details={"symbol": request.symbol, "timeframe": request.timeframe},
                )

            logger.info(f"Loaded {len(df)} data points")

            # Create indicator instances from the request
            indicators = []
            for indicator_config in request.indicators:
                # Create the appropriate indicator instance
                try:
                    indicator_class = BUILT_IN_INDICATORS.get(indicator_config.id)
                    if not indicator_class:
                        raise ConfigurationError(
                            message=f"Unknown indicator: {indicator_config.id}",
                            error_code="CONFIG-UnknownIndicator",
                            details={"indicator_id": indicator_config.id},
                        )

                    # Create indicator instance with provided parameters
                    indicator = indicator_class(**indicator_config.parameters)

                    # If custom output name is specified, store it for later
                    if indicator_config.output_name:
                        # Store custom output name for later use (type: ignore for dynamic attribute)
                        indicator.output_name = indicator_config.output_name  # type: ignore[attr-defined]

                    indicators.append(indicator)

                except Exception as e:
                    logger.error(
                        f"Error creating indicator {indicator_config.id}: {str(e)}"
                    )
                    raise ConfigurationError(
                        message=f"Failed to create indicator {indicator_config.id}",
                        error_code="CONFIG-IndicatorCreationFailed",
                        details={
                            "indicator_id": indicator_config.id,
                            "parameters": indicator_config.parameters,
                            "error": str(e),
                        },
                    ) from e

            # Initialize the indicator engine with the created indicators
            engine = IndicatorEngine(indicators)

            # Calculate indicators
            try:
                result_df = engine.apply(df)
                logger.info(f"Successfully calculated {len(indicators)} indicators")
            except Exception as e:
                logger.error(f"Error calculating indicators: {str(e)}")
                raise ProcessingError(
                    message="Failed to calculate indicators",
                    error_code="PROC-CalculationFailed",
                    details={"error": str(e)},
                ) from e

            # Extract dates and indicator values
            dates = [
                dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(dt, "strftime") else str(dt)
                for dt in result_df.index
            ]

            # Determine which columns are indicators (not OHLCV)
            ohlcv_columns = ["open", "high", "low", "close", "volume"]
            indicator_columns = [
                col for col in result_df.columns if col.lower() not in ohlcv_columns
            ]

            # Map indicator values by name
            indicator_values = {}
            for col in indicator_columns:
                # Handle custom output names
                output_name = col
                for indicator in indicators:
                    if hasattr(indicator, "output_name") and output_name.startswith(
                        indicator.name
                    ):
                        output_name = indicator.output_name
                        break

                # Convert to list and handle NaN/Inf values for JSON compatibility
                values = result_df[col].tolist()
                # Replace NaN and Inf values with None for JSON serialization
                import math

                clean_values: list[float | None] = []
                for val in values:
                    if pd.isna(val) or math.isinf(val):
                        clean_values.append(None)
                    else:
                        clean_values.append(val)

                indicator_values[output_name] = clean_values

            # Create metadata
            metadata = {
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "start_date": dates[0] if dates else None,
                "end_date": dates[-1] if dates else None,
                "points": len(dates),
            }

            # Ensure proper types for return values
            dates_list: list[str] = [str(d) for d in dates]
            indicator_values_clean: dict[str, list[float]] = {
                k: [float(val) if val is not None else 0.0 for val in v]
                for k, v in indicator_values.items()
            }
            metadata_clean: dict[str, Any] = dict(metadata)

            return dates_list, indicator_values_clean, metadata_clean

        except (DataError, ConfigurationError, ProcessingError):
            # Re-raise known error types
            raise
        except Exception as e:
            logger.error(f"Indicator calculation failed unexpectedly: {str(e)}")
            raise ProcessingError(
                message="An unexpected error occurred during indicator calculation",
                error_code="PROC-UnexpectedError",
                details={"error": str(e)},
            ) from e

    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the indicator service.

        Returns:
            Dict[str, Any]: Health check information
        """
        try:
            # Check available indicators
            indicator_count = len(BUILT_IN_INDICATORS)

            # Get a list of indicator names
            indicator_names = list(BUILT_IN_INDICATORS.keys())

            return {
                "status": "healthy",
                "available_indicators": indicator_count,
                "first_5_indicators": indicator_names[:5] if indicator_names else [],
                "message": "Indicator service is functioning normally",
            }
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"Indicator service health check failed: {str(e)}",
            }
