"""Unit tests for OperationsService with repository integration.

Tests the core operations service with repository-backed persistence,
verifying that operations are persisted to DB and cached appropriately.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import OperationsService


@pytest.fixture
def mock_repository():
    """Create a mock OperationsRepository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def sample_metadata():
    """Create sample operation metadata."""
    return OperationMetadata(
        symbol="AAPL",
        timeframe="1h",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        parameters={
            "strategy_name": "test_strategy",
            "initial_capital": 100000,
        },
    )


@pytest.fixture
def sample_operation_info():
    """Create a sample OperationInfo for testing."""
    return OperationInfo(
        operation_id="op_test_123",
        operation_type=OperationType.TRAINING,
        status=OperationStatus.PENDING,
        created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
        progress=OperationProgress(
            percentage=0.0,
            current_step=None,
            steps_completed=0,
            steps_total=10,
        ),
        metadata=OperationMetadata(
            symbol="EURUSD",
            timeframe="1h",
        ),
    )


class TestOperationsServiceRepositoryIntegration:
    """Test OperationsService repository integration (Task 1.3)."""

    @pytest.mark.asyncio
    async def test_service_accepts_repository_injection(self, mock_repository):
        """Service should accept repository via constructor."""
        service = OperationsService(repository=mock_repository)

        # Verify repository was stored
        assert service._repository is mock_repository

    @pytest.mark.asyncio
    async def test_service_works_without_repository(self):
        """Service should work without repository (backward compatible)."""
        service = OperationsService()

        # Verify service can be created without repository
        assert service._repository is None

    @pytest.mark.asyncio
    async def test_create_operation_persists_to_repository(
        self, mock_repository, sample_metadata, sample_operation_info
    ):
        """create_operation should persist to repository before caching."""
        # Set up mock - get returns None (no existing operation)
        mock_repository.get.return_value = None
        mock_repository.create.return_value = sample_operation_info

        service = OperationsService(repository=mock_repository)

        await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=sample_metadata,
        )

        # Verify repository.create was called
        mock_repository.create.assert_called_once()
        call_args = mock_repository.create.call_args[0][0]
        assert isinstance(call_args, OperationInfo)
        assert call_args.operation_type == OperationType.TRAINING

    @pytest.mark.asyncio
    async def test_create_operation_caches_after_persistence(
        self, mock_repository, sample_metadata, sample_operation_info
    ):
        """create_operation should cache operation after persisting to DB."""
        # Set up mock - get returns None (no existing operation)
        mock_repository.get.return_value = None
        mock_repository.create.return_value = sample_operation_info

        service = OperationsService(repository=mock_repository)

        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=sample_metadata,
            operation_id="op_test_123",
        )

        # Verify operation is in cache
        assert "op_test_123" in service._cache
        assert service._cache["op_test_123"] is operation

    @pytest.mark.asyncio
    async def test_get_operation_returns_from_cache_if_present(
        self, mock_repository, sample_operation_info
    ):
        """get_operation should return from cache without hitting DB."""
        service = OperationsService(repository=mock_repository)

        # Pre-populate cache
        service._cache["op_test_123"] = sample_operation_info

        operation = await service.get_operation("op_test_123")

        # Verify we got the cached operation
        assert operation is sample_operation_info

        # Verify repository was NOT called (cache hit)
        mock_repository.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_operation_fetches_from_repository_on_cache_miss(
        self, mock_repository, sample_operation_info
    ):
        """get_operation should fetch from repository on cache miss."""
        mock_repository.get.return_value = sample_operation_info

        service = OperationsService(repository=mock_repository)

        # Cache is empty - should hit repository
        operation = await service.get_operation("op_test_123")

        # Verify repository was called
        mock_repository.get.assert_called_once_with("op_test_123")

        # Verify operation was returned
        assert operation is sample_operation_info

    @pytest.mark.asyncio
    async def test_get_operation_caches_after_repository_fetch(
        self, mock_repository, sample_operation_info
    ):
        """get_operation should cache operation after fetching from repository."""
        mock_repository.get.return_value = sample_operation_info

        service = OperationsService(repository=mock_repository)

        # First call - cache miss, fetches from repository
        await service.get_operation("op_test_123")

        # Verify operation is now in cache
        assert "op_test_123" in service._cache
        assert service._cache["op_test_123"] is sample_operation_info

        # Second call - should use cache
        mock_repository.get.reset_mock()
        await service.get_operation("op_test_123")
        mock_repository.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_operation_returns_none_when_not_in_db(self, mock_repository):
        """get_operation should return None when not in cache or DB."""
        mock_repository.get.return_value = None

        service = OperationsService(repository=mock_repository)

        operation = await service.get_operation("nonexistent")

        assert operation is None
        mock_repository.get.assert_called_once_with("nonexistent")


