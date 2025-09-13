"""
DummyService API models.

This module defines the request and response models for the DummyService API endpoints,
demonstrating the perfect ServiceOrchestrator pattern with minimal, clean models.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ktrdr.api.models.base import ApiResponse


class DummyOperationResponse(BaseModel):
    """
    Response model for DummyService operations.

    This model demonstrates the standard operation response format that
    ServiceOrchestrator returns - containing operation_id, status, and message.
    """

    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[dict[str, Any]] = Field(
        None, description="Operation data containing operation_id, status, message"
    )
    error: Optional[dict[str, str]] = Field(
        None, description="Error information if the operation failed"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {
                    "operation_id": "op_dummy_123",
                    "status": "started",
                    "message": "Started dummy_task operation",
                },
                "error": None,
            }
        }
    )


# Type alias for clean imports
DummyApiResponse = ApiResponse[dict[str, Any]]
