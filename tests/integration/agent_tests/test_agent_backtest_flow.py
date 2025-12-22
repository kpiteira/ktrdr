"""Integration tests for agent backtest flow (M4 Task 4.5).

Tests verify:
1. Backtest service integration with research worker
2. Backtest metrics extraction and gate evaluation
3. Backtest result storage in parent metadata
4. Feature consistency between training and backtest (timeframe prefix fix)

These tests use mocks for fast execution without requiring Docker workers.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from ktrdr.agents.gates import check_backtest_gate
from ktrdr.agents.workers.research_worker import (
    AgentResearchWorker,
    GateFailedError,
)
from ktrdr.agents.workers.stubs import StubAssessmentWorker, StubDesignWorker
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


class MockOperationsService:
    """In-memory operations service for testing."""

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
    """Mock training service that returns good metrics.

    The metrics structure must match what check_training_gate expects:
    - test_metrics.test_accuracy: Accuracy (0.0-1.0)
    - test_metrics.test_loss: Final test loss (used for max_loss check)
    - training_metrics.history.train_loss: Loss history for decrease check
    """

    def __init__(self, ops_service, return_metrics=None):
        self.ops = ops_service
        self.return_metrics = return_metrics or {
            "success": True,
            "test_metrics": {
                "test_accuracy": 0.65,  # 65% > 45% threshold
                "test_loss": 0.35,  # 0.35 < 0.8 threshold
            },
            "training_metrics": {
                "history": {
                    "train_loss": [0.85, 0.65, 0.45, 0.35],  # 59% decrease > 20%
                },
                "final_train_loss": 0.35,
            },
            "model_path": "/app/models/test/1h_v1",
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
    """Mock backtest service for testing backtest integration."""

    def __init__(self, ops_service, return_metrics=None, delay_seconds=0):
        self.ops = ops_service
        self.return_metrics = return_metrics or {
            "success": True,
            "metrics": {
                "sharpe_ratio": 1.2,
                "win_rate": 0.55,
                "max_drawdown": 0.15,
                "max_drawdown_pct": 0.15,
                "total_return": 0.23,
                "total_trades": 42,
            },
        }
        self.delay_seconds = delay_seconds
        self.call_count = 0
        self.last_call_kwargs: dict = {}

    async def run_backtest(self, **kwargs):
        """Create backtest operation and complete with metrics."""
        self.call_count += 1
        self.last_call_kwargs = kwargs

        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)

        backtest_op = await self.ops.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        await self.ops.complete_operation(backtest_op.operation_id, self.return_metrics)
        return {"operation_id": backtest_op.operation_id}


@pytest.fixture(autouse=True)
def fast_stub_mode(monkeypatch):
    """Enable fast stub mode for all tests (0.5s delay instead of 30s)."""
    monkeypatch.setenv("STUB_WORKER_FAST", "true")


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


class TestBacktestServiceIntegration:
    """Tests for backtest service integration with research worker."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_service_called_after_training_gate_passes(
        self, ops_service, training_service, backtest_service
    ):
        """Backtest service is called after training gate passes."""
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

        # Verify backtest was called
        assert backtest_service.call_count == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_receives_correct_parameters(
        self, ops_service, training_service, backtest_service
    ):
        """Backtest service receives correct parameters from training result."""
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

        # Verify parameters passed to backtest
        assert "model_path" in backtest_service.last_call_kwargs
        assert "strategy_config_path" in backtest_service.last_call_kwargs
        assert "symbol" in backtest_service.last_call_kwargs
        assert "timeframe" in backtest_service.last_call_kwargs

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_not_called_if_training_gate_fails(self, ops_service):
        """Backtest service NOT called if training gate fails."""
        bad_training = MockTrainingService(
            ops_service,
            return_metrics={
                "success": True,
                "test_metrics": {
                    "test_accuracy": 0.30,  # Below 45% threshold
                    "test_loss": 0.35,
                },
                "training_metrics": {
                    "history": {"train_loss": [0.85, 0.35]},
                },
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

        with pytest.raises(GateFailedError):
            await worker.run(parent_op.operation_id)

        # Verify backtest was NOT called
        assert good_backtest.call_count == 0


class TestBacktestMetricsExtraction:
    """Tests for backtest metrics extraction and storage."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_metrics_stored_in_parent_metadata(
        self, ops_service, training_service, backtest_service
    ):
        """Backtest metrics are stored in parent operation metadata."""
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

        # Verify metrics stored
        parent = await ops_service.get_operation(parent_op.operation_id)
        params = parent.metadata.parameters

        assert "backtest_result" in params
        assert params["backtest_result"]["sharpe_ratio"] == 1.2
        assert params["backtest_result"]["win_rate"] == 0.55

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_operation_id_stored_in_parent_metadata(
        self, ops_service, training_service, backtest_service
    ):
        """Backtest operation ID is stored in parent metadata for tracking."""
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

        assert "backtest_op_id" in params
        assert params["backtest_op_id"].startswith("op_backtesting_")


class TestBacktestGateEvaluation:
    """Tests for backtest gate evaluation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_gate_passes_with_good_metrics(
        self, ops_service, training_service
    ):
        """Backtest gate passes with metrics above thresholds."""
        good_backtest = MockBacktestService(
            ops_service,
            return_metrics={
                "success": True,
                "metrics": {
                    "sharpe_ratio": 1.5,
                    "win_rate": 0.60,
                    "max_drawdown_pct": 0.10,
                    "total_trades": 50,
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
            backtest_service=good_backtest,
        )

        # Should complete without GateFailedError
        result = await worker.run(parent_op.operation_id)
        assert result["success"] is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_gate_fails_with_low_win_rate(
        self, ops_service, training_service
    ):
        """Backtest gate fails with win rate below 45%."""
        bad_backtest = MockBacktestService(
            ops_service,
            return_metrics={
                "success": True,
                "metrics": {
                    "sharpe_ratio": 1.0,
                    "win_rate": 0.35,  # Below 45%
                    "max_drawdown_pct": 0.10,
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

        assert "win_rate" in str(exc_info.value).lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_gate_fails_with_high_drawdown(
        self, ops_service, training_service
    ):
        """Backtest gate fails with drawdown above 40%."""
        bad_backtest = MockBacktestService(
            ops_service,
            return_metrics={
                "success": True,
                "metrics": {
                    "sharpe_ratio": 1.0,
                    "win_rate": 0.55,
                    "max_drawdown_pct": 0.50,  # Above 40%
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

        assert "drawdown" in str(exc_info.value).lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_backtest_gate_fails_with_very_negative_sharpe(
        self, ops_service, training_service
    ):
        """Backtest gate fails with Sharpe ratio below -0.5."""
        bad_backtest = MockBacktestService(
            ops_service,
            return_metrics={
                "success": True,
                "metrics": {
                    "sharpe_ratio": -1.0,  # Below -0.5
                    "win_rate": 0.55,
                    "max_drawdown_pct": 0.10,
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

        assert "sharpe" in str(exc_info.value).lower()


class TestBacktestGateFunctions:
    """Unit tests for backtest gate function."""

    def test_check_backtest_gate_passes_with_good_metrics(self):
        """check_backtest_gate returns True with good metrics."""
        good = {
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "max_drawdown": 0.15,
        }
        passed, reason = check_backtest_gate(good)
        assert passed is True
        assert reason == "passed"

    def test_check_backtest_gate_handles_zero_trades(self):
        """check_backtest_gate handles zero trades gracefully."""
        zero_trades = {
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "total_trades": 0,
        }
        passed, reason = check_backtest_gate(zero_trades)
        # Should fail due to low win rate
        assert passed is False

    def test_check_backtest_gate_edge_case_at_thresholds(self):
        """check_backtest_gate at exact threshold values."""
        at_thresholds = {
            "sharpe_ratio": -0.5,  # Exactly at threshold
            "win_rate": 0.45,  # Exactly at threshold
            "max_drawdown": 0.40,  # Exactly at threshold
        }
        passed, reason = check_backtest_gate(at_thresholds)
        # Should pass since thresholds are inclusive
        assert passed is True
