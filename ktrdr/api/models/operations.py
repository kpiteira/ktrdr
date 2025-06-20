"""
Operation management models for the KTRDR API.

This module defines models for tracking and managing long-running operations
like data loading, training, backtesting, etc.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

from ktrdr.api.models.base import ApiResponse, ErrorResponse


class OperationStatus(str, Enum):
    """Status of an operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationType(str, Enum):
    """Type of operation."""

    DATA_LOAD = "data_load"
    TRAINING = "training"
    BACKTESTING = "backtesting"
    INDICATOR_COMPUTE = "indicator_compute"
    FUZZY_ANALYSIS = "fuzzy_analysis"


class OperationProgress(BaseModel):
    """Progress information for an operation."""

    percentage: float = Field(
        0.0, ge=0.0, le=100.0, description="Progress percentage (0-100)"
    )
    current_step: Optional[str] = Field(None, description="Current step description")
    steps_completed: int = Field(0, ge=0, description="Number of completed steps")
    steps_total: int = Field(0, ge=0, description="Total number of steps")
    items_processed: int = Field(0, ge=0, description="Number of items processed")
    items_total: Optional[int] = Field(
        None, ge=0, description="Total number of items to process"
    )
    current_item: Optional[str] = Field(
        None, description="Current item being processed"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "percentage": 45.5,
                "current_step": "Loading AAPL data for 2024-01-01 to 2024-01-31",
                "steps_completed": 5,
                "steps_total": 11,
                "items_processed": 250,
                "items_total": 550,
                "current_item": "AAPL_1d_2024-01-15",
            }
        }
    )


class OperationMetadata(BaseModel):
    """Metadata associated with an operation."""

    symbol: Optional[str] = Field(None, description="Trading symbol if applicable")
    timeframe: Optional[str] = Field(None, description="Timeframe if applicable")
    mode: Optional[str] = Field(None, description="Operation mode")
    start_date: Optional[datetime] = Field(None, description="Start date for operation")
    end_date: Optional[datetime] = Field(None, description="End date for operation")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Additional parameters"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "AAPL",
                "timeframe": "1h",
                "mode": "tail",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-06-01T00:00:00Z",
                "parameters": {"validate": True, "repair": False},
            }
        }
    )


class OperationInfo(BaseModel):
    """Complete information about an operation."""

    operation_id: str = Field(..., description="Unique operation identifier")
    operation_type: OperationType = Field(..., description="Type of operation")
    status: OperationStatus = Field(..., description="Current operation status")
    created_at: datetime = Field(..., description="When operation was created")
    started_at: Optional[datetime] = Field(None, description="When operation started")
    completed_at: Optional[datetime] = Field(
        None, description="When operation completed"
    )
    progress: OperationProgress = Field(
        default_factory=OperationProgress, description="Progress information"
    )
    metadata: OperationMetadata = Field(
        default_factory=OperationMetadata, description="Operation metadata"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    result_summary: Optional[Dict[str, Any]] = Field(
        None, description="Summary of results"
    )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate operation duration in seconds."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()

    @property
    def is_cancelled_requested(self) -> bool:
        """Check if cancellation has been requested."""
        return self.status == OperationStatus.CANCELLED

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "operation_id": "op_data_load_20241201_123456",
                "operation_type": "data_load",
                "status": "running",
                "created_at": "2024-12-01T12:34:56Z",
                "started_at": "2024-12-01T12:35:00Z",
                "completed_at": None,
                "progress": {
                    "percentage": 65.0,
                    "current_step": "Loading data segment 7/10",
                    "steps_completed": 6,
                    "steps_total": 10,
                },
                "metadata": {"symbol": "AAPL", "timeframe": "1d", "mode": "tail"},
                "error_message": None,
                "warnings": ["Some non-critical warning"],
                "errors": [],
                "result_summary": None,
            }
        }
    )


class OperationSummary(BaseModel):
    """Summary information about an operation (for lists)."""

    operation_id: str = Field(..., description="Unique operation identifier")
    operation_type: OperationType = Field(..., description="Type of operation")
    status: OperationStatus = Field(..., description="Current operation status")
    created_at: datetime = Field(..., description="When operation was created")
    progress_percentage: float = Field(
        0.0, ge=0.0, le=100.0, description="Progress percentage"
    )
    current_step: Optional[str] = Field(None, description="Current step description")
    symbol: Optional[str] = Field(None, description="Trading symbol if applicable")
    duration_seconds: Optional[float] = Field(
        None, description="Operation duration in seconds"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "operation_id": "op_data_load_20241201_123456",
                "operation_type": "data_load",
                "status": "running",
                "created_at": "2024-12-01T12:34:56Z",
                "progress_percentage": 65.0,
                "current_step": "Loading data segment 7/10",
                "symbol": "AAPL",
                "duration_seconds": 125.5,
            }
        }
    )


# Request models
class CancelOperationRequest(BaseModel):
    """Request to cancel an operation."""

    reason: Optional[str] = Field(None, description="Optional reason for cancellation")
    force: bool = Field(
        False, description="Force cancellation even if operation is in critical section"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"reason": "User requested cancellation via CLI", "force": False}
        }
    )


# Response models
class OperationListResponse(BaseModel):
    """Response containing list of operations."""

    success: bool = Field(True, description="Whether the request was successful")
    data: List[OperationSummary] = Field(..., description="List of operations")
    total_count: int = Field(..., ge=0, description="Total number of operations")
    active_count: int = Field(..., ge=0, description="Number of active operations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": [
                    {
                        "operation_id": "op_data_load_20241201_123456",
                        "operation_type": "data_load",
                        "status": "running",
                        "created_at": "2024-12-01T12:34:56Z",
                        "progress_percentage": 65.0,
                        "current_step": "Loading data segment 7/10",
                        "symbol": "AAPL",
                        "duration_seconds": 125.5,
                    }
                ],
                "total_count": 15,
                "active_count": 2,
            }
        }
    )


class OperationStatusResponse(BaseModel):
    """Response containing operation status."""

    success: bool = Field(True, description="Whether the request was successful")
    data: OperationInfo = Field(..., description="Operation information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {
                    "operation_id": "op_data_load_20241201_123456",
                    "operation_type": "data_load",
                    "status": "running",
                    "created_at": "2024-12-01T12:34:56Z",
                    "started_at": "2024-12-01T12:35:00Z",
                    "progress": {
                        "percentage": 65.0,
                        "current_step": "Loading data segment 7/10",
                    },
                    "metadata": {"symbol": "AAPL", "timeframe": "1d"},
                },
            }
        }
    )


class OperationCancelResponse(BaseModel):
    """Response for operation cancellation."""

    success: bool = Field(True, description="Whether the request was successful")
    data: Dict[str, Any] = Field(..., description="Cancellation result")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {
                    "operation_id": "op_data_load_20241201_123456",
                    "status": "cancelled",
                    "cancelled_at": "2024-12-01T12:45:30Z",
                    "cancellation_reason": "User requested cancellation via CLI",
                },
            }
        }
    )


class OperationStartResponse(BaseModel):
    """Response for operation start."""

    success: bool = Field(True, description="Whether the request was successful")
    data: Dict[str, Any] = Field(..., description="Operation start result")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {
                    "operation_id": "op_data_load_20241201_123456",
                    "status": "started",
                    "estimated_duration_seconds": 180,
                    "can_be_cancelled": True,
                },
            }
        }
    )
