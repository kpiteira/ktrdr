"""
Integration tests for service initialization.

Tests that the training host service starts successfully with OperationsService.
"""

import pytest
from fastapi.testclient import TestClient


class TestServiceInitialization:
    """Test that the service initializes correctly with all required components."""

    def test_service_starts_with_operations_service(self):
        """Test that the service starts and OperationsService is initialized."""
        # Import main app
        from main import app

        # Create test client (this triggers startup event)
        with TestClient(app) as client:
            # Verify service is running
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["healthy"] is True

        # Verify OperationsService was initialized (singleton persists)
        from services.operations import get_operations_service

        ops_service = get_operations_service()
        assert ops_service is not None
        assert hasattr(ops_service, "_operations")
        assert hasattr(ops_service, "_local_bridges")

    def test_operations_service_available_after_startup(self):
        """Test that OperationsService is accessible after startup."""
        from main import app

        with TestClient(app) as client:
            # Service should be running
            response = client.get("/")
            assert response.status_code == 200
            assert response.json()["service"] == "Training Host Service"

            # OperationsService should be initialized
            from services.operations import get_operations_service

            ops_service = get_operations_service()
            assert ops_service is not None

            # Should be able to access cache TTL
            assert hasattr(ops_service, "_cache_ttl")
            assert ops_service._cache_ttl > 0

    @pytest.mark.asyncio
    async def test_operations_service_can_create_operations_after_startup(self):
        """Test that OperationsService can create operations after startup."""
        from main import app

        with TestClient(app):
            from ktrdr.api.models.operations import OperationMetadata, OperationType
            from services.operations import get_operations_service

            ops_service = get_operations_service()

            # Create test operation
            metadata = OperationMetadata(
                symbol="TEST_INIT",
                timeframe="1d",
                description="Test operation after service initialization",
            )

            operation = await ops_service.create_operation(
                operation_type=OperationType.TRAINING, metadata=metadata
            )

            assert operation is not None
            assert operation.operation_id is not None

            # Cleanup
            del ops_service._operations[operation.operation_id]
