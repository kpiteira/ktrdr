"""End-to-end integration tests for agent cycle with stub workers.

Tests the full agent cycle using USE_STUB_WORKERS=true environment variable.
These tests verify that all components integrate correctly without requiring
real Claude API calls or real training/backtest workers.

Test Categories:
1. Full cycle completion
2. Cancellation mid-cycle
3. Phase transition verification
4. Gate failure scenarios
5. Service error handling
"""

import asyncio
from datetime import datetime, timezone

import pytest

from ktrdr.agents.gates import check_backtest_gate, check_training_gate
from ktrdr.agents.workers.research_worker import (
    AgentResearchWorker,
    GateFailedError,
    WorkerError,
)
from ktrdr.agents.workers.stubs import StubAssessmentWorker, StubDesignWorker
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


class MockOperationsService:
    """In-memory operations service for E2E testing."""

    def __init__(self):
        self._operations: dict[str, OperationInfo] = {}
        self._counter = 0

    async def create_operation(
        self, operation_type, metadata=None, parent_operation_id=None
    ):
        """Create a new operation."""
        self._counter += 1
        op_id = f"op_{operation_type.value}_{self._counter}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or OperationMetadata(),
            parent_operation_id=parent_operation_id,
        )
        self._operations[op_id] = op
        return op

    async def get_operation(self, operation_id):
        """Get operation by ID."""
        return self._operations.get(operation_id)

    async def start_operation(self, operation_id, task):
        """Mark operation as running."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.RUNNING

    async def complete_operation(self, operation_id, result=None):
        """Mark operation as completed."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.COMPLETED
            self._operations[operation_id].result_summary = result

    async def fail_operation(self, operation_id, error=None):
        """Mark operation as failed."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.FAILED
            self._operations[operation_id].error_message = error

    async def cancel_operation(self, operation_id, reason=None):
        """Mark operation as cancelled."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.CANCELLED


class MockTrainingService:
    """Mock training service for E2E testing."""

    def __init__(self, ops_service, return_metrics=None):
        self.ops = ops_service
        self.return_metrics = return_metrics or {
            "success": True,
            "accuracy": 0.65,
            "final_loss": 0.35,
            "initial_loss": 0.85,
            "model_path": "/app/models/stub/model.pt",
        }
        self.call_count = 0

    async def start_training(self, **kwargs):
        """Create training operation and complete with metrics."""
        self.call_count += 1
        training_op = await self.ops.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        await self.ops.complete_operation(training_op.operation_id, self.return_metrics)
        return {"operation_id": training_op.operation_id}


class MockBacktestService:
    """Mock backtest service for E2E testing."""

    def __init__(self, ops_service, return_metrics=None):
        self.ops = ops_service
        self.return_metrics = return_metrics or {
            "success": True,
            "metrics": {
                "sharpe_ratio": 1.2,
                "win_rate": 0.55,
                "max_drawdown_pct": 0.15,
                "total_return": 0.23,
                "total_trades": 42,
            },
        }
        self.call_count = 0

    async def run_backtest(self, **kwargs):
        """Create backtest operation and complete with metrics."""
        self.call_count += 1
        backtest_op = await self.ops.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        await self.ops.complete_operation(backtest_op.operation_id, self.return_metrics)
        return {"operation_id": backtest_op.operation_id}


@pytest.fixture
def ops_service():
    """Create mock operations service."""
    return MockOperationsService()


@pytest.fixture
def training_service(ops_service):
    """Create mock training service with good metrics."""
    return MockTrainingService(ops_service)


@pytest.fixture
def backtest_service(ops_service):
    """Create mock backtest service with good metrics."""
    return MockBacktestService(ops_service)


