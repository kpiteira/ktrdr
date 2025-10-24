"""
Unit tests for M3 Task 3.1: Host Training Pull Architecture - Convergence.

Tests that backend acts as pure proxy for host training operations,
registering OperationServiceProxy instead of creating orchestrator/bridge.

Key Test Scenarios:
1. Backend registers proxy (not bridge) for host training
2. Backend stores both operation IDs (backend + host)
3. Backend returns immediately after proxy registration
4. get_operation() pulls from host via proxy
5. Operation ID mapping works correctly
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ktrdr.api.models.operations import OperationStatus, OperationType
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.services.adapters.operation_service_proxy import OperationServiceProxy


@pytest.fixture
def operations_service():
    """Create OperationsService instance for testing."""
    return OperationsService()


@pytest.fixture
def mock_proxy():
    """Create mock OperationServiceProxy."""
    proxy = MagicMock(spec=OperationServiceProxy)
    proxy.get_operation = AsyncMock()
    proxy.get_metrics = AsyncMock()
    return proxy


class TestRegisterRemoteProxy:
    """Test OperationsService.register_remote_proxy() method."""

    def test_register_remote_proxy_stores_mapping(
        self, operations_service, mock_proxy
    ):
        """Test that register_remote_proxy() stores operation ID mapping."""
        backend_op_id = "op_training_20250120_abc123"
        host_op_id = "host_training_xyz789"

        # ACT: Register proxy with both IDs
        operations_service.register_remote_proxy(
            backend_operation_id=backend_op_id,
            proxy=mock_proxy,
            host_operation_id=host_op_id,
        )

        # ASSERT: Mapping stored correctly
        assert backend_op_id in operations_service._remote_proxies
        stored_proxy, stored_host_id = operations_service._remote_proxies[backend_op_id]
        assert stored_proxy is mock_proxy
        assert stored_host_id == host_op_id

    def test_register_remote_proxy_initializes_cursor(
        self, operations_service, mock_proxy
    ):
        """Test that register_remote_proxy() initializes metrics cursor to 0."""
        backend_op_id = "op_training_123"
        host_op_id = "host_training_456"

        # ACT
        operations_service.register_remote_proxy(
            backend_operation_id=backend_op_id,
            proxy=mock_proxy,
            host_operation_id=host_op_id,
        )

        # ASSERT: Cursor initialized to 0
        assert backend_op_id in operations_service._metrics_cursors
        assert operations_service._metrics_cursors[backend_op_id] == 0


class TestHostTrainingRouting:
    """Test that backend routes host training correctly (proxy, not bridge)."""

    @pytest.mark.asyncio
    async def test_backend_registers_proxy_not_bridge_for_host_training(
        self, operations_service, mock_proxy
    ):
        """
        Test that when training runs on host service, backend registers
        OperationServiceProxy (not ProgressBridge).
        """
        # ARRANGE
        backend_op_id = "op_training_backend_123"
        host_op_id = "host_training_session_456"

        # Create operation in backend
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata={"symbols": ["AAPL"], "strategy": "test"},
        )
        backend_op_id = operation.operation_id

        # ACT: Register proxy (simulating what _run_host_training() should do)
        operations_service.register_remote_proxy(
            backend_operation_id=backend_op_id,
            proxy=mock_proxy,
            host_operation_id=host_op_id,
        )

        # ASSERT: Proxy registered, NOT bridge
        assert backend_op_id in operations_service._remote_proxies
        assert backend_op_id not in operations_service._local_bridges

    @pytest.mark.asyncio
    async def test_get_operation_pulls_from_host_via_proxy(
        self, operations_service, mock_proxy
    ):
        """
        Test that get_operation() pulls from host service via proxy
        when operation is registered with remote proxy.
        """
        # ARRANGE
        backend_op_id = "op_training_backend_123"
        host_op_id = "host_training_session_456"

        # Create operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata={"symbols": ["AAPL"]},
        )
        backend_op_id = operation.operation_id

        # Register proxy
        operations_service.register_remote_proxy(
            backend_operation_id=backend_op_id,
            proxy=mock_proxy,
            host_operation_id=host_op_id,
        )

        # Start operation (mark as RUNNING)
        await operations_service.start_operation(backend_op_id, task=None)

        # Mock host response
        mock_proxy.get_operation.return_value = {
            "operation_id": host_op_id,
            "status": "running",  # lowercase - matches OperationStatus enum
            "progress": {
                "percentage": 55.0,
                "current_step": "Epoch 55/100",
                "steps_completed": 55,
                "steps_total": 100,
            },
        }
        mock_proxy.get_metrics.return_value = ([], 0)  # No new metrics

        # Invalidate cache to force refresh
        operations_service._last_refresh[backend_op_id] = 0

        # ACT: Get operation (should trigger proxy query)
        result = await operations_service.get_operation(backend_op_id)

        # ASSERT: Proxy was called with HOST operation ID
        mock_proxy.get_operation.assert_called_once_with(host_op_id)
        mock_proxy.get_metrics.assert_called_once_with(host_op_id, 0)

        # Backend operation updated with host data
        assert result.progress.percentage == 55.0
        assert result.progress.current_step == "Epoch 55/100"

    @pytest.mark.asyncio
    async def test_operation_id_mapping_backend_to_host(
        self, operations_service, mock_proxy
    ):
        """
        Test that backend operation ID correctly maps to host operation ID.

        Client uses backend ID, but queries to host use host ID.
        """
        # ARRANGE
        backend_op_id = "op_training_20250120_abc"
        host_op_id = "host_training_session_xyz"

        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata={"session_id": "xyz"},
        )
        backend_op_id = operation.operation_id

        # Register with both IDs
        operations_service.register_remote_proxy(
            backend_operation_id=backend_op_id,
            proxy=mock_proxy,
            host_operation_id=host_op_id,
        )

        # Start operation
        await operations_service.start_operation(backend_op_id, task=None)

        # Mock host response
        mock_proxy.get_operation.return_value = {
            "operation_id": host_op_id,  # Host returns its own ID
            "status": "running",  # lowercase - matches OperationStatus enum
            "progress": {"percentage": 25.0},
        }
        mock_proxy.get_metrics.return_value = ([], 0)

        # Invalidate cache
        operations_service._last_refresh[backend_op_id] = 0

        # ACT: Query using BACKEND operation ID
        result = await operations_service.get_operation(backend_op_id)

        # ASSERT: Backend queried host using HOST operation ID
        mock_proxy.get_operation.assert_called_with(host_op_id)

        # But result still has backend operation ID
        assert result.operation_id == backend_op_id

    @pytest.mark.asyncio
    async def test_completion_discovered_when_client_queries(
        self, operations_service, mock_proxy
    ):
        """
        Test that completion is discovered when client queries backend,
        not through background polling.
        """
        # ARRANGE
        backend_op_id = "op_training_backend"
        host_op_id = "host_training_session"

        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata={},
        )
        backend_op_id = operation.operation_id

        operations_service.register_remote_proxy(
            backend_operation_id=backend_op_id,
            proxy=mock_proxy,
            host_operation_id=host_op_id,
        )

        await operations_service.start_operation(backend_op_id, task=None)

        # First query: Host returns RUNNING
        mock_proxy.get_operation.return_value = {
            "operation_id": host_op_id,
            "status": "running",  # lowercase - matches OperationStatus enum
            "progress": {"percentage": 50.0},
        }
        mock_proxy.get_metrics.return_value = ([], 0)
        operations_service._last_refresh[backend_op_id] = 0

        result1 = await operations_service.get_operation(backend_op_id)
        assert result1.status == OperationStatus.RUNNING

        # Second query: Host returns COMPLETED
        mock_proxy.get_operation.return_value = {
            "operation_id": host_op_id,
            "status": "completed",  # lowercase - matches OperationStatus enum
            "progress": {"percentage": 100.0},
        }
        operations_service._last_refresh[backend_op_id] = 0

        result2 = await operations_service.get_operation(backend_op_id)

        # ASSERT: Backend detected completion via client query
        assert result2.status == OperationStatus.COMPLETED
        assert result2.progress.percentage == 100.0


@pytest.mark.skip(reason="Integration test - requires refactored _run_host_training()")
class TestRunHostTrainingRefactored:
    """
    Integration tests for refactored _run_host_training() method.

    These tests will pass once _run_host_training() is refactored to:
    1. NOT create HostSessionManager
    2. NOT create ProgressBridge
    3. Register OperationServiceProxy instead
    4. Return immediately (no waiting)
    """

    @pytest.mark.asyncio
    async def test_run_host_training_registers_proxy_and_returns_immediately(self):
        """
        Test that _run_host_training() registers proxy and returns immediately,
        without creating orchestrator or waiting for completion.
        """
        # TODO: Implement once _run_host_training() is refactored
        pass

    @pytest.mark.asyncio
    async def test_run_host_training_no_bridge_created(self):
        """
        Test that _run_host_training() does NOT create ProgressBridge.

        Bridge should only exist on host service, not in backend for host operations.
        """
        # TODO: Implement once _run_host_training() is refactored
        pass