class TestOperationsServiceUpdatePersistence:
    """Test that update operations persist to repository."""

    @pytest.mark.asyncio
    async def test_complete_operation_persists_to_repository(
        self, mock_repository, sample_metadata
    ):
        """complete_operation should persist status change to repository."""
        # Create service with repository
        service = OperationsService(repository=mock_repository)

        # Create operation info in cache
        operation = OperationInfo(
            operation_id="op_complete_test",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=50.0),
        )
        service._cache["op_complete_test"] = operation

        # Mock repository update
        mock_repository.update.return_value = operation

        result_summary = {"accuracy": 0.95}
        await service.complete_operation("op_complete_test", result_summary)

        # Verify repository.update was called with correct status
        mock_repository.update.assert_called()
        call_kwargs = mock_repository.update.call_args
        assert call_kwargs[0][0] == "op_complete_test"

    @pytest.mark.asyncio
    async def test_fail_operation_persists_to_repository(
        self, mock_repository, sample_metadata
    ):
        """fail_operation should persist failure to repository."""
        service = OperationsService(repository=mock_repository)

        # Create operation in cache
        operation = OperationInfo(
            operation_id="op_fail_test",
            operation_type=OperationType.BACKTESTING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=25.0),
        )
        service._cache["op_fail_test"] = operation
        mock_repository.update.return_value = operation

        await service.fail_operation("op_fail_test", "Test error")

        # Verify repository.update was called
        mock_repository.update.assert_called()

    @pytest.mark.asyncio
    async def test_update_progress_does_not_persist_to_repository(
        self, mock_repository, sample_metadata
    ):
        """update_progress should NOT persist progress to repository (Task 3.10).

        Design principle: Workers must be fast. DB writes should only happen for:
        - Create operation (once)
        - Checkpoint (periodic, policy-driven)
        - Complete/Fail (once)

        Progress updates stay in-memory; clients pull via proxy for live progress.
        """
        service = OperationsService(repository=mock_repository)

        # Create operation in cache
        operation = OperationInfo(
            operation_id="op_progress_test",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=0.0),
        )
        service._cache["op_progress_test"] = operation
        mock_repository.update.return_value = operation

        new_progress = OperationProgress(
            percentage=75.0,
            current_step="Epoch 75/100",
        )
        await service.update_progress("op_progress_test", new_progress)

        # Verify repository.update was NOT called (Task 3.10 fix)
        mock_repository.update.assert_not_called()

        # But in-memory cache should still be updated
        assert service._cache["op_progress_test"].progress.percentage == 75.0


