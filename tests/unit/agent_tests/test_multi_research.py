"""Tests for multi-research coordinator functionality.

Task 1.1: Tests for _get_all_active_research_ops() method.
Task 1.2: Tests for _get_concurrency_limit() method.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service for testing."""
    service = AsyncMock()

    # Track operations in memory
    operations: dict[str, OperationInfo] = {}
    operation_counter = 0

    def create_op(
        operation_type,
        metadata=None,
        parent_operation_id=None,
        status=OperationStatus.PENDING,
    ):
        """Create operation helper."""
        nonlocal operation_counter
        operation_counter += 1
        op_id = f"op_{operation_type.value}_{operation_counter}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=status,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or OperationMetadata(),
            parent_operation_id=parent_operation_id,
        )
        operations[op_id] = op
        return op

    async def async_list_operations(
        operation_type=None, status=None, limit=100, offset=0, active_only=False
    ):
        """List operations with filtering."""
        filtered = list(operations.values())

        if operation_type:
            filtered = [op for op in filtered if op.operation_type == operation_type]

        if status:
            filtered = [op for op in filtered if op.status == status]

        if active_only:
            filtered = [
                op
                for op in filtered
                if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
            ]

        # Sort by created_at descending
        filtered.sort(key=lambda op: op.created_at, reverse=True)

        total_count = len(filtered)
        active_count = len(
            [
                op
                for op in operations.values()
                if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
            ]
        )

        return filtered[offset : offset + limit], total_count, active_count

    service.list_operations = async_list_operations
    service._operations = operations
    service._create_op = create_op

    return service


class TestGetAllActiveResearchOps:
    """Tests for _get_all_active_research_ops() method - Task 1.1."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_active_researches(
        self, mock_operations_service
    ):
        """Returns empty list when no active researches exist."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        result = await service._get_all_active_research_ops()

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_single_operation_when_one_active(
        self, mock_operations_service
    ):
        """Returns list with single operation when one active research exists."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create one running research
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op.operation_id

    @pytest.mark.asyncio
    async def test_returns_multiple_operations_when_several_active(
        self, mock_operations_service
    ):
        """Returns list with all active operations when multiple researches active."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create three running researches
        op1 = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        op2 = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        op3 = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 3
        result_ids = {op.operation_id for op in result}
        assert result_ids == {op1.operation_id, op2.operation_id, op3.operation_id}

    @pytest.mark.asyncio
    async def test_includes_running_status(self, mock_operations_service):
        """Includes operations with RUNNING status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].status == OperationStatus.RUNNING

    @pytest.mark.asyncio
    async def test_includes_resuming_status(self, mock_operations_service):
        """Includes operations with RESUMING status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RESUMING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].status == OperationStatus.RESUMING

    @pytest.mark.asyncio
    async def test_includes_pending_status(self, mock_operations_service):
        """Includes operations with PENDING status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.PENDING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].status == OperationStatus.PENDING

    @pytest.mark.asyncio
    async def test_includes_all_active_statuses(self, mock_operations_service):
        """Includes operations with RUNNING, RESUMING, and PENDING statuses."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create one of each status
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RESUMING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.PENDING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 3
        statuses = {op.status for op in result}
        assert statuses == {
            OperationStatus.RUNNING,
            OperationStatus.RESUMING,
            OperationStatus.PENDING,
        }

    @pytest.mark.asyncio
    async def test_excludes_completed_operations(self, mock_operations_service):
        """Excludes operations with COMPLETED status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create completed operation
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.COMPLETED,
        )
        # Create running operation
        op_active = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op_active.operation_id

    @pytest.mark.asyncio
    async def test_excludes_failed_operations(self, mock_operations_service):
        """Excludes operations with FAILED status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create failed operation
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.FAILED,
        )
        # Create running operation
        op_active = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op_active.operation_id

    @pytest.mark.asyncio
    async def test_excludes_cancelled_operations(self, mock_operations_service):
        """Excludes operations with CANCELLED status."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create cancelled operation
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.CANCELLED,
        )
        # Create running operation
        op_active = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op_active.operation_id

    @pytest.mark.asyncio
    async def test_only_returns_agent_research_operations(
        self, mock_operations_service
    ):
        """Only returns AGENT_RESEARCH operations, not other types."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create operations of different types
        mock_operations_service._create_op(
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.BACKTESTING,
            status=OperationStatus.RUNNING,
        )
        op_research = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_all_active_research_ops()

        assert len(result) == 1
        assert result[0].operation_id == op_research.operation_id
        assert result[0].operation_type == OperationType.AGENT_RESEARCH


