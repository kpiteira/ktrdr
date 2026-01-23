"""Integration tests for multi-research status (M5 Task 5.3).

Verifies that status endpoint correctly returns all active researches
with phases, worker utilization, budget, and capacity information.

Uses mocked services for speed and reliability.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service for integration testing."""
    service = AsyncMock()

    operations: dict[str, OperationInfo] = {}
    operation_counter = 0

    async def async_create_operation(
        operation_type, metadata=None, parent_operation_id=None, is_backend_local=False
    ):
        nonlocal operation_counter
        operation_counter += 1
        op_id = f"op_{operation_type.value}_{operation_counter}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or OperationMetadata(),
            parent_operation_id=parent_operation_id,
        )
        operations[op_id] = op
        return op

    async def async_get_operation(operation_id):
        return operations.get(operation_id)

    async def async_list_operations(
        operation_type=None, status=None, limit=100, offset=0, active_only=False
    ):
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

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.list_operations = async_list_operations
    service._operations = operations

    return service


class TestMultiResearchStatusIntegration:
    """Integration tests for get_status() with multiple researches."""

    @pytest.fixture
    def mock_worker_registry(self):
        """Create a mock worker registry for status tests."""
        from ktrdr.api.models.workers import WorkerStatus, WorkerType

        registry = MagicMock()

        training_worker_1 = MagicMock()
        training_worker_1.status = WorkerStatus.BUSY
        training_worker_2 = MagicMock()
        training_worker_2.status = WorkerStatus.AVAILABLE

        backtest_worker_1 = MagicMock()
        backtest_worker_1.status = WorkerStatus.AVAILABLE

        def mock_list_workers(worker_type=None):
            if worker_type == WorkerType.TRAINING:
                return [training_worker_1, training_worker_2]
            elif worker_type == WorkerType.BACKTESTING:
                return [backtest_worker_1]
            return []

        registry.list_workers = mock_list_workers
        return registry

    @pytest.fixture
    def mock_budget_tracker(self):
        """Create a mock budget tracker for status tests."""
        tracker = MagicMock()
        tracker.get_remaining.return_value = 3.42
        tracker.daily_limit = 5.0
        return tracker

    @pytest.mark.asyncio
    async def test_status_shows_all_active_researches(
        self, mock_operations_service, mock_worker_registry, mock_budget_tracker
    ):
        """E2E: Multiple triggered researches all appear in status."""
        from ktrdr.api.services.agent_service import AgentService

        # Create two running research operations
        op_a = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "training",
                    "strategy_name": "rsi_variant_7",
                    "training_op_id": "op_train_a",
                }
            ),
        )
        mock_operations_service._operations[op_a.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op_a.operation_id].started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=2, seconds=15)
        )

        op_b = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "backtesting",
                    "strategy_name": "mtf_momentum_1",
                    "backtest_op_id": "op_backtest_b",
                }
            ),
        )
        mock_operations_service._operations[op_b.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op_b.operation_id].started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1, seconds=45)
        )

        with (
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_worker_registry,
            ),
            patch(
                "ktrdr.api.services.agent_service.get_budget_tracker",
                return_value=mock_budget_tracker,
            ),
        ):
            service = AgentService(operations_service=mock_operations_service)
            status = await service.get_status()

        # Verify status is active
        assert status["status"] == "active"

        # Verify both researches appear
        assert len(status["active_researches"]) == 2

        op_ids = [r["operation_id"] for r in status["active_researches"]]
        assert op_a.operation_id in op_ids
        assert op_b.operation_id in op_ids

    @pytest.mark.asyncio
    async def test_status_shows_correct_phases(
        self, mock_operations_service, mock_worker_registry, mock_budget_tracker
    ):
        """Each research shows its current phase."""
        from ktrdr.api.services.agent_service import AgentService

        # Create two operations at different phases
        op_training = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op_training.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op_training.operation_id].started_at = (
            datetime.now(timezone.utc)
        )

        op_designing = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "designing"}),
        )
        mock_operations_service._operations[op_designing.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op_designing.operation_id].started_at = (
            datetime.now(timezone.utc)
        )

        with (
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_worker_registry,
            ),
            patch(
                "ktrdr.api.services.agent_service.get_budget_tracker",
                return_value=mock_budget_tracker,
            ),
        ):
            service = AgentService(operations_service=mock_operations_service)
            status = await service.get_status()

        # Find each research by operation_id
        researches_by_id = {r["operation_id"]: r for r in status["active_researches"]}

        assert researches_by_id[op_training.operation_id]["phase"] == "training"
        assert researches_by_id[op_designing.operation_id]["phase"] == "designing"

    @pytest.mark.asyncio
    async def test_status_shows_worker_utilization(
        self, mock_operations_service, mock_worker_registry, mock_budget_tracker
    ):
        """Status shows worker busy/total counts by type."""
        from ktrdr.api.services.agent_service import AgentService

        with (
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_worker_registry,
            ),
            patch(
                "ktrdr.api.services.agent_service.get_budget_tracker",
                return_value=mock_budget_tracker,
            ),
        ):
            service = AgentService(operations_service=mock_operations_service)
            status = await service.get_status()

        assert "workers" in status
        assert status["workers"]["training"]["busy"] == 1
        assert status["workers"]["training"]["total"] == 2
        assert status["workers"]["backtesting"]["busy"] == 0
        assert status["workers"]["backtesting"]["total"] == 1

    @pytest.mark.asyncio
    async def test_status_shows_budget_remaining(
        self, mock_operations_service, mock_worker_registry, mock_budget_tracker
    ):
        """Status shows budget remaining and daily limit."""
        from ktrdr.api.services.agent_service import AgentService

        with (
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_worker_registry,
            ),
            patch(
                "ktrdr.api.services.agent_service.get_budget_tracker",
                return_value=mock_budget_tracker,
            ),
        ):
            service = AgentService(operations_service=mock_operations_service)
            status = await service.get_status()

        assert "budget" in status
        assert status["budget"]["remaining"] == 3.42
        assert status["budget"]["daily_limit"] == 5.0

    @pytest.mark.asyncio
    async def test_status_shows_capacity_info(
        self,
        mock_operations_service,
        mock_worker_registry,
        mock_budget_tracker,
        monkeypatch,
    ):
        """Status shows capacity active count and limit."""
        from ktrdr.api.services.agent_service import AgentService

        monkeypatch.setenv("AGENT_MAX_CONCURRENT_RESEARCHES", "6")

        # Create 2 active operations
        for _ in range(2):
            op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_RESEARCH,
                metadata=OperationMetadata(parameters={"phase": "training"}),
            )
            mock_operations_service._operations[op.operation_id].status = (
                OperationStatus.RUNNING
            )
            mock_operations_service._operations[op.operation_id].started_at = (
                datetime.now(timezone.utc)
            )

        with (
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_worker_registry,
            ),
            patch(
                "ktrdr.api.services.agent_service.get_budget_tracker",
                return_value=mock_budget_tracker,
            ),
        ):
            service = AgentService(operations_service=mock_operations_service)
            status = await service.get_status()

        assert "capacity" in status
        assert status["capacity"]["active"] == 2
        assert status["capacity"]["limit"] == 6

    @pytest.mark.asyncio
    async def test_status_shows_duration_for_each_research(
        self, mock_operations_service, mock_worker_registry, mock_budget_tracker
    ):
        """Each research shows duration in seconds."""
        from ktrdr.api.services.agent_service import AgentService

        # Create operation started 2 minutes ago
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "training"}),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.RUNNING
        )
        mock_operations_service._operations[op.operation_id].started_at = datetime.now(
            timezone.utc
        ) - timedelta(minutes=2)

        with (
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_worker_registry,
            ),
            patch(
                "ktrdr.api.services.agent_service.get_budget_tracker",
                return_value=mock_budget_tracker,
            ),
        ):
            service = AgentService(operations_service=mock_operations_service)
            status = await service.get_status()

        research = status["active_researches"][0]
        # Should be around 120 seconds, allow tolerance
        assert 115 <= research["duration_seconds"] <= 125


