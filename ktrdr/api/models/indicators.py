"""
Indicator models for the KTRDR API.

This module defines the models related to technical indicators, including
request and response models for indicator configuration and calculation.
"""

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from ktrdr.api.models.base import ApiResponse


class IndicatorType(str, Enum):
    """Types of technical indicators."""

    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    SUPPORT_RESISTANCE = "support_resistance"
    MULTI_PURPOSE = "multi_purpose"


class IndicatorParameter(BaseModel):
    """
    Definition of an indicator parameter.

    Attributes:
        name (str): Parameter name
        type (str): Parameter type (int, float, str, bool)
        description (str): Parameter description
        default (Any): Default value
        min_value (Optional[Union[int, float]]): Minimum value for numeric parameters
        max_value (Optional[Union[int, float]]): Maximum value for numeric parameters
        options (Optional[List[Any]]): Available options for enum-like parameters
    """

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (int, float, str, bool)")
    description: str = Field(..., description="Parameter description")
    default: Any = Field(..., description="Default value")
    min_value: Optional[Union[int, float]] = Field(
        None, description="Minimum value for numeric parameters"
    )
    max_value: Optional[Union[int, float]] = Field(
        None, description="Maximum value for numeric parameters"
    )
    options: Optional[list[Any]] = Field(
        None, description="Available options for enum-like parameters"
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate parameter type."""
        valid_types = ["int", "float", "str", "bool", "list", "dict"]
        if v not in valid_types:
            raise ValueError(f"Parameter type must be one of {valid_types}")
        return v

    @model_validator(mode="after")
    def validate_constraints(self) -> "IndicatorParameter":
        """Validate that constraints are appropriate for the parameter type."""
        if self.type in ["int", "float"]:
            # Numeric types should have min and max if constraints are specified
            if self.min_value is not None and self.max_value is not None:
                if self.min_value > self.max_value:
                    raise ValueError(
                        "min_value must be less than or equal to max_value"
                    )

        if self.options is not None and len(self.options) > 0:
            # If options are specified, default should be one of them
            if self.default not in self.options:
                raise ValueError("default value must be one of the specified options")

        return self


class IndicatorMetadata(BaseModel):
    """
    Metadata about an indicator.

    Attributes:
        id (str): Unique identifier for the indicator
        name (str): Display name of the indicator
        description (str): Description of the indicator
        type (IndicatorType): Type of indicator
        parameters (List[IndicatorParameter]): Available parameters
        resources (Optional[Dict[str, str]]): Additional resources (URLs, docs)
    """

    id: str = Field(..., description="Unique identifier for the indicator")
    name: str = Field(..., description="Display name of the indicator")
    description: str = Field(..., description="Description of the indicator")
    type: IndicatorType = Field(..., description="Type of indicator")
    parameters: list[IndicatorParameter] = Field(
        ..., description="Available parameters"
    )
    resources: Optional[dict[str, str]] = Field(
        None, description="Additional resources (URLs, docs)"
    )


class IndicatorConfig(BaseModel):
    """
    Indicator configuration for calculation.

    Attributes:
        id (str): Indicator identifier
        parameters (Dict[str, Any]): Indicator parameters
        output_name (Optional[str]): Custom name for the indicator output
    """

    id: str = Field(..., description="Indicator identifier")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Indicator parameters"
    )
    output_name: Optional[str] = Field(
        None, description="Custom name for the indicator output"
    )


class IndicatorResult(BaseModel):
    """
    Indicator calculation result.

    Attributes:
        name (str): Name of the indicator (or custom output name)
        values (List[Optional[float]]): Calculated indicator values
        metadata (Optional[Dict[str, Any]]): Additional metadata
    """

    name: str = Field(..., description="Name of the indicator (or custom output name)")
    values: list[Optional[float]] = Field(
        ..., description="Calculated indicator values"
    )
    metadata: Optional[dict[str, Any]] = Field(None, description="Additional metadata")


class IndicatorCalculateRequest(BaseModel):
    """
    Request model for calculating indicators.

    Attributes:
        symbol (str): Trading symbol
        timeframe (str): Data timeframe
        indicators (List[IndicatorConfig]): Indicator configurations to calculate
        start_date (Optional[str]): Start date for calculation (ISO format)
        end_date (Optional[str]): End date for calculation (ISO format)
    """

    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe")
    indicators: list[IndicatorConfig] = Field(
        ..., description="Indicator configurations to calculate"
    )
    start_date: Optional[str] = Field(
        None, description="Start date for calculation (ISO format)"
    )
    end_date: Optional[str] = Field(
        None, description="End date for calculation (ISO format)"
    )

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate that the timeframe is in the correct format."""
        valid_timeframes = [
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "1d",
            "1w",
            "1M",
        ]
        if v not in valid_timeframes:
            raise ValueError(f"Timeframe must be one of {valid_timeframes}")
        return v

    @model_validator(mode="after")
    def validate_indicators(self) -> "IndicatorCalculateRequest":
        """Validate that at least one indicator is specified."""
        if not self.indicators or len(self.indicators) == 0:
            raise ValueError("At least one indicator must be specified")
        return self


class IndicatorCalculateResponse(BaseModel):
    """
    Response model for indicator calculation.

    Attributes:
        success (bool): Whether the calculation was successful
        dates (List[str]): List of date strings
        indicators (Dict[str, List[Optional[float]]]): Calculated indicator values
        metadata (Optional[Dict[str, Any]]): Additional metadata
    """

    success: bool = Field(..., description="Whether the calculation was successful")
    dates: list[str] = Field(..., description="List of date strings")
    indicators: dict[str, list[Optional[float]]] = Field(
        ..., description="Calculated indicator values"
    )
    metadata: Optional[dict[str, Any]] = Field(None, description="Additional metadata")


class IndicatorsListResponse(ApiResponse[list[IndicatorMetadata]]):
    """Response model for listing available indicators."""

    pass


class IndicatorDetail(BaseModel):
    """
    Detailed information about an indicator.

    Attributes:
        metadata (IndicatorMetadata): Basic indicator metadata
        description_html (Optional[str]): HTML-formatted description
        formula_html (Optional[str]): HTML-formatted formula
        examples (Optional[List[Dict[str, Any]]]): Example configurations and results
    """

    metadata: IndicatorMetadata = Field(..., description="Basic indicator metadata")
    description_html: Optional[str] = Field(
        None, description="HTML-formatted description"
    )
    formula_html: Optional[str] = Field(None, description="HTML-formatted formula")
    examples: Optional[list[dict[str, Any]]] = Field(
        None, description="Example configurations and results"
    )


class IndicatorDetailResponse(ApiResponse[IndicatorDetail]):
    """Response model for indicator detail endpoint."""

    pass
