"""Tests for multi-research coordinator functionality.

Task 1.1: Tests for _get_all_active_research_ops() method.
Task 1.2: Tests for _get_concurrency_limit() method.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

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

    def test_invalid_override_raises_validation_error(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Invalid override value (non-integer) raises validation error.

        After config system M5 migration, settings use Pydantic validation
        which fails fast on invalid values rather than silently falling back.
        """
        from pydantic import ValidationError

        from ktrdr.config import clear_settings_cache

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "invalid")
        clear_settings_cache()

        # Pydantic should reject invalid integer value
        with pytest.raises(ValidationError):
            from ktrdr.config.settings import get_agent_settings

            get_agent_settings()

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


class TestTriggerCapacityCheck:
    """Tests for trigger() capacity check - Task 1.3."""

    @pytest.fixture
    def mock_worker_registry(self):
        """Create a mock worker registry for capacity tests."""
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

    @pytest.fixture(autouse=True)
    def use_stub_workers(self, monkeypatch):
        """Use stub workers to avoid real API calls in unit tests."""
        monkeypatch.setenv("USE_STUB_WORKERS", "true")
        monkeypatch.setenv("STUB_WORKER_FAST", "true")

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup_coordinator(self):
        """Cancel leaked background coordinator tasks after each test."""
        yield
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task() and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass  # Best-effort cleanup: ignore errors from cancelled tasks

    @pytest.fixture(autouse=True)
    def mock_budget(self):
        """Mock budget tracker to allow triggers in tests."""
        from unittest.mock import MagicMock, patch

        mock_tracker = MagicMock()
        mock_tracker.can_spend.return_value = (True, None)

        with patch(
            "ktrdr.api.services.agent_service.get_budget_tracker",
            return_value=mock_tracker,
        ):
            yield mock_tracker

    @pytest.mark.asyncio
    async def test_first_trigger_succeeds(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """First trigger succeeds when no active researches (count 0)."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        # Set limit to 5
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "5")

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger()

        assert result["triggered"] is True
        assert "operation_id" in result

    @pytest.mark.asyncio
    async def test_second_trigger_succeeds_under_capacity(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Second trigger succeeds when under capacity (count 1, limit 5)."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        # Set limit to 5
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "5")

        # Create one running research
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger()

        # Should succeed - we're at 1/5 capacity
        assert result["triggered"] is True
        assert "operation_id" in result

    @pytest.mark.asyncio
    async def test_trigger_at_capacity_fails_with_at_capacity_reason(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Trigger at capacity fails with 'at_capacity' reason."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        # Set limit to 2
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "2")

        # Create 2 running researches (at capacity)
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger()

        assert result["triggered"] is False
        assert result["reason"] == "at_capacity"

    @pytest.mark.asyncio
    async def test_at_capacity_response_includes_active_count(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """At-capacity response includes active_count field."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        # Set limit to 2
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "2")

        # Create 2 running researches
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger()

        assert "active_count" in result
        assert result["active_count"] == 2

    @pytest.mark.asyncio
    async def test_at_capacity_response_includes_limit(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """At-capacity response includes limit field."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        # Set limit to 3
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "3")

        # Create 3 running researches
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger()

        assert "limit" in result
        assert result["limit"] == 3

    @pytest.mark.asyncio
    async def test_at_capacity_response_includes_message(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """At-capacity response includes descriptive message."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        # Set limit to 2
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "2")

        # Create 2 running researches
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger()

        assert "message" in result
        # Message should mention capacity
        assert "capacity" in result["message"].lower() or "2/2" in result["message"]

    @pytest.mark.asyncio
    async def test_budget_check_still_happens_first(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Budget check still happens before capacity check."""
        from unittest.mock import MagicMock, patch

        from ktrdr.api.services.agent_service import AgentService

        # Set limit to 2
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "2")

        # Create 2 running researches (at capacity)
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        # Mock budget as exhausted
        mock_tracker = MagicMock()
        mock_tracker.can_spend.return_value = (False, "budget_exhausted")

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            with patch(
                "ktrdr.api.services.agent_service.get_budget_tracker",
                return_value=mock_tracker,
            ):
                service = AgentService(operations_service=mock_operations_service)
                result = await service.trigger()

        # Should return budget_exhausted, not at_capacity
        assert result["triggered"] is False
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_trigger_succeeds_when_one_below_capacity(
        self, mock_operations_service, mock_worker_registry, monkeypatch
    ):
        """Trigger succeeds when exactly one below capacity."""
        from unittest.mock import patch

        from ktrdr.api.services.agent_service import AgentService

        # Set limit to 3
        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "3")

        # Create 2 running researches (one below capacity)
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        mock_operations_service._create_op(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )

        with patch(
            "ktrdr.api.endpoints.workers.get_worker_registry",
            return_value=mock_worker_registry,
        ):
            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger()

        # Should succeed - we're at 2/3 capacity
        assert result["triggered"] is True


class TestMultiResearchCoordinatorLoop:
    """Tests for multi-research coordinator loop - Task 1.4."""

    @pytest.fixture
    def mock_ops_service_for_worker(self):
        """Create a mock operations service for research worker testing."""
        service = AsyncMock()
        operations: dict[str, OperationInfo] = {}

        async def async_get_operation(operation_id):
            return operations.get(operation_id)

        async def async_list_operations(
            operation_type=None, status=None, limit=100, offset=0, active_only=False
        ):
            """List operations with filtering."""
            filtered = list(operations.values())

            if operation_type:
                filtered = [
                    op for op in filtered if op.operation_type == operation_type
                ]

            if status:
                filtered = [op for op in filtered if op.status == status]

            return filtered, len(filtered), len(filtered)

        async def async_update_progress(operation_id, progress):
            pass

        service.get_operation = async_get_operation
        service.list_operations = async_list_operations
        service.update_progress = async_update_progress
        service._operations = operations

        return service

    @pytest.fixture
    def mock_design_worker(self):
        """Create a mock design worker."""
        worker = AsyncMock()
        worker.run.return_value = {
            "success": True,
            "strategy_name": "test_strategy",
            "strategy_path": "/tmp/test_strategy.yaml",
        }
        return worker

    @pytest.fixture
    def mock_assessment_worker(self):
        """Create a mock assessment worker."""
        worker = AsyncMock()
        worker.run.return_value = {
            "success": True,
            "verdict": "promising",
        }
        return worker

    @pytest.mark.asyncio
    async def test_get_active_research_operations_returns_correct_operations(
        self, mock_ops_service_for_worker
    ):
        """_get_active_research_operations() returns all active AGENT_RESEARCH operations."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_worker,
            design_worker=AsyncMock(),
            assessment_worker=AsyncMock(),
        )

        # Add some operations
        op1 = OperationInfo(
            operation_id="op_1",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        op2 = OperationInfo(
            operation_id="op_2",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        mock_ops_service_for_worker._operations["op_1"] = op1
        mock_ops_service_for_worker._operations["op_2"] = op2

        result = await worker._get_active_research_operations()

        assert len(result) == 2
        assert {op.operation_id for op in result} == {"op_1", "op_2"}

    @pytest.mark.asyncio
    async def test_get_active_research_operations_excludes_completed(
        self, mock_ops_service_for_worker
    ):
        """_get_active_research_operations() excludes COMPLETED operations."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_worker,
            design_worker=AsyncMock(),
            assessment_worker=AsyncMock(),
        )

        # Add completed and running operations
        op_completed = OperationInfo(
            operation_id="op_completed",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(parameters={"phase": "done"}),
        )
        op_running = OperationInfo(
            operation_id="op_running",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_ops_service_for_worker._operations["op_completed"] = op_completed
        mock_ops_service_for_worker._operations["op_running"] = op_running

        result = await worker._get_active_research_operations()

        assert len(result) == 1
        assert result[0].operation_id == "op_running"

    @pytest.mark.asyncio
    async def test_advance_research_calls_correct_phase_handler_idle(
        self, mock_ops_service_for_worker, mock_design_worker, mock_assessment_worker
    ):
        """_advance_research() calls _start_design for idle phase."""
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_worker,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        op = OperationInfo(
            operation_id="op_test",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        mock_ops_service_for_worker._operations["op_test"] = op

        with patch.object(worker, "_start_design") as mock_start_design:
            await worker._advance_research(op)
            mock_start_design.assert_called_once_with("op_test")

    @pytest.mark.asyncio
    async def test_advance_research_calls_correct_phase_handler_designing(
        self, mock_ops_service_for_worker, mock_design_worker, mock_assessment_worker
    ):
        """_advance_research() calls _handle_designing_phase for designing phase."""
        import asyncio
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_worker,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        op = OperationInfo(
            operation_id="op_test",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(
                parameters={"phase": "designing", "design_op_id": "op_design_1"}
            ),
        )
        mock_ops_service_for_worker._operations["op_test"] = op

        # Add mock child operation
        child_op = OperationInfo(
            operation_id="op_design_1",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )
        mock_ops_service_for_worker._operations["op_design_1"] = child_op

        # Add a task to _child_tasks to prevent orphan detection
        # (M6 restart recovery checks for orphaned tasks)
        async def fake_task():
            await asyncio.sleep(100)

        task = asyncio.create_task(fake_task())
        worker._child_tasks["op_test"] = task

        try:
            with patch.object(worker, "_handle_designing_phase") as mock_handler:
                await worker._advance_research(op)
                mock_handler.assert_called_once()
                # First arg is operation_id, second is child_op
                call_args = mock_handler.call_args
                assert call_args[0][0] == "op_test"
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected during test cleanup: task was explicitly cancelled

    @pytest.mark.asyncio
    async def test_run_exits_when_no_active_operations(
        self, mock_ops_service_for_worker, mock_design_worker, mock_assessment_worker
    ):
        """run() exits loop when no active operations."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_worker,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0.01  # Fast polling for test

        # No operations - should exit immediately
        await worker.run()  # Should not hang

    @pytest.mark.asyncio
    async def test_run_processes_multiple_operations_in_one_cycle(
        self, mock_ops_service_for_worker, mock_design_worker, mock_assessment_worker
    ):
        """run() advances all active operations in one loop iteration."""
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_worker,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0.01

        # Create two operations that will complete on first advance
        op1 = OperationInfo(
            operation_id="op_1",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        op2 = OperationInfo(
            operation_id="op_2",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Track which operations were advanced
        advanced_ops = []

        call_count = [0]

        async def mock_advance_research(op):
            advanced_ops.append(op.operation_id)
            # After first round, mark operations as completed so loop exits
            call_count[0] += 1
            if call_count[0] >= 2:
                # Remove from operations to simulate completion
                mock_ops_service_for_worker._operations.clear()

        mock_ops_service_for_worker._operations["op_1"] = op1
        mock_ops_service_for_worker._operations["op_2"] = op2

        with patch.object(
            worker, "_advance_research", side_effect=mock_advance_research
        ):
            await worker.run()

        # Both operations should have been advanced
        assert "op_1" in advanced_ops
        assert "op_2" in advanced_ops

    @pytest.mark.asyncio
    async def test_run_continues_after_one_research_completes(
        self, mock_ops_service_for_worker, mock_design_worker, mock_assessment_worker
    ):
        """run() continues processing after one research completes."""
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_worker,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0.01

        op1 = OperationInfo(
            operation_id="op_1",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )
        op2 = OperationInfo(
            operation_id="op_2",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        mock_ops_service_for_worker._operations["op_1"] = op1
        mock_ops_service_for_worker._operations["op_2"] = op2

        advance_calls = []
        loop_iterations = [0]

        async def mock_advance_research(op):
            advance_calls.append(op.operation_id)
            loop_iterations[0] += 1

            # On first iteration: op_1 completes (remove it)
            if op.operation_id == "op_1" and loop_iterations[0] <= 2:
                del mock_ops_service_for_worker._operations["op_1"]

            # On second iteration: op_2 completes (remove it)
            if op.operation_id == "op_2" and loop_iterations[0] > 2:
                del mock_ops_service_for_worker._operations["op_2"]

        with patch.object(
            worker, "_advance_research", side_effect=mock_advance_research
        ):
            await worker.run()

        # op_1 should have been called once, op_2 should have been called twice
        assert advance_calls.count("op_1") >= 1
        assert advance_calls.count("op_2") >= 1

    @pytest.mark.asyncio
    async def test_run_no_operation_id_parameter(
        self, mock_ops_service_for_worker, mock_design_worker, mock_assessment_worker
    ):
        """run() takes no operation_id parameter (discovers ops itself)."""
        import inspect

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_worker,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Check that run() signature has no required parameters
        sig = inspect.signature(worker.run)
        required_params = [
            p
            for p in sig.parameters.values()
            if p.default == inspect.Parameter.empty and p.name != "self"
        ]
        assert len(required_params) == 0, "run() should not require any parameters"


class TestOperationCompletionHandling:
    """Tests for Task 1.7: Operation completion inside the loop."""

    @pytest.fixture
    def mock_ops_service_for_completion(self):
        """Create mock operations service with complete_operation tracking."""
        service = AsyncMock()
        operations: dict[str, OperationInfo] = {}

        async def list_operations(operation_type=None, status=None, **kwargs):
            filtered = list(operations.values())
            if operation_type:
                filtered = [
                    op for op in filtered if op.operation_type == operation_type
                ]
            if status:
                filtered = [op for op in filtered if op.status == status]
            return filtered, len(filtered), len(filtered)

        async def get_operation(op_id):
            return operations.get(op_id)

        service.list_operations.side_effect = list_operations
        service.get_operation.side_effect = get_operation
        service.complete_operation = AsyncMock()
        service.fail_operation = AsyncMock()
        service.update_progress = AsyncMock()
        service._operations = operations

        return service

    @pytest.fixture
    def mock_design_worker(self):
        """Create a mock design worker."""
        worker = AsyncMock()
        worker.run.return_value = {
            "success": True,
            "strategy_name": "test_strategy",
            "strategy_path": "/tmp/test_strategy.yaml",
        }
        return worker

    @pytest.fixture
    def mock_assessment_worker(self):
        """Create a mock assessment worker."""
        worker = AsyncMock()
        worker.run.return_value = {
            "success": True,
            "verdict": "promising",
        }
        return worker

    @pytest.mark.asyncio
    async def test_cycle_duration_recorded_from_created_at(
        self,
        mock_ops_service_for_completion,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Cycle duration is calculated from operation created_at timestamp."""
        from datetime import timedelta
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_completion,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Create operation with created_at 60 seconds ago
        created_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        parent_op = OperationInfo(
            operation_id="op_test",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=created_time,
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "assessment_op_id": "op_assess",
                    "strategy_name": "test_strategy",
                    "phase_start_time": 1000.0,
                }
            ),
        )

        # Child operation (assessment) completed
        child_op = OperationInfo(
            operation_id="op_assess",
            operation_type=OperationType.AGENT_ASSESSMENT,
            status=OperationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
            result_summary={
                "verdict": "promising",
                "input_tokens": 100,
                "output_tokens": 50,
            },
        )

        mock_ops_service_for_completion._operations["op_test"] = parent_op
        mock_ops_service_for_completion._operations["op_assess"] = child_op

        # Track duration recorded
        recorded_durations = []

        def mock_record_duration(duration):
            recorded_durations.append(duration)

        with patch(
            "ktrdr.agents.workers.research_worker.record_cycle_duration",
            side_effect=mock_record_duration,
        ):
            await worker._handle_assessing_phase("op_test", child_op)

        # Duration should be recorded and roughly 60 seconds (not 0)
        assert len(recorded_durations) == 1
        assert recorded_durations[0] >= 59.0  # Allow small timing variance
        assert recorded_durations[0] < 120.0  # But not too large

    @pytest.mark.asyncio
    async def test_complete_operation_called_inside_handler(
        self,
        mock_ops_service_for_completion,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """complete_operation is called inside _handle_assessing_phase, not run()."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_completion,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        parent_op = OperationInfo(
            operation_id="op_test",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "assessment_op_id": "op_assess",
                    "strategy_name": "test_strategy",
                    "phase_start_time": 1000.0,
                }
            ),
        )

        child_op = OperationInfo(
            operation_id="op_assess",
            operation_type=OperationType.AGENT_ASSESSMENT,
            status=OperationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
            result_summary={"verdict": "promising"},
        )

        mock_ops_service_for_completion._operations["op_test"] = parent_op
        mock_ops_service_for_completion._operations["op_assess"] = child_op

        # Call the handler directly
        await worker._handle_assessing_phase("op_test", child_op)

        # complete_operation should have been called with the operation_id
        mock_ops_service_for_completion.complete_operation.assert_called_once()
        call_args = mock_ops_service_for_completion.complete_operation.call_args
        assert call_args[0][0] == "op_test"

    @pytest.mark.asyncio
    async def test_cycle_outcome_recorded_per_research(
        self,
        mock_ops_service_for_completion,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Cycle outcome is recorded when each research completes, not at coordinator exit."""
        from unittest.mock import patch

        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_completion,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        parent_op = OperationInfo(
            operation_id="op_test",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "assessment_op_id": "op_assess",
                    "strategy_name": "test_strategy",
                    "phase_start_time": 1000.0,
                }
            ),
        )

        child_op = OperationInfo(
            operation_id="op_assess",
            operation_type=OperationType.AGENT_ASSESSMENT,
            status=OperationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
            result_summary={"verdict": "promising"},
        )

        mock_ops_service_for_completion._operations["op_test"] = parent_op
        mock_ops_service_for_completion._operations["op_assess"] = child_op

        recorded_outcomes = []

        def mock_record_outcome(outcome):
            recorded_outcomes.append(outcome)

        with patch(
            "ktrdr.agents.workers.research_worker.record_cycle_outcome",
            side_effect=mock_record_outcome,
        ):
            await worker._handle_assessing_phase("op_test", child_op)

        # Outcome should be recorded as "completed"
        assert len(recorded_outcomes) == 1
        assert recorded_outcomes[0] == "completed"

    @pytest.mark.asyncio
    async def test_handler_returns_result_for_coordinator_visibility(
        self,
        mock_ops_service_for_completion,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """_handle_assessing_phase returns result dict for logging/visibility."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_ops_service_for_completion,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        parent_op = OperationInfo(
            operation_id="op_test",
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(
                parameters={
                    "phase": "assessing",
                    "assessment_op_id": "op_assess",
                    "strategy_name": "my_strategy",
                    "phase_start_time": 1000.0,
                }
            ),
        )

        child_op = OperationInfo(
            operation_id="op_assess",
            operation_type=OperationType.AGENT_ASSESSMENT,
            status=OperationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
            result_summary={"verdict": "promising"},
        )

        mock_ops_service_for_completion._operations["op_test"] = parent_op
        mock_ops_service_for_completion._operations["op_assess"] = child_op

        result = await worker._handle_assessing_phase("op_test", child_op)

        # Should return completion result
        assert result is not None
        assert result["success"] is True
        assert result["strategy_name"] == "my_strategy"
        assert result["verdict"] == "promising"
