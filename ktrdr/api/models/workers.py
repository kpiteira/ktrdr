"""Worker data models for distributed execution.

This module defines the core data models for managing worker nodes in the
distributed training and backtesting architecture.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class WorkerType(str, Enum):
    """Types of workers in the distributed system."""

    BACKTESTING = "backtesting"
    CPU_TRAINING = "cpu_training"
    GPU_HOST = "gpu_host"


class WorkerStatus(str, Enum):
    """Worker availability status."""

    AVAILABLE = "available"
    BUSY = "busy"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"


@dataclass
class WorkerEndpoint:
    """
    Represents a registered worker endpoint in the system.

    Workers self-register with the backend on startup and maintain their
    availability through health checks.

    Attributes:
        worker_id: Unique identifier for the worker (e.g., hostname)
        worker_type: Type of worker (backtesting, training, etc.)
        endpoint_url: HTTP URL where worker can be reached
        status: Current availability status
        current_operation_id: ID of operation currently being processed (if busy)
        capabilities: Worker capabilities (cores, memory, GPU, etc.)
        last_health_check: Timestamp of last health check attempt
        last_healthy_at: Timestamp of last successful health check
        health_check_failures: Count of consecutive health check failures
        metadata: Additional worker metadata (datacenter, region, etc.)
    """

    worker_id: str
    worker_type: WorkerType
    endpoint_url: str
    status: WorkerStatus
    current_operation_id: Optional[str] = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    last_health_check: Optional[datetime] = None
    last_healthy_at: Optional[datetime] = None
    health_check_failures: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure default values for dict fields."""
        if self.capabilities is None:
            self.capabilities = {}
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """
        Convert worker endpoint to dictionary.

        Returns:
            Dictionary representation with enum values as strings and
            datetimes as ISO format strings.
        """
        data = asdict(self)

        # Convert enum values to strings
        data["worker_type"] = self.worker_type.value
        data["status"] = self.status.value

        # Convert datetimes to ISO format
        if self.last_health_check:
            data["last_health_check"] = self.last_health_check.isoformat()
        if self.last_healthy_at:
            data["last_healthy_at"] = self.last_healthy_at.isoformat()

        return data
