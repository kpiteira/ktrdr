"""
Base models for the KTRDR API.

This module defines the base models used across the API for consistent
request and response formats.
"""

from typing import Generic, TypeVar, Dict, List, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

# Define a type variable for generic response types
T = TypeVar("T")


class ErrorResponse(BaseModel):
    """
    Standard error response model.

    Attributes:
        code (str): Error code identifier
        message (str): Human-readable error message
        details (Optional[Dict[str, Any]]): Additional error details
    """

    code: str = Field(..., description="Error code identifier")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )


class ApiResponse(BaseModel, Generic[T]):
    """
    Standard API response envelope.

    The response envelope provides a consistent format for all API responses,
    with success status and either data or error information.

    Attributes:
        success (bool): Whether the request was successful
        data (Optional[T]): Response data (if success is True)
        error (Optional[ErrorResponse]): Error information (if success is False)
    """

    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[T] = Field(None, description="Response data when success is True")
    error: Optional[ErrorResponse] = Field(
        None, description="Error information when success is False"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"success": True, "data": {"key": "value"}, "error": None}
        }
    )


class PaginatedData(BaseModel, Generic[T]):
    """
    Paginated response data model.

    This model is used to provide paginated data responses with metadata
    about the pagination status.

    Attributes:
        items (List[T]): List of items in the current page
        total (int): Total number of items across all pages
        page (int): Current page number (1-based)
        page_size (int): Number of items per page
        pages (int): Total number of pages
    """

    items: List[T] = Field(..., description="List of items in the current page")
    total: int = Field(..., description="Total number of items across all pages")
    page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "pages": 5,
            }
        }
    )
