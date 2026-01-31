"""
Base class for all technical indicators in the KTRDR system.

This module defines the abstract BaseIndicator class that all indicator
implementations must inherit from, ensuring a consistent interface across
all technical indicators.
"""

import inspect
from abc import ABC, abstractmethod
from typing import Any, Optional, Union

import pandas as pd
from pydantic import BaseModel, ValidationError

from ktrdr import get_logger
from ktrdr.config.validation import InputValidator
from ktrdr.core.type_registry import TypeRegistry
from ktrdr.errors import DataError

logger = get_logger(__name__)

# Global registry for all indicator types
INDICATOR_REGISTRY: TypeRegistry["BaseIndicator"] = TypeRegistry("indicator")


class BaseIndicator(ABC):
    """
    Abstract base class for all technical indicators.

    All indicators in the KTRDR system must inherit from this class
    and implement the compute() method. The BaseIndicator class provides
    common functionality like parameter validation and consistent interfaces.

    Attributes:
        name (str): The name of the indicator (e.g., "RSI", "SMA")
        params (Dict[str, Any]): Dictionary of parameters for the indicator
        display_as_overlay (bool): Whether this indicator can be displayed as an overlay
                                  on price charts by default. Indicators with different
                                  scale than price (like RSI) should set this to False.

    New-style indicators can define a Params nested class for Pydantic validation:
        class MyIndicator(BaseIndicator):
            class Params(BaseIndicator.Params):
                period: int = Field(default=14, ge=2, le=100)

            def compute(self, df): ...
    """

    class Params(BaseModel):
        """Base parameter schema. Subclasses override with their own fields."""

        pass

    # Optional aliases for registry lookup (e.g., ["bbands", "bollinger"])
    _aliases: list[str] = []

    # Whether this indicator should be displayed as overlay on price charts
    # Subclasses can override (e.g., RSI sets to False)
    display_as_overlay: bool = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-register concrete indicator subclasses."""
        super().__init_subclass__(**kwargs)

        # Skip abstract classes
        if inspect.isabstract(cls):
            return

        # Skip test classes (various module naming patterns from pytest)
        module = cls.__module__
        if (
            module.startswith("tests.")
            or ".tests." in module
            or module.startswith("test_")
            or "_test" in module
        ):
            return

        # Derive canonical name from class name
        name = cls.__name__
        if name.endswith("Indicator"):
            name = name[:-9]  # Strip "Indicator" suffix
        canonical = name.lower()

        # Build aliases list (always include full class name lowercase)
        aliases = [cls.__name__.lower()]
        if cls._aliases:
            aliases.extend(cls._aliases)

        INDICATOR_REGISTRY.register(cls, canonical, aliases)

    def __init__(
        self, name: str | None = None, display_as_overlay: bool = True, **params: Any
    ) -> None:
        """
        Initialize a new indicator with its parameters.

        Supports two styles:
        - Old style: super().__init__(name="RSI", period=14) - explicit name
        - New style: MyIndicator(period=14) - name derived from class, Params validation

        Args:
            name: The name of the indicator (old style) or None (new style)
            display_as_overlay: Whether to display as overlay on price charts
            **params: Indicator parameters
        """
        # Determine if this is old-style or new-style initialization
        # New style: no name provided AND class has custom Params
        has_custom_params = self.__class__.Params is not BaseIndicator.Params

        if name is None and has_custom_params:
            # New style: use class-level display_as_overlay if defined, else default
            # Check if class has its own display_as_overlay (not inherited from BaseIndicator)
            if "display_as_overlay" in self.__class__.__dict__:
                self.display_as_overlay = self.__class__.display_as_overlay
            else:
                self.display_as_overlay = display_as_overlay
            # New style: validate via Params, derive name from class
            try:
                validated = self.__class__.Params(**params)
            except ValidationError as e:
                raise DataError(
                    f"Invalid parameters for {self.__class__.__name__}",
                    error_code="INDICATOR-InvalidParameters",
                    details={"validation_errors": e.errors()},
                ) from e

            # Set validated params as instance attributes
            params_class = self.__class__.Params
            for field_name in params_class.model_fields:
                setattr(self, field_name, getattr(validated, field_name))

            # Store params dict for backward compatibility
            self.params = {
                field_name: getattr(validated, field_name)
                for field_name in params_class.model_fields
            }

            # Derive name from class name
            class_name = self.__class__.__name__
            if class_name.endswith("Indicator"):
                class_name = class_name[:-9]
            self.name = class_name

        else:
            # Old style: explicit name, validate via _validate_params
            self.display_as_overlay = display_as_overlay

            if name is None:
                # No name and no custom Params - use class name
                class_name = self.__class__.__name__
                if class_name.endswith("Indicator"):
                    class_name = class_name[:-9]
                name = class_name

            self.name = InputValidator.validate_string(
                name,
                min_length=1,
                max_length=50,
                pattern=r"^[A-Za-z0-9_]+$",  # alphanumeric and underscore only
            )
            self.params = self._validate_params(params)

        logger.info(f"Initialized {self.name} indicator with parameters: {self.params}")

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Validate the parameters passed to the indicator.

        This method should be overridden by subclasses to implement
        specific validation logic for their parameters.

        Args:
            params (Dict[str, Any]): Dictionary of parameters to validate

        Returns:
            Dict[str, Any]: Validated parameters

        Raises:
            DataError: If any parameter validation fails
        """
        return params

    @classmethod
    def is_multi_output(cls) -> bool:
        """
        Indicate whether this indicator produces multiple output columns.

        Returns:
            bool: True if indicator returns DataFrame (multiple columns),
                  False if indicator returns Series (single column).

        Note:
            Multi-output indicators should override this method to return True.
            Single-output indicators can use the default False return value.
        """
        return False

    @classmethod
    def get_output_names(cls) -> list[str]:
        """
        Return semantic output names for multi-output indicators.

        Single-output indicators return empty list.
        Multi-output indicators return ordered list of output names.
        First item is the primary output (used for bare indicator_id references).

        Returns:
            list[str]: List of output names, or empty list for single-output

        Examples:
            RSI: []
            BollingerBands: ["upper", "middle", "lower"]
            MACD: ["line", "signal", "histogram"]
        """
        return []

    @classmethod
    def get_primary_output(cls) -> Optional[str]:
        """
        Return the primary output name for multi-output indicators.

        Convenience method - returns get_output_names()[0] or None.

        Returns:
            Optional[str]: Primary output name, or None for single-output

        Examples:
            RSI.get_primary_output() -> None
            BollingerBands.get_primary_output() -> "upper"
            MACD.get_primary_output() -> "line"
        """
        outputs = cls.get_output_names()
        return outputs[0] if outputs else None

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute the indicator values for the given DataFrame.

        This method must be implemented by all indicator subclasses.

        Args:
            df (pd.DataFrame): DataFrame containing OHLCV data with at least
                              the required columns for this indicator

        Returns:
            Union[pd.Series, pd.DataFrame]: Computed indicator values

        Raises:
            DataError: If input data is invalid or insufficient
        """
        pass

    def validate_input_data(self, df: pd.DataFrame, required_columns: list) -> None:
        """
        Validate that the input DataFrame contains the required columns.

        Args:
            df (pd.DataFrame): DataFrame to validate
            required_columns (list): List of column names that must be present

        Raises:
            DataError: If any required column is missing or if the DataFrame is empty
        """
        if df.empty:
            error_msg = "Input DataFrame is empty"
            logger.error(error_msg)
            raise DataError(
                message=error_msg,
                error_code="DATA-EmptyDataFrame",
                details={"indicator": self.name},
            )

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            error_msg = f"Missing required columns: {missing_columns}"
            logger.error(error_msg)
            raise DataError(
                message=error_msg,
                error_code="DATA-MissingColumns",
                details={
                    "indicator": self.name,
                    "required_columns": required_columns,
                    "available_columns": df.columns.tolist(),
                    "missing_columns": missing_columns,
                },
            )

    def validate_sufficient_data(self, df: pd.DataFrame, min_periods: int) -> None:
        """
        Validate that the DataFrame contains enough data points for calculation.

        Args:
            df (pd.DataFrame): DataFrame to validate
            min_periods (int): Minimum number of data points required

        Raises:
            DataError: If the DataFrame has fewer rows than min_periods
        """
        if len(df) < min_periods:
            error_msg = (
                f"Insufficient data: {len(df)} points available, {min_periods} required"
            )
            logger.error(error_msg)
            raise DataError(
                message=error_msg,
                error_code="DATA-InsufficientDataPoints",
                details={
                    "indicator": self.name,
                    "available_points": len(df),
                    "required_points": min_periods,
                },
            )
