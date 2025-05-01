"""
Extended error models for the KTRDR API.

This module defines detailed error models to provide consistent
error reporting across all API endpoints.
"""
from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from ktrdr.api.models.base import ErrorResponse, ApiResponse


class ErrorCode(str, Enum):
    """Standardized error codes for the API."""
    # Generic errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    
    # Data-specific errors
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    DATA_FORMAT_ERROR = "DATA_FORMAT_ERROR"
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    DATA_SOURCE_ERROR = "DATA_SOURCE_ERROR"
    
    # Indicator-specific errors
    INDICATOR_NOT_FOUND = "INDICATOR_NOT_FOUND"
    INDICATOR_CALCULATION_ERROR = "INDICATOR_CALCULATION_ERROR"
    INDICATOR_PARAMETER_ERROR = "INDICATOR_PARAMETER_ERROR"
    
    # Fuzzy logic errors
    FUZZY_CONFIG_NOT_FOUND = "FUZZY_CONFIG_NOT_FOUND"
    FUZZY_EVALUATION_ERROR = "FUZZY_EVALUATION_ERROR"
    FUZZY_INPUT_ERROR = "FUZZY_INPUT_ERROR"
    
    # Chart-specific errors
    CHART_GENERATION_ERROR = "CHART_GENERATION_ERROR"
    CHART_PARAMETER_ERROR = "CHART_PARAMETER_ERROR"
    
    # Strategy-specific errors
    STRATEGY_NOT_FOUND = "STRATEGY_NOT_FOUND"
    STRATEGY_EXECUTION_ERROR = "STRATEGY_EXECUTION_ERROR"
    STRATEGY_PARAMETER_ERROR = "STRATEGY_PARAMETER_ERROR"


class ValidationErrorItem(BaseModel):
    """
    Individual validation error detail.
    
    Attributes:
        field (str): The field that failed validation
        error (str): Error message
        value (Optional[Any]): The invalid value (if available)
    """
    field: str = Field(..., description="The field that failed validation")
    error: str = Field(..., description="Error message")
    value: Optional[Any] = Field(None, description="The invalid value (if available)")


class ValidationErrorDetail(BaseModel):
    """
    Detailed validation error information.
    
    Attributes:
        errors (List[ValidationErrorItem]): List of validation errors
    """
    errors: List[ValidationErrorItem] = Field(..., description="List of validation errors")


class DataErrorDetail(BaseModel):
    """
    Detailed data error information.
    
    Attributes:
        symbol (Optional[str]): The symbol that caused the error
        timeframe (Optional[str]): The timeframe that caused the error
        message (str): Error message
        error_type (Optional[str]): Type of data error
    """
    symbol: Optional[str] = Field(None, description="The symbol that caused the error")
    timeframe: Optional[str] = Field(None, description="The timeframe that caused the error")
    message: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Type of data error")


class IndicatorErrorDetail(BaseModel):
    """
    Detailed indicator error information.
    
    Attributes:
        indicator_id (Optional[str]): The indicator ID that caused the error
        parameter (Optional[str]): The parameter that caused the error
        message (str): Error message
        error_type (Optional[str]): Type of indicator error
    """
    indicator_id: Optional[str] = Field(None, description="The indicator ID that caused the error")
    parameter: Optional[str] = Field(None, description="The parameter that caused the error")
    message: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Type of indicator error")


class FuzzyErrorDetail(BaseModel):
    """
    Detailed fuzzy logic error information.
    
    Attributes:
        config_id (Optional[str]): The fuzzy config ID that caused the error
        variable (Optional[str]): The variable that caused the error
        message (str): Error message
        error_type (Optional[str]): Type of fuzzy error
    """
    config_id: Optional[str] = Field(None, description="The fuzzy config ID that caused the error")
    variable: Optional[str] = Field(None, description="The variable that caused the error")
    message: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Type of fuzzy error")


class DetailedErrorResponse(ErrorResponse):
    """
    Enhanced error response with additional context and details.
    
    Extends the base ErrorResponse with additional fields for better error handling.
    
    Attributes:
        code (ErrorCode): Standardized error code
        message (str): Human-readable error message
        details (Optional[Dict[str, Any]]): Additional error details
        request_id (Optional[str]): Unique request ID for tracking
        documentation_url (Optional[str]): URL to error documentation
        validation_errors (Optional[ValidationErrorDetail]): Validation error details
    """
    code: ErrorCode = Field(..., description="Standardized error code")
    request_id: Optional[str] = Field(None, description="Unique request ID for tracking")
    documentation_url: Optional[str] = Field(None, description="URL to error documentation")
    validation_errors: Optional[ValidationErrorDetail] = Field(None, description="Validation error details")
    
    model_config = {
        "use_enum_values": True
    }


class DetailedApiResponse(ApiResponse):
    """
    Enhanced API response with detailed error information.
    
    Extends the generic ApiResponse to use the DetailedErrorResponse for errors.
    
    Attributes:
        success (bool): Whether the request was successful
        data (Optional[T]): Response data (if success is True)
        error (Optional[DetailedErrorResponse]): Detailed error information (if success is False)
    """
    error: Optional[DetailedErrorResponse] = None