class TestFullCycleE2E:
    """E2E tests for complete agent cycle."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_cycle_completes_with_stub_workers(
        self, ops_service, training_service, backtest_service
    ):
        """Full cycle completes: design → train → backtest → assess."""
        # Create parent operation
        parent_op = await ops_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Create orchestrator with stub workers
        worker = AgentResearchWorker(
            operations_service=ops_service,
            design_worker=StubDesignWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=training_service,
            backtest_service=backtest_service,
        )

        # Run cycle
        result = await worker.run(parent_op.operation_id)

        # Verify success
        assert result["success"] is True
        assert "strategy_name" in result
        assert "verdict" in result
        assert result["verdict"] == "promising"

        # Verify all phases completed
        parent = await ops_service.get_operation(parent_op.operation_id)
        params = parent.metadata.parameters
        assert "design_op_id" in params
        assert "training_op_id" in params
        assert "backtest_op_id" in params
        assert "assessment_op_id" in params

        # Verify services were called
        assert training_service.call_count == 1
        assert backtest_service.call_count == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_cycle_stores_all_metadata(
        self, ops_service, training_service, backtest_service
    ):
        """Full cycle stores all required metadata per ARCHITECTURE.md."""
        parent_op = await ops_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=ops_service,
            design_worker=StubDesignWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=training_service,
            backtest_service=backtest_service,
        )

        await worker.run(parent_op.operation_id)

        parent = await ops_service.get_operation(parent_op.operation_id)
        params = parent.metadata.parameters

        # Verify design results
        assert params["strategy_name"] == "stub_momentum_v1"
        assert params["strategy_path"] == "/app/strategies/stub_momentum_v1.yaml"

        # Verify training results
        assert "training_result" in params
        assert params["training_result"]["accuracy"] == 0.65

        # Verify backtest results
        assert "backtest_result" in params
        assert params["backtest_result"]["sharpe_ratio"] == 1.2

        # Verify assessment results
        assert params["assessment_verdict"] == "promising"


class TestCancellationE2E:
    """E2E tests for cancellation scenarios."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cancellation_during_design_phase(self, ops_service):
        """Cancellation during design phase stops the cycle."""

        # Slow design worker to allow cancellation
        class SlowDesignWorker:
            async def run(self, *args, **kwargs):
                for _ in range(100):
                    await asyncio.sleep(0.05)
                return {
                    "success": True,
                    "strategy_name": "test",
                    "strategy_path": "/test",
                }

        parent_op = await ops_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=ops_service,
            design_worker=SlowDesignWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=MockTrainingService(ops_service),
            backtest_service=MockBacktestService(ops_service),
        )

        # Start worker
        task = asyncio.create_task(worker.run(parent_op.operation_id))

        # Wait for design to start then cancel
        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Verify child operation was cancelled
        parent = await ops_service.get_operation(parent_op.operation_id)
        design_op_id = parent.metadata.parameters.get("design_op_id")
        if design_op_id:
            design_op = await ops_service.get_operation(design_op_id)
            assert design_op.status == OperationStatus.CANCELLED

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cancellation_responsive_within_200ms(self, ops_service):
        """Cancellation completes within 200ms."""
        import time

        class SlowWorker:
            async def run(self, *args, **kwargs):
                for _ in range(100):
                    await asyncio.sleep(0.1)
                return {"success": True}

        parent_op = await ops_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=ops_service,
            design_worker=SlowWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=MockTrainingService(ops_service),
            backtest_service=MockBacktestService(ops_service),
        )

        task = asyncio.create_task(worker.run(parent_op.operation_id))
        await asyncio.sleep(0.15)

        start = time.time()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        elapsed = time.time() - start
        assert (
            elapsed < 0.2
        ), f"Cancellation took {elapsed*1000:.0f}ms, expected < 200ms"


class TestGateFailuresE2E:
    """E2E tests for gate failure scenarios."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_training_gate_failure_stops_cycle(self, ops_service):
        """Training gate failure stops cycle before backtest."""
        # Training service returns bad metrics
        bad_training = MockTrainingService(
            ops_service,
            return_metrics={
                "success": True,
                "accuracy": 0.30,  # Below 45% threshold
                "final_loss": 0.35,
                "initial_loss": 0.85,
                "model_path": "/app/models/bad/model.pt",
            },
        )

        good_backtest = MockBacktestService(ops_service)

        parent_op = await ops_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=ops_service,
            design_worker=StubDesignWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=bad_training,
            backtest_service=good_backtest,
        )

        with pytest.raises(GateFailedError) as exc_info:
            await worker.run(parent_op.operation_id)

        assert "training" in str(exc_info.value).lower()
        assert "accuracy" in str(exc_info.value).lower()

        # Backtest should NOT have been called
        assert good_backtest.call_count == 0

        # Verify phase stopped at training
        parent = await ops_service.get_operation(parent_op.operation_id)
        assert "backtest_op_id" not in parent.metadata.parameters

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_gate_failure_stops_cycle(
        self, ops_service, training_service
    ):
        """Backtest gate failure stops cycle before assessment."""
        # Backtest service returns bad metrics
        bad_backtest = MockBacktestService(
            ops_service,
            return_metrics={
                "success": True,
                "metrics": {
                    "sharpe_ratio": -1.0,  # Below -0.5 threshold
                    "win_rate": 0.55,
                    "max_drawdown_pct": 0.15,
                },
            },
        )

        parent_op = await ops_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=ops_service,
            design_worker=StubDesignWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=training_service,
            backtest_service=bad_backtest,
        )

        with pytest.raises(GateFailedError) as exc_info:
            await worker.run(parent_op.operation_id)

        assert "backtest" in str(exc_info.value).lower()
        assert "sharpe" in str(exc_info.value).lower()

        # Verify phase stopped at backtesting
        parent = await ops_service.get_operation(parent_op.operation_id)
        assert "assessment_op_id" not in parent.metadata.parameters

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_gate_failure_includes_threshold_values(self, ops_service):
        """Gate failure error includes both actual and threshold values."""
        bad_training = MockTrainingService(
            ops_service,
            return_metrics={
                "success": True,
                "accuracy": 0.35,
                "final_loss": 0.35,
                "initial_loss": 0.85,
                "model_path": "/app/models/bad/model.pt",
            },
        )

        parent_op = await ops_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=ops_service,
            design_worker=StubDesignWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=bad_training,
            backtest_service=MockBacktestService(ops_service),
        )

        with pytest.raises(GateFailedError) as exc_info:
            await worker.run(parent_op.operation_id)

        error_str = str(exc_info.value)
        # Should include actual value (35%) and threshold (45%)
        assert "35" in error_str
        assert "45" in error_str


class TestServiceFailuresE2E:
    """E2E tests for service failure scenarios."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_design_worker_failure_stops_cycle(self, ops_service):
        """Design worker failure stops the cycle with WorkerError."""

        class FailingDesignWorker:
            async def run(self, *args, **kwargs):
                raise ValueError("Claude API error")

        parent_op = await ops_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=ops_service,
            design_worker=FailingDesignWorker(),
            assessment_worker=StubAssessmentWorker(),
            training_service=MockTrainingService(ops_service),
            backtest_service=MockBacktestService(ops_service),
        )

        with pytest.raises(WorkerError) as exc_info:
            await worker.run(parent_op.operation_id)

        assert "design" in str(exc_info.value).lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_worker_failure_stops_cycle(
        self, ops_service, training_service, backtest_service
    ):
        """Assessment worker failure stops the cycle with WorkerError."""

        class FailingAssessmentWorker:
            async def run(self, *args, **kwargs):
                raise ValueError("Claude API error")

        parent_op = await ops_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        worker = AgentResearchWorker(
            operations_service=ops_service,
            design_worker=StubDesignWorker(),
            assessment_worker=FailingAssessmentWorker(),
            training_service=training_service,
            backtest_service=backtest_service,
        )

        with pytest.raises(WorkerError) as exc_info:
            await worker.run(parent_op.operation_id)

        assert "assessment" in str(exc_info.value).lower()