class TestStatusIdleState:
    """Tests for idle status with last cycle info."""

    @pytest.fixture
    def mock_worker_registry(self):
        """Create a mock worker registry."""
        from ktrdr.api.models.workers import WorkerType

        registry = MagicMock()

        def mock_list_workers(worker_type=None):
            if worker_type == WorkerType.TRAINING:
                return []
            elif worker_type == WorkerType.BACKTESTING:
                return []
            return []

        registry.list_workers = mock_list_workers
        return registry

    @pytest.fixture
    def mock_budget_tracker(self):
        """Create a mock budget tracker."""
        tracker = MagicMock()
        tracker.get_remaining.return_value = 5.0
        tracker.daily_limit = 5.0
        return tracker

    @pytest.mark.asyncio
    async def test_idle_status_shows_empty_active_list(
        self, mock_operations_service, mock_worker_registry, mock_budget_tracker
    ):
        """Idle status shows empty active_researches list."""
        from ktrdr.api.services.agent_service import AgentService

        # No active operations

        with (
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_worker_registry,
            ),
            patch(
                "ktrdr.api.services.agent_service.get_budget_tracker",
                return_value=mock_budget_tracker,
            ),
        ):
            service = AgentService(operations_service=mock_operations_service)
            status = await service.get_status()

        assert status["status"] == "idle"
        assert status["active_researches"] == []

    @pytest.mark.asyncio
    async def test_idle_status_shows_last_completed_cycle(
        self, mock_operations_service, mock_worker_registry, mock_budget_tracker
    ):
        """Idle status shows last completed research info."""
        from ktrdr.api.services.agent_service import AgentService

        # Create a completed operation
        op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"phase": "completed", "strategy_name": "test_strategy"}
            ),
        )
        mock_operations_service._operations[op.operation_id].status = (
            OperationStatus.COMPLETED
        )
        mock_operations_service._operations[op.operation_id].completed_at = (
            datetime.now(timezone.utc)
        )
        mock_operations_service._operations[op.operation_id].result_summary = {
            "strategy_name": "test_strategy"
        }

        with (
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_worker_registry,
            ),
            patch(
                "ktrdr.api.services.agent_service.get_budget_tracker",
                return_value=mock_budget_tracker,
            ),
        ):
            service = AgentService(operations_service=mock_operations_service)
            status = await service.get_status()

        assert status["status"] == "idle"
        assert status["last_cycle"] is not None
        assert status["last_cycle"]["operation_id"] == op.operation_id
        assert status["last_cycle"]["outcome"] == "completed"