class TestGetActiveResearchOpBackwardCompatibility:
    """Test that existing _get_active_research_op() still works after adding new method."""

    @pytest.mark.asyncio
    async def test_get_active_research_op_still_returns_single_operation(
        self, mock_operations_service
    ):
        """Existing method should still return a single operation."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        # Create a running research
        op = mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        result = await service._get_active_research_op()

        assert result is not None
        assert result.operation_id == op.operation_id

    @pytest.mark.asyncio
    async def test_get_active_research_op_still_returns_none_when_no_active(
        self, mock_operations_service
    ):
        """Existing method should still return None when no active operations."""
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService(operations_service=mock_operations_service)

        result = await service._get_active_research_op()

        assert result is None


class TestGetConcurrencyLimit:
    """Tests for _get_concurrency_limit() method - Task 1.2."""

    @pytest.fixture
    def mock_worker_registry(self):
        """Create a mock worker registry."""
        from unittest.mock import MagicMock

        from ktrdr.api.models.workers import WorkerEndpoint, WorkerStatus, WorkerType

        registry = MagicMock()
        workers: dict[WorkerType, list[WorkerEndpoint]] = {
            WorkerType.TRAINING: [],
            WorkerType.BACKTESTING: [],
        }

        def list_workers(worker_type=None, status=None):
            if worker_type is None:
                all_workers = []
                for w_list in workers.values():
                    all_workers.extend(w_list)
                return all_workers
            return workers.get(worker_type, [])

        def add_worker(worker_type: WorkerType, worker_id: str):
            """Helper to add a worker for testing."""
            worker = WorkerEndpoint(
                worker_id=worker_id,
                worker_type=worker_type,
                endpoint_url=f"http://localhost:500{len(workers[worker_type])}",
                status=WorkerStatus.AVAILABLE,
            )
            workers[worker_type].append(worker)
            return worker

        registry.list_workers = list_workers
        registry._workers = workers
        registry._add_worker = add_worker

        return registry

    def test_returns_override_value_when_env_var_set(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Returns override value when AGENT_MAX_CONCURRENT_RESEARCHES is set."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "10")

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = service._get_concurrency_limit()

        assert result == 10

    def test_calculates_from_workers_when_no_override(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Calculates limit from workers when no override is set."""
        from unittest.mock import patch

        from ktrdr.api.models.workers import WorkerType
        from ktrdr.api.services.agent_service import AgentService

        # Remove override env var if set
        monkeypatch.delenv("AGENT_MAX_CONCURRENT_RESEARCHES", raising=False)

        # Add 2 training workers and 3 backtest workers
        mock_worker_registry._add_worker(WorkerType.TRAINING, "training-1")
        mock_worker_registry._add_worker(WorkerType.TRAINING, "training-2")
        mock_worker_registry._add_worker(WorkerType.BACKTESTING, "backtest-1")
        mock_worker_registry._add_worker(WorkerType.BACKTESTING, "backtest-2")
        mock_worker_registry._add_worker(WorkerType.BACKTESTING, "backtest-3")

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = service._get_concurrency_limit()

        # 2 training + 3 backtest + 1 buffer = 6
        assert result == 6

    def test_applies_buffer_correctly(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Applies buffer from AGENT_CONCURRENCY_BUFFER env var."""
        from unittest.mock import patch

        from ktrdr.api.models.workers import WorkerType
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.delenv("AGENT_MAX_CONCURRENT_RESEARCHES", raising=False)
        monkeypatch.setenv("AGENT_CONCURRENCY_BUFFER", "3")

        # Add 2 workers total
        mock_worker_registry._add_worker(WorkerType.TRAINING, "training-1")
        mock_worker_registry._add_worker(WorkerType.BACKTESTING, "backtest-1")

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = service._get_concurrency_limit()

        # 1 training + 1 backtest + 3 buffer = 5
        assert result == 5

    def test_returns_minimum_1_when_no_workers_registered(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Returns minimum of 1 when no workers are registered."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.delenv("AGENT_MAX_CONCURRENT_RESEARCHES", raising=False)
        monkeypatch.delenv("AGENT_CONCURRENCY_BUFFER", raising=False)

        # No workers added - registry is empty

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = service._get_concurrency_limit()

        # 0 workers + 1 buffer = 1, and min is 1
        assert result == 1

    def test_override_zero_is_not_treated_as_override(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Setting override to '0' should calculate from workers, not use 0."""
        from unittest.mock import patch

        from ktrdr.api.models.workers import WorkerType
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "0")

        # Add workers
        mock_worker_registry._add_worker(WorkerType.TRAINING, "training-1")
        mock_worker_registry._add_worker(WorkerType.BACKTESTING, "backtest-1")

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = service._get_concurrency_limit()

        # Should calculate: 1 + 1 + 1 (default buffer) = 3
        assert result == 3

    def test_invalid_override_falls_back_to_calculation(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Invalid override value (non-integer) falls back to calculation."""
        from unittest.mock import patch

        from ktrdr.api.models.workers import WorkerType
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "invalid")

        # Add workers
        mock_worker_registry._add_worker(WorkerType.TRAINING, "training-1")

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = service._get_concurrency_limit()

        # Should calculate: 1 training + 0 backtest + 1 buffer = 2
        assert result == 2

    def test_default_buffer_is_1(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Default buffer is 1 when AGENT_CONCURRENCY_BUFFER not set."""
        from unittest.mock import patch

        from ktrdr.api.models.workers import WorkerType
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.delenv("AGENT_MAX_CONCURRENT_RESEARCHES", raising=False)
        monkeypatch.delenv("AGENT_CONCURRENCY_BUFFER", raising=False)

        # Add 1 training worker
        mock_worker_registry._add_worker(WorkerType.TRAINING, "training-1")

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = service._get_concurrency_limit()

        # 1 training + 0 backtest + 1 default buffer = 2
        assert result == 2