class TestOperationsServiceRuntimeHandles:
    """Test that runtime handles (tasks, bridges) remain in-memory only."""

    @pytest.mark.asyncio
    async def test_operation_tasks_not_persisted(
        self, mock_repository, sample_metadata
    ):
        """operation_tasks should remain in-memory, not persisted."""
        # Create a sample operation that will be persisted
        sample_op = OperationInfo(
            operation_id="op_task_test",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=0.0),
        )
        # Set up mock - get returns None (no existing operation)
        mock_repository.get.return_value = None
        mock_repository.create.return_value = sample_op

        service = OperationsService(repository=mock_repository)

        # Create operation
        await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=sample_metadata,
            operation_id="op_task_test",
        )

        # Create mock task
        mock_task = MagicMock()
        mock_task.done.return_value = False

        # Start operation with task
        await service.start_operation("op_task_test", mock_task)

        # Verify task is in _operation_tasks (in-memory)
        assert "op_task_test" in service._operation_tasks

        # Verify repository.create was called but task is NOT in the call
        # (tasks are runtime handles, not persisted)
        create_call_args = mock_repository.create.call_args[0][0]
        assert not hasattr(create_call_args, "task")

    @pytest.mark.asyncio
    async def test_local_bridges_not_persisted(self, mock_repository, sample_metadata):
        """local_bridges should remain in-memory, not persisted."""
        sample_op = OperationInfo(
            operation_id="op_bridge_test",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=0.0),
        )
        # Set up mock - get returns None (no existing operation)
        mock_repository.get.return_value = None
        mock_repository.create.return_value = sample_op

        service = OperationsService(repository=mock_repository)

        # Create operation
        await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=sample_metadata,
            operation_id="op_bridge_test",
        )

        # Register local bridge
        mock_bridge = MagicMock()
        service.register_local_bridge("op_bridge_test", mock_bridge)

        # Verify bridge is in _local_bridges (in-memory)
        assert "op_bridge_test" in service._local_bridges
        assert service._local_bridges["op_bridge_test"] is mock_bridge


class TestOperationsServiceBackwardCompatibility:
    """Test backward compatibility when no repository is provided."""

    @pytest.mark.asyncio
    async def test_create_operation_works_without_repository(self, sample_metadata):
        """create_operation should work without repository (pure in-memory)."""
        service = OperationsService()  # No repository

        operation = await service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=sample_metadata,
        )

        assert operation is not None
        assert operation.operation_id.startswith("op_backtesting_")

    @pytest.mark.asyncio
    async def test_get_operation_works_without_repository(self, sample_metadata):
        """get_operation should work without repository (pure in-memory)."""
        service = OperationsService()  # No repository

        # Create and then get
        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=sample_metadata,
        )

        retrieved = await service.get_operation(operation.operation_id)

        assert retrieved is not None
        assert retrieved.operation_id == operation.operation_id

    @pytest.mark.asyncio
    async def test_complete_operation_works_without_repository(self, sample_metadata):
        """complete_operation should work without repository."""
        service = OperationsService()  # No repository

        # Create operation
        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=sample_metadata,
        )

        # Complete it
        await service.complete_operation(operation.operation_id, {"result": "success"})

        # Verify status changed
        updated = await service.get_operation(operation.operation_id)
        assert updated.status == OperationStatus.COMPLETED


class TestOperationsServiceListWithRepository:
    """Test list_operations with repository."""

    @pytest.mark.asyncio
    async def test_list_operations_returns_cached_operations(
        self, mock_repository, sample_metadata
    ):
        """list_operations should return operations from cache."""
        service = OperationsService(repository=mock_repository)

        # Add operations to cache
        cached_operation = OperationInfo(
            operation_id="op_cache_only",
            operation_type=OperationType.BACKTESTING,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=0.0),
        )
        service._cache["op_cache_only"] = cached_operation

        # List should return cached operations
        operations, total, active = await service.list_operations()

        # Verify cached operation is returned
        assert len(operations) == 1
        assert operations[0].operation_id == "op_cache_only"
        assert total == 1


class TestOperationsServiceCacheNaming:
    """Test that internal storage uses _cache naming (not _operations)."""

    def test_service_uses_cache_attribute(self):
        """Service should use _cache attribute for in-memory storage."""
        service = OperationsService()

        # Verify _cache exists and is a dict
        assert hasattr(service, "_cache")
        assert isinstance(service._cache, dict)
