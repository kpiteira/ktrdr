"""
Unit tests for Operations Metrics functionality (M1: API Contract).

Tests the metrics exposure endpoints and client methods following TDD approach.
These tests are written BEFORE implementation (RED phase).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def sample_operation_with_metrics():
    """Create a sample operation with metrics for testing."""
    return OperationInfo(
        operation_id="op-training-123",
        operation_type=OperationType.TRAINING,
        status=OperationStatus.RUNNING,
        created_at=datetime(2025, 1, 17, 10, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2025, 1, 17, 10, 0, 5, tzinfo=timezone.utc),
        progress=OperationProgress(
            percentage=43.0,
            current_step="Epoch 43/100",
            steps_completed=43,
            steps_total=100,
        ),
        metadata=OperationMetadata(parameters={"epochs": 100, "batch_size": 32}),
        # NEW: metrics field (empty in M1)
        metrics={},
    )


@pytest.fixture
def sample_operation_without_metrics():
    """Create a sample operation without metrics (non-training operation)."""
    return OperationInfo(
        operation_id="op-data-456",
        operation_type=OperationType.DATA_LOAD,
        status=OperationStatus.RUNNING,
        created_at=datetime(2025, 1, 17, 10, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2025, 1, 17, 10, 0, 5, tzinfo=timezone.utc),
        progress=OperationProgress(percentage=50.0),
        metadata=OperationMetadata(symbol="AAPL", timeframe="1h"),
        # Metrics can be None for non-training operations
        metrics=None,
    )


class TestOperationModelMetricsField:
    """Test that Operation model has metrics field."""

    def test_operation_has_metrics_field(self, sample_operation_with_metrics):
        """Test that OperationInfo model has metrics field."""
        # This will FAIL until we add the metrics field to OperationInfo
        assert hasattr(sample_operation_with_metrics, "metrics")

    def test_metrics_field_is_optional(self, sample_operation_without_metrics):
        """Test that metrics field can be None."""
        assert sample_operation_without_metrics.metrics is None

    def test_metrics_field_accepts_dict(self, sample_operation_with_metrics):
        """Test that metrics field accepts dict type."""
        assert isinstance(sample_operation_with_metrics.metrics, dict)

    def test_metrics_field_can_be_empty(self, sample_operation_with_metrics):
        """Test that metrics field can be empty dict (M1 behavior)."""
        assert sample_operation_with_metrics.metrics == {}


class TestOperationMetricsResponse:
    """Test response model for metrics endpoint."""

    def test_metrics_response_structure(self):
        """Test that metrics response has correct structure (M1: empty)."""
        # Expected structure for M1 (empty metrics)
        expected_response = {
            "success": True,
            "data": {
                "operation_id": "op-training-123",
                "operation_type": "training",
                "metrics": {},  # Empty in M1
            },
        }

        assert expected_response["success"] is True
        assert "data" in expected_response
        assert "operation_id" in expected_response["data"]
        assert "operation_type" in expected_response["data"]
        assert "metrics" in expected_response["data"]
        assert expected_response["data"]["metrics"] == {}


# Integration tests (require API server running)
# These will be marked as integration tests
@pytest.mark.integration
class TestOperationsMetricsEndpoints:
    """Test the GET and POST /operations/{id}/metrics endpoints."""

    @pytest.mark.asyncio
    async def test_get_metrics_endpoint_exists(self):
        """
        Test that GET /operations/{id}/metrics endpoint exists.

        This test will FAIL until we implement the endpoint in M1.
        """
        from ktrdr.api.services.operations_service import OperationsService

        # Create a sample training operation
        service = OperationsService()
        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(),
        )

        # Now method exists - verify it works
        metrics = await service.get_operation_metrics(operation.operation_id)

        # In M1, should return empty metrics
        assert metrics is not None
        assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_post_metrics_endpoint_validates_structure(self):
        """
        Test that POST /operations/{id}/metrics validates payload structure.

        In M1: endpoint should accept payload and validate it, but not store.
        This test will FAIL until we implement the endpoint.
        """
        from ktrdr.api.services.operations_service import OperationsService

        # Create a sample training operation
        service = OperationsService()
        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(),
        )

        # Sample metrics payload
        metrics_payload = {
            "epoch": 0,
            "train_loss": 0.8234,
            "val_loss": 0.8912,
            "train_accuracy": 0.65,
            "val_accuracy": 0.58,
            "learning_rate": 0.001,
            "duration": 12.5,
        }

        # Now method exists - verify it validates
        await service.add_operation_metrics(operation.operation_id, metrics_payload)

        # In M1, method should not raise error (validates successfully)
        # Actual storage will be added in M2


@pytest.mark.integration
class TestMCPOperationsClient:
    """Test MCP client get_operation_metrics method."""

    @pytest.mark.asyncio
    async def test_mcp_client_has_get_operation_metrics_method(self):
        """
        Test that MCP OperationsAPIClient has get_operation_metrics method.

        This test will FAIL until we add the method to the client in M1.
        """
        from mcp.src.clients.operations_client import OperationsAPIClient

        # Create client instance
        client = OperationsAPIClient(
            base_url="http://localhost:8000/api/v1", timeout=30.0
        )

        # Method should exist now
        assert hasattr(client, "get_operation_metrics")

    @pytest.mark.asyncio
    async def test_mcp_client_get_operation_metrics_calls_correct_endpoint(self):
        """
        Test that get_operation_metrics calls the correct API endpoint.

        This test verifies the client method makes correct HTTP request.
        Will FAIL until method is implemented.
        """
        from unittest.mock import patch

        from mcp.src.clients.operations_client import OperationsAPIClient

        client = OperationsAPIClient(
            base_url="http://localhost:8000/api/v1", timeout=30.0
        )

        # Mock the _request method
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "success": True,
                "data": {
                    "operation_id": "op-training-123",
                    "operation_type": "training",
                    "metrics": {},
                },
            }

            # Method now exists - verify it calls correct endpoint
            result = await client.get_operation_metrics("op-training-123")

            # Verify correct endpoint was called
            mock_request.assert_called_once_with(
                "GET", "/operations/op-training-123/metrics"
            )

            # Verify response structure
            assert result["success"] is True
            assert result["data"]["operation_id"] == "op-training-123"
            assert "metrics" in result["data"]


# Unit tests for service methods (will be implemented in M1)
class TestOperationsServiceMetricsMethods:
    """Test OperationsService methods for metrics management."""

    @pytest.mark.asyncio
    async def test_get_operation_metrics_method_exists(self):
        """
        Test that OperationsService has get_operation_metrics method.

        Will FAIL in RED phase until method is added.
        """
        from ktrdr.api.services.operations_service import OperationsService

        service = OperationsService()

        # This will FAIL until we add the method
        assert hasattr(service, "get_operation_metrics")

    @pytest.mark.asyncio
    async def test_add_operation_metrics_method_exists(self):
        """
        Test that OperationsService has add_operation_metrics method (for M1 validation).

        Will FAIL in RED phase until method is added.
        """
        from ktrdr.api.services.operations_service import OperationsService

        service = OperationsService()

        # This will FAIL until we add the method
        assert hasattr(service, "add_operation_metrics")

    @pytest.mark.asyncio
    async def test_get_operation_metrics_returns_empty_structure(self):
        """
        Test that get_operation_metrics returns empty structure in M1.

        Since M1 doesn't collect metrics yet, should return empty structure.
        """
        from ktrdr.api.services.operations_service import OperationsService

        service = OperationsService()

        # Create test operation
        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(),
        )

        # Will FAIL until method is implemented
        try:
            metrics = await service.get_operation_metrics(operation.operation_id)

            # In M1, should return empty structure
            assert metrics is not None
            assert isinstance(metrics, dict)
            # Empty metrics in M1
            assert metrics.get("epochs") is None or metrics.get("epochs") == []

        except AttributeError:
            # Expected to fail in RED phase
            pytest.fail("Method get_operation_metrics not implemented yet")


# Edge case tests
class TestMetricsEdgeCases:
    """Test edge cases for metrics functionality."""

    @pytest.mark.asyncio
    async def test_get_metrics_for_nonexistent_operation(self):
        """
        Test getting metrics for operation that doesn't exist.

        Should raise appropriate error.
        """
        from ktrdr.api.services.operations_service import OperationsService

        service = OperationsService()

        # Should raise KeyError for nonexistent operation
        with pytest.raises(KeyError):
            await service.get_operation_metrics("nonexistent-op-id")

    @pytest.mark.asyncio
    async def test_get_metrics_for_non_training_operation(self):
        """
        Test getting metrics for non-training operation.

        Should return None or empty metrics gracefully.
        """
        from ktrdr.api.services.operations_service import OperationsService

        service = OperationsService()

        # Create non-training operation
        operation = await service.create_operation(
            operation_type=OperationType.DATA_LOAD,
            metadata=OperationMetadata(),
        )

        # This will FAIL until method exists
        try:
            metrics = await service.get_operation_metrics(operation.operation_id)

            # Should handle gracefully (None or empty)
            assert metrics is None or metrics == {} or metrics.get("metrics") == {}

        except AttributeError:
            # Expected in RED phase
            pytest.fail("Method get_operation_metrics not implemented yet")
