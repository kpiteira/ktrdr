"""
API base models tests.

This module tests the base models for the API responses.
"""

import pytest
from pydantic import ValidationError

from ktrdr.api.models.base import ErrorResponse, ApiResponse, PaginatedData


class TestErrorResponse:
    """Tests for the ErrorResponse model."""

    def test_valid_error_response(self):
        """Test that a valid error response is created correctly."""
        error = ErrorResponse(
            code="TEST_ERROR",
            message="Test error message",
            details={"source": "test", "value": 123},
        )
        assert error.code == "TEST_ERROR"
        assert error.message == "Test error message"
        assert error.details == {"source": "test", "value": 123}

    def test_error_response_without_details(self):
        """Test that an error response can be created without details."""
        error = ErrorResponse(code="TEST_ERROR", message="Test error message")
        assert error.code == "TEST_ERROR"
        assert error.message == "Test error message"
        assert error.details is None

    def test_error_response_validation(self):
        """Test that error response validation works correctly."""
        with pytest.raises(ValidationError):
            ErrorResponse(message="Test error message", details={"source": "test"})

        with pytest.raises(ValidationError):
            ErrorResponse(code="TEST_ERROR", details={"source": "test"})


class TestApiResponse:
    """Tests for the ApiResponse model."""

    def test_successful_response(self):
        """Test that a successful response is created correctly."""
        response = ApiResponse[dict](success=True, data={"key": "value"})
        assert response.success is True
        assert response.data == {"key": "value"}
        assert response.error is None

    def test_error_response(self):
        """Test that an error response is created correctly."""
        error = ErrorResponse(code="TEST_ERROR", message="Test error message")
        response = ApiResponse[dict](success=False, error=error)
        assert response.success is False
        assert response.data is None
        assert response.error == error

    def test_different_data_types(self):
        """Test that ApiResponse works with different data types."""
        # String data
        response_str = ApiResponse[str](success=True, data="test string")
        assert response_str.success is True
        assert response_str.data == "test string"

        # List data
        response_list = ApiResponse[list](success=True, data=[1, 2, 3])
        assert response_list.success is True
        assert response_list.data == [1, 2, 3]

    def test_response_validation(self):
        """Test that response validation works correctly."""
        # Test that a valid response passes validation
        valid_response = ApiResponse[dict](success=True, data={"key": "value"})
        assert valid_response.success is True
        assert valid_response.data is not None

        valid_error_response = ApiResponse[dict](
            success=False,
            error=ErrorResponse(code="TEST_ERROR", message="Test error message"),
        )
        assert valid_error_response.success is False
        assert valid_error_response.error is not None

        # Test string instead of boolean for success
        try:
            # This should raise an error with Pydantic V2
            ApiResponse[dict](
                success="not a boolean", data={"key": "value"}  # Type error
            )
            pytest.fail("ValidationError not raised for invalid success type")
        except ValidationError:
            pass  # This is expected


class TestPaginatedData:
    """Tests for the PaginatedData model."""

    def test_valid_paginated_data(self):
        """Test that valid paginated data is created correctly."""
        paginated = PaginatedData[dict](
            items=[{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}],
            total=100,
            page=1,
            page_size=20,
            pages=5,
        )
        assert len(paginated.items) == 2
        assert paginated.items[0]["id"] == 1
        assert paginated.total == 100
        assert paginated.page == 1
        assert paginated.page_size == 20
        assert paginated.pages == 5

    def test_paginated_data_validation(self):
        """Test that paginated data validation works correctly."""
        # Required fields must be provided
        with pytest.raises(ValidationError):
            PaginatedData[dict](items=[{"id": 1, "name": "Item 1"}], total=100, page=1)

        # Items must be a list
        with pytest.raises(ValidationError):
            PaginatedData[dict](
                items="not a list", total=100, page=1, page_size=20, pages=5
            )
