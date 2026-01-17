"""Unit tests for worker data models."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ktrdr.api.models.workers import (
    CompletedOperationReport,
    WorkerEndpoint,
    WorkerStatus,
    WorkerType,
)


class TestWorkerType:
    """Tests for WorkerType enum."""

    def test_worker_types_defined(self):
        """Test that all worker types are defined."""
        assert WorkerType.BACKTESTING == "backtesting"
        assert WorkerType.CPU_TRAINING == "cpu_training"
        assert WorkerType.GPU_HOST == "gpu_host"

    def test_worker_type_is_string_enum(self):
        """Test that WorkerType values are strings."""
        for worker_type in WorkerType:
            assert isinstance(worker_type.value, str)


class TestWorkerStatus:
    """Tests for WorkerStatus enum."""

    def test_worker_statuses_defined(self):
        """Test that all worker statuses are defined."""
        assert WorkerStatus.AVAILABLE == "available"
        assert WorkerStatus.BUSY == "busy"
        assert WorkerStatus.TEMPORARILY_UNAVAILABLE == "temporarily_unavailable"

    def test_worker_status_is_string_enum(self):
        """Test that WorkerStatus values are strings."""
        for status in WorkerStatus:
            assert isinstance(status.value, str)


class TestWorkerEndpoint:
    """Tests for WorkerEndpoint dataclass."""

    def test_create_worker_endpoint(self):
        """Test creating a WorkerEndpoint with required fields."""
        worker = WorkerEndpoint(
            worker_id="test-worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
            status=WorkerStatus.AVAILABLE,
        )

        assert worker.worker_id == "test-worker-1"
        assert worker.worker_type == WorkerType.BACKTESTING
        assert worker.endpoint_url == "http://localhost:5003"
        assert worker.status == WorkerStatus.AVAILABLE
        assert worker.current_operation_id is None
        assert worker.capabilities == {}
        assert worker.metadata == {}
        assert worker.last_health_check is None
        assert worker.last_healthy_at is None
        assert worker.health_check_failures == 0

    def test_create_worker_endpoint_with_all_fields(self):
        """Test creating a WorkerEndpoint with all fields."""
        now = datetime.now(UTC)
        worker = WorkerEndpoint(
            worker_id="test-worker-2",
            worker_type=WorkerType.GPU_HOST,
            endpoint_url="http://192.168.1.100:5002",
            status=WorkerStatus.BUSY,
            current_operation_id="op-123",
            capabilities={"gpu": True, "cores": 8},
            last_health_check=now,
            last_healthy_at=now,
            health_check_failures=2,
            metadata={"region": "us-west"},
        )

        assert worker.worker_id == "test-worker-2"
        assert worker.worker_type == WorkerType.GPU_HOST
        assert worker.endpoint_url == "http://192.168.1.100:5002"
        assert worker.status == WorkerStatus.BUSY
        assert worker.current_operation_id == "op-123"
        assert worker.capabilities == {"gpu": True, "cores": 8}
        assert worker.last_health_check == now
        assert worker.last_healthy_at == now
        assert worker.health_check_failures == 2
        assert worker.metadata == {"region": "us-west"}

    def test_post_init_sets_default_dicts(self):
        """Test that __post_init__ sets default empty dicts."""
        worker = WorkerEndpoint(
            worker_id="test-worker-3",
            worker_type=WorkerType.CPU_TRAINING,
            endpoint_url="http://localhost:5004",
            status=WorkerStatus.AVAILABLE,
        )

        assert worker.capabilities == {}
        assert worker.metadata == {}

    def test_to_dict_basic(self):
        """Test to_dict() method with basic worker."""
        worker = WorkerEndpoint(
            worker_id="test-worker-4",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
            status=WorkerStatus.AVAILABLE,
        )

        data = worker.to_dict()

        assert data["worker_id"] == "test-worker-4"
        assert data["worker_type"] == "backtesting"  # Enum value
        assert data["endpoint_url"] == "http://localhost:5003"
        assert data["status"] == "available"  # Enum value
        assert data["current_operation_id"] is None
        assert data["capabilities"] == {}
        assert data["metadata"] == {}
        assert data["last_health_check"] is None
        assert data["last_healthy_at"] is None
        assert data["health_check_failures"] == 0

    def test_to_dict_with_datetimes(self):
        """Test to_dict() method with datetime fields."""
        now = datetime.now(UTC)
        worker = WorkerEndpoint(
            worker_id="test-worker-5",
            worker_type=WorkerType.GPU_HOST,
            endpoint_url="http://localhost:5002",
            status=WorkerStatus.BUSY,
            current_operation_id="op-456",
            last_health_check=now,
            last_healthy_at=now - timedelta(seconds=30),
        )

        data = worker.to_dict()

        assert data["worker_id"] == "test-worker-5"
        assert data["worker_type"] == "gpu_host"
        assert data["status"] == "busy"
        assert data["current_operation_id"] == "op-456"
        # Datetimes converted to ISO format
        assert data["last_health_check"] == now.isoformat()
        assert data["last_healthy_at"] == (now - timedelta(seconds=30)).isoformat()

    def test_to_dict_preserves_capabilities_and_metadata(self):
        """Test that to_dict() preserves nested dicts."""
        worker = WorkerEndpoint(
            worker_id="test-worker-6",
            worker_type=WorkerType.CPU_TRAINING,
            endpoint_url="http://localhost:5004",
            status=WorkerStatus.AVAILABLE,
            capabilities={"cores": 4, "memory_gb": 8},
            metadata={"datacenter": "dc1", "rack": "A5"},
        )

        data = worker.to_dict()

        assert data["capabilities"] == {"cores": 4, "memory_gb": 8}
        assert data["metadata"] == {"datacenter": "dc1", "rack": "A5"}


class TestCompletedOperationReport:
    """Tests for CompletedOperationReport Pydantic model."""

    def test_create_completed_operation_report_minimal(self):
        """Test creating a CompletedOperationReport with required fields only."""
        completed_at = datetime.now(timezone.utc)
        report = CompletedOperationReport(
            operation_id="op_123",
            status="COMPLETED",
            completed_at=completed_at,
        )

        assert report.operation_id == "op_123"
        assert report.status == "COMPLETED"
        assert report.completed_at == completed_at
        assert report.result is None
        assert report.error_message is None

    def test_create_completed_operation_report_with_result(self):
        """Test creating a CompletedOperationReport with result."""
        completed_at = datetime.now(timezone.utc)
        report = CompletedOperationReport(
            operation_id="op_456",
            status="COMPLETED",
            completed_at=completed_at,
            result={"accuracy": 0.95, "loss": 0.05},
        )

        assert report.operation_id == "op_456"
        assert report.status == "COMPLETED"
        assert report.result == {"accuracy": 0.95, "loss": 0.05}

    def test_create_completed_operation_report_failed(self):
        """Test creating a CompletedOperationReport for failed operation."""
        completed_at = datetime.now(timezone.utc)
        report = CompletedOperationReport(
            operation_id="op_789",
            status="FAILED",
            completed_at=completed_at,
            error_message="Out of memory error",
        )

        assert report.status == "FAILED"
        assert report.error_message == "Out of memory error"

    def test_create_completed_operation_report_cancelled(self):
        """Test creating a CompletedOperationReport for cancelled operation."""
        completed_at = datetime.now(timezone.utc)
        report = CompletedOperationReport(
            operation_id="op_cancel",
            status="CANCELLED",
            completed_at=completed_at,
        )

        assert report.status == "CANCELLED"

    def test_completed_operation_report_validates_status(self):
        """Test that status must be a valid terminal status."""
        completed_at = datetime.now(timezone.utc)

        # Valid statuses should work
        for status in ["COMPLETED", "FAILED", "CANCELLED"]:
            report = CompletedOperationReport(
                operation_id="op_test",
                status=status,
                completed_at=completed_at,
            )
            assert report.status == status

        # Invalid status should raise validation error
        with pytest.raises(ValidationError):
            CompletedOperationReport(
                operation_id="op_test",
                status="RUNNING",  # Not a valid terminal status
                completed_at=completed_at,
            )

    def test_completed_operation_report_requires_operation_id(self):
        """Test that operation_id is required."""
        with pytest.raises(ValidationError):
            CompletedOperationReport(
                status="COMPLETED",
                completed_at=datetime.now(timezone.utc),
            )

    def test_completed_operation_report_requires_completed_at(self):
        """Test that completed_at is required."""
        with pytest.raises(ValidationError):
            CompletedOperationReport(
                operation_id="op_test",
                status="COMPLETED",
            )
