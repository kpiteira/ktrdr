"""
API models package.

This package contains Pydantic models for API requests and responses.
"""

# Export models from the base module
from ktrdr.api.models.base import (
    ErrorResponse,
    ApiResponse,
    PaginatedData,
)

# Public API
__all__ = [
    "ErrorResponse",
    "ApiResponse",
    "PaginatedData",
]