class TestGateFunctionsUnit:
    """Unit tests for gate functions."""

    def test_training_gate_passes_good_metrics(self):
        """Training gate passes with good metrics."""
        good = {
            "accuracy": 0.65,
            "final_loss": 0.35,
            "initial_loss": 0.85,
        }
        passed, reason = check_training_gate(good)
        assert passed is True
        assert reason == "passed"

    def test_training_gate_fails_low_accuracy(self):
        """Training gate fails with low accuracy."""
        bad = {
            "accuracy": 0.30,
            "final_loss": 0.35,
            "initial_loss": 0.85,
        }
        passed, reason = check_training_gate(bad)
        assert passed is False
        assert "accuracy" in reason.lower()

    def test_training_gate_fails_high_loss(self):
        """Training gate fails with high final loss."""
        bad = {
            "accuracy": 0.65,
            "final_loss": 0.90,  # Above 0.8
            "initial_loss": 0.95,
        }
        passed, reason = check_training_gate(bad)
        assert passed is False
        assert "loss" in reason.lower()

    def test_training_gate_fails_insufficient_improvement(self):
        """Training gate fails with insufficient loss improvement."""
        bad = {
            "accuracy": 0.65,
            "final_loss": 0.70,
            "initial_loss": 0.75,  # Only 6.7% improvement
        }
        passed, reason = check_training_gate(bad)
        assert passed is False
        assert "decrease" in reason.lower()

    def test_backtest_gate_passes_good_metrics(self):
        """Backtest gate passes with good metrics."""
        good = {
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "max_drawdown": 0.15,
        }
        passed, reason = check_backtest_gate(good)
        assert passed is True
        assert reason == "passed"

    def test_backtest_gate_fails_low_win_rate(self):
        """Backtest gate fails with low win rate."""
        bad = {
            "sharpe_ratio": 1.2,
            "win_rate": 0.35,  # Below 45%
            "max_drawdown": 0.15,
        }
        passed, reason = check_backtest_gate(bad)
        assert passed is False
        assert "win_rate" in reason.lower()

    def test_backtest_gate_fails_high_drawdown(self):
        """Backtest gate fails with high drawdown."""
        bad = {
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "max_drawdown": 0.50,  # Above 40%
        }
        passed, reason = check_backtest_gate(bad)
        assert passed is False
        assert "drawdown" in reason.lower()

    def test_backtest_gate_fails_negative_sharpe(self):
        """Backtest gate fails with very negative Sharpe ratio."""
        bad = {
            "sharpe_ratio": -1.0,  # Below -0.5
            "win_rate": 0.55,
            "max_drawdown": 0.15,
        }
        passed, reason = check_backtest_gate(bad)
        assert passed is False
        assert "sharpe" in reason.lower()
