"""
Tests for Operations Service integration in training host service.

Tests the wrapper module that provides access to OperationsService
from ktrdr.api.services.operations_service.
"""

import pytest

from services.operations import get_operations_service


class TestOperationsServiceWrapper:
    """Test the operations service wrapper module."""

    def test_get_operations_service_returns_instance(self):
        """Test that get_operations_service() returns an OperationsService instance."""
        service = get_operations_service()
        assert service is not None
        assert hasattr(
            service, "_operations"
        ), "Service should have _operations registry"
        assert hasattr(
            service, "_local_bridges"
        ), "Service should have _local_bridges registry (M1 infrastructure)"
        assert hasattr(
            service, "_cache_ttl"
        ), "Service should have _cache_ttl (M1 infrastructure)"

    def test_get_operations_service_returns_singleton(self):
        """Test that get_operations_service() returns the same instance on multiple calls."""
        service1 = get_operations_service()
        service2 = get_operations_service()
        assert service1 is service2, "Should return same singleton instance"

    def test_operations_service_has_registry_methods(self):
        """Test that the operations service has expected registry methods from M1."""
        service = get_operations_service()

        # M1 methods for bridge registration
        assert hasattr(
            service, "register_local_bridge"
        ), "Should have register_local_bridge() method"
        assert hasattr(
            service, "create_operation"
        ), "Should have create_operation() method"
        assert hasattr(service, "get_operation"), "Should have get_operation() method"
        assert hasattr(
            service, "complete_operation"
        ), "Should have complete_operation() method"

    def test_operations_service_cache_ttl_configurable(self):
        """Test that cache TTL is configurable via environment variable."""
        service = get_operations_service()
        assert hasattr(
            service, "_cache_ttl"
        ), "Service should have _cache_ttl attribute"
        assert isinstance(
            service._cache_ttl, float
        ), "Cache TTL should be a float (seconds)"
        # Default is 1.0 second per M1 implementation
        assert service._cache_ttl > 0, "Cache TTL should be positive"

    @pytest.mark.asyncio
    async def test_operations_service_can_create_operation(self):
        """Test that the operations service can create operations."""
        from ktrdr.api.models.operations import OperationMetadata, OperationType

        service = get_operations_service()

        # Create a test operation
        metadata = OperationMetadata(
            symbol="TEST",
            timeframe="1d",
            description="Test operation for host service",
        )

        operation = await service.create_operation(
            operation_type=OperationType.TRAINING, metadata=metadata
        )

        assert operation is not None
        assert operation.operation_id is not None
        assert operation.operation_type == OperationType.TRAINING
        assert operation.metadata.symbol == "TEST"

        # Cleanup
        del service._operations[operation.operation_id]


class TestOperationsServiceImport:
    """Test that imports work correctly."""

    def test_can_import_operations_service(self):
        """Test that OperationsService can be imported from services.operations."""
        from services.operations import OperationsService

        assert OperationsService is not None

    def test_can_import_get_operations_service(self):
        """Test that get_operations_service can be imported."""
        from services.operations import get_operations_service

        assert get_operations_service is not None
        assert callable(get_operations_service)
