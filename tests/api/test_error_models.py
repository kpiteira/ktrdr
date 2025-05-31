"""
API error models tests.

This module tests the enhanced error models for API responses.
"""

import pytest
from pydantic import ValidationError

from ktrdr.api.models.errors import (
    ErrorCode,
    ValidationErrorItem,
    ValidationErrorDetail,
    DataErrorDetail,
    IndicatorErrorDetail,
    FuzzyErrorDetail,
    DetailedErrorResponse,
    DetailedApiResponse,
)


class TestValidationErrorModels:
    """Tests for the validation error models."""

    def test_validation_error_item(self):
        """Test that a validation error item is created correctly."""
        error_item = ValidationErrorItem(
            field="symbol", error="Field required", value=None
        )
        assert error_item.field == "symbol"
        assert error_item.error == "Field required"
        assert error_item.value is None

    def test_validation_error_detail(self):
        """Test that validation error details are created correctly."""
        error_detail = ValidationErrorDetail(
            errors=[
                ValidationErrorItem(field="symbol", error="Field required", value=None),
                ValidationErrorItem(
                    field="timeframe", error="Invalid value", value="invalid"
                ),
            ]
        )
        assert len(error_detail.errors) == 2
        assert error_detail.errors[0].field == "symbol"
        assert error_detail.errors[1].field == "timeframe"


class TestSpecificErrorDetailModels:
    """Tests for specific error detail models."""

    def test_data_error_detail(self):
        """Test that data error details are created correctly."""
        error_detail = DataErrorDetail(
            symbol="AAPL",
            timeframe="1d",
            message="Data not available for the specified date range",
            error_type="NOT_FOUND",
        )
        assert error_detail.symbol == "AAPL"
        assert error_detail.timeframe == "1d"
        assert error_detail.message == "Data not available for the specified date range"
        assert error_detail.error_type == "NOT_FOUND"

    def test_indicator_error_detail(self):
        """Test that indicator error details are created correctly."""
        error_detail = IndicatorErrorDetail(
            indicator_id="rsi",
            parameter="period",
            message="Period must be greater than 1",
            error_type="VALIDATION_ERROR",
        )
        assert error_detail.indicator_id == "rsi"
        assert error_detail.parameter == "period"
        assert error_detail.message == "Period must be greater than 1"
        assert error_detail.error_type == "VALIDATION_ERROR"

    def test_fuzzy_error_detail(self):
        """Test that fuzzy error details are created correctly."""
        error_detail = FuzzyErrorDetail(
            config_id="trading_strategy_1",
            variable="rsi",
            message="Invalid fuzzy variable reference",
            error_type="REFERENCE_ERROR",
        )
        assert error_detail.config_id == "trading_strategy_1"
        assert error_detail.variable == "rsi"
        assert error_detail.message == "Invalid fuzzy variable reference"
        assert error_detail.error_type == "REFERENCE_ERROR"


class TestDetailedErrorResponse:
    """Tests for the DetailedErrorResponse model."""

    def test_basic_error_response(self):
        """Test that a basic detailed error response is created correctly."""
        error = DetailedErrorResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message="Validation error occurred",
            details={"field": "symbol", "value": None},
        )
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.message == "Validation error occurred"
        assert error.details == {"field": "symbol", "value": None}
        assert error.request_id is None
        assert error.documentation_url is None
        assert error.validation_errors is None

    def test_complete_error_response(self):
        """Test that a complete detailed error response is created correctly."""
        error = DetailedErrorResponse(
            code=ErrorCode.VALIDATION_ERROR,
            message="Multiple validation errors occurred",
            details={"source": "request_body"},
            request_id="req-123-abc",
            documentation_url="https://docs.example.com/errors/validation",
            validation_errors=ValidationErrorDetail(
                errors=[
                    ValidationErrorItem(
                        field="symbol", error="Field required", value=None
                    ),
                    ValidationErrorItem(
                        field="timeframe", error="Invalid value", value="invalid"
                    ),
                ]
            ),
        )
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.message == "Multiple validation errors occurred"
        assert error.details == {"source": "request_body"}
        assert error.request_id == "req-123-abc"
        assert error.documentation_url == "https://docs.example.com/errors/validation"
        assert len(error.validation_errors.errors) == 2

    def test_invalid_error_code(self):
        """Test that an invalid error code raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            DetailedErrorResponse(
                code="INVALID_CODE",  # Not in ErrorCode enum
                message="Test error message",
            )
        assert "code" in str(exc_info.value)


class TestDetailedApiResponse:
    """Tests for the DetailedApiResponse model."""

    def test_successful_response(self):
        """Test that a successful response is created correctly."""
        response = DetailedApiResponse[dict](success=True, data={"key": "value"})
        assert response.success is True
        assert response.data == {"key": "value"}
        assert response.error is None

    def test_error_response(self):
        """Test that an error response is created correctly."""
        error = DetailedErrorResponse(
            code=ErrorCode.DATA_NOT_FOUND,
            message="Data not found",
            request_id="req-123-abc",
        )
        response = DetailedApiResponse[dict](success=False, error=error)
        assert response.success is False
        assert response.data is None
        assert response.error == error
        assert response.error.code == ErrorCode.DATA_NOT_FOUND
        assert response.error.request_id == "req-123-abc"
