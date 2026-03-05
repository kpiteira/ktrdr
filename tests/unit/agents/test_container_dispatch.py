"""Tests for container dispatch in research worker.

Task 5.1: Research worker dispatches design and assessment to container
workers via HTTP instead of running them in-process.
"""

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.api.models.workers import WorkerType

# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service for testing."""
    service = AsyncMock()
    operations: dict[str, OperationInfo] = {}
    operation_counter = 0

    async def async_create_operation(
        operation_type,
        metadata=None,
        parent_operation_id=None,
        is_backend_local=False,
        **kwargs,
    ):
        nonlocal operation_counter
        operation_counter += 1
        op_id = (
            kwargs.get("operation_id")
            or f"op_{operation_type.value}_{operation_counter}"
        )
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

    async def async_complete_operation(operation_id, result=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.COMPLETED
            operations[operation_id].result_summary = result

    async def async_fail_operation(operation_id, error=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.FAILED
            operations[operation_id].error_message = error

    async def async_start_operation(operation_id, task=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.RUNNING

    async def async_update_progress(operation_id, progress):
        if operation_id in operations:
            operations[operation_id].progress = progress

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
        return filtered[:limit], len(filtered), 0

    def generate_operation_id(op_type):
        nonlocal operation_counter
        operation_counter += 1
        return f"op_{op_type.value}_{operation_counter}"

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.complete_operation = async_complete_operation
    service.fail_operation = async_fail_operation
    service.start_operation = async_start_operation
    service.update_progress = async_update_progress
    service.list_operations = async_list_operations
    service.generate_operation_id = generate_operation_id
    service._operations = operations

    return service


@pytest.fixture
def mock_stub_design_worker():
    """Stub design worker (in-process)."""
    worker = AsyncMock()
    worker.run = AsyncMock(
        return_value={
            "success": True,
            "strategy_name": "v3_stub",
            "strategy_path": "/app/strategies/v3_stub.yaml",
            "input_tokens": 2500,
            "output_tokens": 1800,
        }
    )
    return worker


@pytest.fixture
def mock_stub_assessment_worker():
    """Stub assessment worker (in-process)."""
    worker = AsyncMock()
    worker.run = AsyncMock(
        return_value={
            "success": True,
            "verdict": "promising",
            "strengths": ["Good"],
            "weaknesses": ["Limited"],
            "suggestions": ["Test more"],
        }
    )
    return worker


@pytest.fixture
def mock_agent_dispatch():
    """Mock agent dispatch service for container workers."""
    dispatch = AsyncMock()
    dispatch.dispatch_design = AsyncMock(
        return_value={
            "operation_id": "op_design_container_1",
            "success": True,
            "status": "started",
        }
    )
    dispatch.dispatch_assessment = AsyncMock(
        return_value={
            "operation_id": "op_assess_container_1",
            "success": True,
            "status": "started",
        }
    )
    return dispatch


# ============================================================================
# TestAgentDispatchService
# ============================================================================


class TestAgentDispatchService:
    """Tests for AgentDispatchService — HTTP dispatch to container workers."""

    def test_dispatch_service_imports(self):
        """AgentDispatchService can be imported from agents module."""
        from ktrdr.agents.dispatch import AgentDispatchService

        assert AgentDispatchService is not None

    @pytest.mark.asyncio
    async def test_dispatch_design_selects_worker_and_posts(self):
        """dispatch_design selects AGENT_DESIGN worker and POSTs to /designs/start."""
        from ktrdr.agents.dispatch import AgentDispatchService

        mock_registry = MagicMock()
        mock_worker = MagicMock()
        mock_worker.worker_id = "design-agent-1"
        mock_worker.endpoint_url = "http://design-agent-1:5010"
        mock_registry.select_worker.return_value = mock_worker

        dispatch = AgentDispatchService(worker_registry=mock_registry)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "operation_id": "op_design_123",
            "status": "started",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("ktrdr.agents.dispatch.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await dispatch.dispatch_design(
                task_id="op_parent_1",
                brief="Design a momentum strategy",
                symbol="EURUSD",
                timeframe="1h",
            )

        assert result["operation_id"] == "op_design_123"
        mock_registry.select_worker.assert_called_once_with(WorkerType.AGENT_DESIGN)
        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert call_url == "http://design-agent-1:5010/designs/start"

    @pytest.mark.asyncio
    async def test_dispatch_assessment_selects_worker_and_posts(self):
        """dispatch_assessment selects AGENT_ASSESSMENT worker and POSTs to /assessments/start."""
        from ktrdr.agents.dispatch import AgentDispatchService

        mock_registry = MagicMock()
        mock_worker = MagicMock()
        mock_worker.worker_id = "assessment-agent-1"
        mock_worker.endpoint_url = "http://assessment-agent-1:5020"
        mock_registry.select_worker.return_value = mock_worker

        dispatch = AgentDispatchService(worker_registry=mock_registry)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "operation_id": "op_assess_123",
            "status": "started",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("ktrdr.agents.dispatch.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await dispatch.dispatch_assessment(
                task_id="op_parent_1",
                strategy_name="test_strategy",
                training_metrics={"accuracy": 0.75},
                backtest_results={"sharpe_ratio": 1.2},
            )

        assert result["operation_id"] == "op_assess_123"
        mock_registry.select_worker.assert_called_once_with(WorkerType.AGENT_ASSESSMENT)
        call_url = mock_client.post.call_args[0][0]
        assert call_url == "http://assessment-agent-1:5020/assessments/start"

    @pytest.mark.asyncio
    async def test_dispatch_design_raises_when_no_workers(self):
        """dispatch_design raises RuntimeError when no AGENT_DESIGN workers available."""
        from ktrdr.agents.dispatch import AgentDispatchService

        mock_registry = MagicMock()
        mock_registry.select_worker.return_value = None

        dispatch = AgentDispatchService(worker_registry=mock_registry)

        with pytest.raises(RuntimeError, match="No available.*AGENT_DESIGN"):
            await dispatch.dispatch_design(
                task_id="op_1",
                brief="Design something",
                symbol="EURUSD",
                timeframe="1h",
            )

    @pytest.mark.asyncio
    async def test_dispatch_assessment_raises_when_no_workers(self):
        """dispatch_assessment raises RuntimeError when no AGENT_ASSESSMENT workers."""
        from ktrdr.agents.dispatch import AgentDispatchService

        mock_registry = MagicMock()
        mock_registry.select_worker.return_value = None

        dispatch = AgentDispatchService(worker_registry=mock_registry)

        with pytest.raises(RuntimeError, match="No available.*AGENT_ASSESSMENT"):
            await dispatch.dispatch_assessment(
                task_id="op_1",
                strategy_name="test",
                training_metrics={},
                backtest_results={},
            )


# ============================================================================
# TestResearchWorkerContainerDispatch
# ============================================================================


class TestResearchWorkerContainerDispatch:
    """Tests for research worker dispatching to container workers."""

    @pytest.mark.asyncio
    async def test_start_design_dispatches_via_http_when_dispatch_provided(
        self,
        mock_operations_service,
        mock_stub_design_worker,
        mock_stub_assessment_worker,
        mock_agent_dispatch,
    ):
        """_start_design uses agent_dispatch when provided (container mode)."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_stub_design_worker,
            assessment_worker=mock_stub_assessment_worker,
            agent_dispatch=mock_agent_dispatch,
        )

        # Create parent operation
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"brief": "Design a strategy", "model": "claude-sonnet-4-6"},
                symbol="EURUSD",
                timeframe="1h",
            ),
        )
        mock_operations_service._operations[parent_op.operation_id].status = (
            OperationStatus.RUNNING
        )

        await worker._start_design(parent_op.operation_id)

        # Verify HTTP dispatch was used
        mock_agent_dispatch.dispatch_design.assert_called_once()
        call_kwargs = mock_agent_dispatch.dispatch_design.call_args[1]
        assert call_kwargs["brief"] == "Design a strategy"
        assert call_kwargs["symbol"] == "EURUSD"
        assert call_kwargs["timeframe"] == "1h"

        # Verify operation ID stored in parent metadata
        parent_op = await mock_operations_service.get_operation(parent_op.operation_id)
        assert (
            parent_op.metadata.parameters.get("design_op_id") == "op_design_container_1"
        )
        assert parent_op.metadata.parameters.get("phase") == "designing"

        # Verify stub worker was NOT called (container dispatch took over)
        mock_stub_design_worker.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_design_falls_back_to_stub_when_no_dispatch(
        self,
        mock_operations_service,
        mock_stub_design_worker,
        mock_stub_assessment_worker,
    ):
        """_start_design uses asyncio task (stub) when agent_dispatch is None."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_stub_design_worker,
            assessment_worker=mock_stub_assessment_worker,
            # No agent_dispatch — falls back to in-process
        )

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"brief": "Design something"},
                symbol="EURUSD",
                timeframe="1h",
            ),
        )
        mock_operations_service._operations[parent_op.operation_id].status = (
            OperationStatus.RUNNING
        )

        await worker._start_design(parent_op.operation_id)

        # Verify asyncio task was created (stub flow)
        assert parent_op.operation_id in worker._child_tasks

    @pytest.mark.asyncio
    async def test_start_assessment_dispatches_via_http_when_dispatch_provided(
        self,
        mock_operations_service,
        mock_stub_design_worker,
        mock_stub_assessment_worker,
        mock_agent_dispatch,
    ):
        """_start_assessment uses agent_dispatch when provided (container mode)."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_stub_design_worker,
            assessment_worker=mock_stub_assessment_worker,
            agent_dispatch=mock_agent_dispatch,
        )

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "strategy_name": "test_strat",
                    "training_result": {"accuracy": 0.8},
                    "backtest_result": {"sharpe_ratio": 1.5},
                    "model": "claude-sonnet-4-6",
                },
                symbol="EURUSD",
                timeframe="1h",
            ),
        )
        mock_operations_service._operations[parent_op.operation_id].status = (
            OperationStatus.RUNNING
        )

        await worker._start_assessment(parent_op.operation_id)

        # Verify HTTP dispatch was used
        mock_agent_dispatch.dispatch_assessment.assert_called_once()
        call_kwargs = mock_agent_dispatch.dispatch_assessment.call_args[1]
        assert call_kwargs["strategy_name"] == "test_strat"
        assert call_kwargs["training_metrics"] == {"accuracy": 0.8}
        assert call_kwargs["backtest_results"] == {"sharpe_ratio": 1.5}

        # Verify operation ID stored in parent metadata
        parent_op = await mock_operations_service.get_operation(parent_op.operation_id)
        assert (
            parent_op.metadata.parameters.get("assessment_op_id")
            == "op_assess_container_1"
        )
        assert parent_op.metadata.parameters.get("phase") == "assessing"

        # Verify stub worker was NOT called
        mock_stub_assessment_worker.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_assessment_falls_back_to_stub_when_no_dispatch(
        self,
        mock_operations_service,
        mock_stub_design_worker,
        mock_stub_assessment_worker,
    ):
        """_start_assessment uses asyncio task (stub) when agent_dispatch is None."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_stub_design_worker,
            assessment_worker=mock_stub_assessment_worker,
        )

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "strategy_name": "test_strat",
                    "training_result": {},
                    "backtest_result": {},
                },
                symbol="EURUSD",
                timeframe="1h",
            ),
        )
        mock_operations_service._operations[parent_op.operation_id].status = (
            OperationStatus.RUNNING
        )

        await worker._start_assessment(parent_op.operation_id)

        # Verify asyncio task was created (stub flow)
        assert parent_op.operation_id in worker._child_tasks

    @pytest.mark.asyncio
    async def test_design_dispatch_failure_raises_worker_error(
        self,
        mock_operations_service,
        mock_stub_design_worker,
        mock_stub_assessment_worker,
    ):
        """When container dispatch fails, WorkerError is raised."""
        from ktrdr.agents.workers.research_worker import (
            AgentResearchWorker,
            WorkerError,
        )

        mock_dispatch = AsyncMock()
        mock_dispatch.dispatch_design = AsyncMock(
            side_effect=RuntimeError("No available AGENT_DESIGN workers")
        )

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_stub_design_worker,
            assessment_worker=mock_stub_assessment_worker,
            agent_dispatch=mock_dispatch,
        )

        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={"brief": "Design something"},
                symbol="EURUSD",
                timeframe="1h",
            ),
        )
        mock_operations_service._operations[parent_op.operation_id].status = (
            OperationStatus.RUNNING
        )

        with pytest.raises(WorkerError, match="Design dispatch failed"):
            await worker._start_design(parent_op.operation_id)

    @pytest.mark.asyncio
    async def test_container_design_polling_works_via_operation_status(
        self,
        mock_operations_service,
        mock_stub_design_worker,
        mock_stub_assessment_worker,
        mock_agent_dispatch,
    ):
        """After container dispatch, _handle_designing_phase polls via operation status."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_stub_design_worker,
            assessment_worker=mock_stub_assessment_worker,
            agent_dispatch=mock_agent_dispatch,
        )

        # Create parent with design_op_id already set (as if dispatch already happened)
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "designing",
                    "design_op_id": "op_design_container_1",
                    "phase_start_time": time.time(),
                },
            ),
        )

        # Create the design child operation as RUNNING
        await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(),
            operation_id="op_design_container_1",
        )
        mock_operations_service._operations["op_design_container_1"].status = (
            OperationStatus.RUNNING
        )

        # Phase handler should see RUNNING and wait
        await worker._handle_designing_phase(
            parent_op.operation_id,
            mock_operations_service._operations["op_design_container_1"],
        )
        # No transition should have happened — still waiting

        # Now complete the design operation
        mock_operations_service._operations["op_design_container_1"].status = (
            OperationStatus.COMPLETED
        )
        mock_operations_service._operations["op_design_container_1"].result_summary = {
            "strategy_name": "container_designed_strat",
            "strategy_path": "/app/strategies/container_designed_strat.yaml",
            "input_tokens": 5000,
            "output_tokens": 3000,
        }

        # Mock training worker availability and _start_training
        with (
            patch.object(worker, "_is_training_worker_available", return_value=True),
            patch.object(worker, "_start_training", new_callable=AsyncMock),
        ):
            await worker._handle_designing_phase(
                parent_op.operation_id,
                mock_operations_service._operations["op_design_container_1"],
            )

        # Verify strategy data was stored in parent metadata
        parent = await mock_operations_service.get_operation(parent_op.operation_id)
        assert (
            parent.metadata.parameters.get("strategy_name")
            == "container_designed_strat"
        )

    @pytest.mark.asyncio
    async def test_orphan_detection_skipped_for_container_dispatch(
        self,
        mock_operations_service,
        mock_stub_design_worker,
        mock_stub_assessment_worker,
        mock_agent_dispatch,
    ):
        """Orphan detection should not restart container operations.

        Container workers survive backend restarts (they're separate processes),
        so orphan detection should only apply to in-process asyncio tasks.
        """
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_stub_design_worker,
            assessment_worker=mock_stub_assessment_worker,
            agent_dispatch=mock_agent_dispatch,
        )

        # Create a RUNNING child operation with no asyncio task
        child_op = OperationInfo(
            operation_id="op_design_container_99",
            operation_type=OperationType.AGENT_DESIGN,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=OperationMetadata(),
        )

        # With container dispatch, orphan detection should NOT trigger
        # because container workers survive backend restarts
        result = await worker._check_and_handle_orphan(
            "parent_op_1",
            "designing",
            child_op,
        )

        # When agent_dispatch is set, orphan detection should be skipped
        assert result is False
