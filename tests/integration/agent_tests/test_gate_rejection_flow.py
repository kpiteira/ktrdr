"""Tests for gate rejection → assessment flow.

Task 2.3 of M2: Verify gate rejections route to ASSESSING instead of FAILED.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.agents.workers.research_worker import AgentResearchWorker
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


@pytest.fixture(autouse=True)
def mock_budget_tracker():
    """Mock budget tracker for all tests to prevent writes to real budget file."""
    mock_tracker = MagicMock()
    mock_tracker.record_spend = MagicMock()
    mock_tracker.can_spend.return_value = (True, "ok")
    mock_tracker.get_remaining.return_value = 5.0

    with patch(
        "ktrdr.agents.workers.research_worker.get_budget_tracker",
        return_value=mock_tracker,
    ):
        yield mock_tracker


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service for testing."""
    service = AsyncMock()

    # Track operations in memory
    operations: dict[str, OperationInfo] = {}

    def create_op(operation_type, metadata=None, parent_operation_id=None):
        """Create operation helper."""
        op_id = f"op_{operation_type.value}_{len(operations)}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=OperationStatus.PENDING,
            created_at=MagicMock(),
            metadata=metadata or OperationMetadata(),
            parent_operation_id=parent_operation_id,
        )
        operations[op_id] = op
        return op

    async def async_create_operation(
        operation_type, metadata=None, parent_operation_id=None
    ):
        return create_op(operation_type, metadata, parent_operation_id)

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

    async def async_start_operation(operation_id, task):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.RUNNING

    async def async_cancel_operation(operation_id, reason=None):
        if operation_id in operations:
            operations[operation_id].status = OperationStatus.CANCELLED

    async def async_update_progress(operation_id, progress):
        pass  # No-op for tests

    service.create_operation = async_create_operation
    service.get_operation = async_get_operation
    service.complete_operation = async_complete_operation
    service.fail_operation = async_fail_operation
    service.start_operation = async_start_operation
    service.cancel_operation = async_cancel_operation
    service.update_progress = async_update_progress
    service._operations = operations

    return service


@pytest.fixture
def stub_workers(mock_operations_service):
    """Create mock workers that complete immediately (no delay).

    Unlike the real StubDesignWorker/StubAssessmentWorker, these complete
    instantly and properly create child operations in the mock service.
    """

    class MockDesignWorker:
        """Design worker that creates child op and completes immediately."""

        async def run(self, parent_operation_id: str, model: str | None = None):
            # Create child operation
            child_op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_DESIGN,
                metadata=OperationMetadata(parameters={"model": model}),
                parent_operation_id=parent_operation_id,
            )

            # Store child op ID in parent metadata
            parent_op = await mock_operations_service.get_operation(parent_operation_id)
            parent_op.metadata.parameters["design_op_id"] = child_op.operation_id

            # Complete immediately with result
            result = {
                "success": True,
                "strategy_name": "mock_strategy_v1",
                "strategy_path": "/app/strategies/mock_strategy_v1.yaml",
                "input_tokens": 100,
                "output_tokens": 50,
            }
            await mock_operations_service.complete_operation(
                child_op.operation_id, result
            )
            return result

    class MockAssessmentWorker:
        """Assessment worker that creates child op and completes immediately."""

        async def run(
            self,
            parent_operation_id: str,
            results: dict,
            model: str | None = None,
            gate_rejection_reason: str | None = None,
        ):
            # Create child operation
            child_op = await mock_operations_service.create_operation(
                operation_type=OperationType.AGENT_ASSESSMENT,
                metadata=OperationMetadata(
                    parameters={
                        "model": model,
                        "gate_rejection_reason": gate_rejection_reason,
                    }
                ),
                parent_operation_id=parent_operation_id,
            )

            # Store child op ID in parent metadata
            parent_op = await mock_operations_service.get_operation(parent_operation_id)
            parent_op.metadata.parameters["assessment_op_id"] = child_op.operation_id

            # Complete immediately with result
            result = {
                "success": True,
                "verdict": "weak_signal" if gate_rejection_reason else "promising",
                "strengths": ["Some signal detected"],
                "weaknesses": ["Low accuracy"] if gate_rejection_reason else [],
                "input_tokens": 100,
                "output_tokens": 50,
            }
            await mock_operations_service.complete_operation(
                child_op.operation_id, result
            )
            return result

    return {
        "design": MockDesignWorker(),
        "assessment": MockAssessmentWorker(),
    }


@pytest.fixture
def mock_training_service_low_accuracy(mock_operations_service):
    """Mock TrainingService that returns low accuracy (fails gate)."""
    service = AsyncMock()

    async def start_training(**kwargs):
        """Create a training operation with low accuracy."""
        training_op = await mock_operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        # Complete with LOW accuracy - will fail gate
        await mock_operations_service.complete_operation(
            training_op.operation_id,
            {
                "success": True,
                "accuracy": 0.05,  # 5% - below 10% threshold
                "val_accuracy": 0.04,
                "final_loss": 0.95,
                "initial_loss": 0.99,
                "model_path": "/app/models/poor_model/model.pt",
            },
        )
        return {"operation_id": training_op.operation_id}

    service.start_training = start_training
    return service


@pytest.fixture
def mock_training_service_good(mock_operations_service):
    """Mock TrainingService that returns good accuracy (passes gate)."""
    service = AsyncMock()

    async def start_training(**kwargs):
        """Create a training operation with good accuracy."""
        training_op = await mock_operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        await mock_operations_service.complete_operation(
            training_op.operation_id,
            {
                "success": True,
                "accuracy": 0.65,
                "val_accuracy": 0.63,
                "final_loss": 0.35,
                "initial_loss": 0.85,
                "model_path": "/app/models/good_model/model.pt",
            },
        )
        return {"operation_id": training_op.operation_id}

    service.start_training = start_training
    return service


@pytest.fixture
def mock_backtest_service_poor_sharpe(mock_operations_service):
    """Mock BacktestingService that returns poor Sharpe ratio (fails gate)."""
    service = AsyncMock()

    async def run_backtest(**kwargs):
        """Create a backtest operation with poor Sharpe ratio."""
        backtest_op = await mock_operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(parameters=kwargs),
        )
        # Complete with poor Sharpe ratio - will fail gate
        await mock_operations_service.complete_operation(
            backtest_op.operation_id,
            {
                "success": True,
                "metrics": {
                    "sharpe_ratio": -0.5,  # Negative - below 0 threshold
                    "win_rate": 0.35,
                    "max_drawdown_pct": 0.45,
                    "total_return": -0.15,
                    "total_trades": 10,
                },
            },
        )
        return {"operation_id": backtest_op.operation_id}

    service.run_backtest = run_backtest
    return service


class TestTrainingGateRejectionFlow:
    """Tests for training gate rejection → assessment flow."""

    @pytest.mark.asyncio
    async def test_training_gate_rejection_transitions_to_assessing(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service_low_accuracy,
    ):
        """Training gate rejection transitions to ASSESSING, not FAILED.

        CURRENT BEHAVIOR (to be changed by Task 2.3):
        - Training gate rejection raises GateError

        DESIRED BEHAVIOR (after Task 2.3):
        - Training gate rejection transitions to ASSESSING with partial results
        """
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Track phases seen
        phases_seen = []
        original_get = mock_operations_service.get_operation

        async def tracking_get(op_id):
            op = await original_get(op_id)
            if op and op.operation_id == parent_op.operation_id:
                phase = op.metadata.parameters.get("phase")
                if phase and (not phases_seen or phases_seen[-1] != phase):
                    phases_seen.append(phase)
            return op

        mock_operations_service.get_operation = tracking_get

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service_low_accuracy,
            backtest_service=AsyncMock(),  # Should never be called
        )

        # Task 2.3: After implementation, this should NOT raise GateError
        # Instead it should complete successfully with assessing phase
        result = await worker.run(parent_op.operation_id)

        # Should have transitioned to assessing (not raised)
        assert (
            "assessing" in phases_seen
        ), f"Expected 'assessing' in phases, got: {phases_seen}"
        # Should NOT have gone to backtesting (skipped)
        assert (
            "backtesting" not in phases_seen
        ), f"Should skip backtesting, but saw: {phases_seen}"
        # Should complete successfully
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_training_gate_rejection_skips_backtest(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service_low_accuracy,
    ):
        """Training gate rejection skips backtest phase entirely."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        mock_backtest_service = AsyncMock()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service_low_accuracy,
            backtest_service=mock_backtest_service,
        )

        await worker.run(parent_op.operation_id)

        # Backtest service should never have been called
        mock_backtest_service.run_backtest.assert_not_called()

    @pytest.mark.asyncio
    async def test_training_gate_rejection_calls_assessment_with_gate_reason(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service_low_accuracy,
    ):
        """Training gate rejection passes gate_rejection_reason to assessment."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Track calls to assessment worker by wrapping the stub
        assessment_calls = []
        original_run = stub_workers["assessment"].run

        async def tracking_run(*args, **kwargs):
            assessment_calls.append({"args": args, "kwargs": kwargs})
            return await original_run(*args, **kwargs)

        stub_workers["assessment"].run = tracking_run

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service_low_accuracy,
            backtest_service=AsyncMock(),
        )

        await worker.run(parent_op.operation_id)

        # Assessment worker should have been called with gate_rejection_reason
        assert (
            len(assessment_calls) == 1
        ), f"Expected 1 call, got {len(assessment_calls)}"
        call_kwargs = assessment_calls[0]["kwargs"]
        assert "gate_rejection_reason" in call_kwargs
        assert call_kwargs["gate_rejection_reason"] is not None
        assert "training" in call_kwargs["gate_rejection_reason"].lower()

    @pytest.mark.asyncio
    async def test_training_gate_rejection_assessment_gets_none_backtest(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service_low_accuracy,
    ):
        """Training gate rejection passes backtest=None to assessment."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Track calls to assessment worker
        assessment_calls = []
        original_run = stub_workers["assessment"].run

        async def tracking_run(*args, **kwargs):
            assessment_calls.append({"args": args, "kwargs": kwargs})
            return await original_run(*args, **kwargs)

        stub_workers["assessment"].run = tracking_run

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service_low_accuracy,
            backtest_service=AsyncMock(),
        )

        await worker.run(parent_op.operation_id)

        # Check that results dict passed to assessment has backtest=None
        assert len(assessment_calls) == 1
        # Second positional arg is results dict
        args = assessment_calls[0]["args"]
        kwargs = assessment_calls[0]["kwargs"]
        results_arg = args[1] if len(args) > 1 else kwargs.get("results")
        assert results_arg is not None
        assert results_arg.get("backtest") is None


class TestBacktestGateRejectionFlow:
    """Tests for backtest gate rejection → assessment flow."""

    @pytest.mark.asyncio
    async def test_backtest_gate_rejection_transitions_to_assessing(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service_good,
        mock_backtest_service_poor_sharpe,
    ):
        """Backtest gate rejection transitions to ASSESSING, not FAILED."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        phases_seen = []
        original_get = mock_operations_service.get_operation

        async def tracking_get(op_id):
            op = await original_get(op_id)
            if op and op.operation_id == parent_op.operation_id:
                phase = op.metadata.parameters.get("phase")
                if phase and (not phases_seen or phases_seen[-1] != phase):
                    phases_seen.append(phase)
            return op

        mock_operations_service.get_operation = tracking_get

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service_good,
            backtest_service=mock_backtest_service_poor_sharpe,
        )

        result = await worker.run(parent_op.operation_id)

        # Should have gone through backtesting AND assessing
        assert "backtesting" in phases_seen
        assert "assessing" in phases_seen
        # Should complete successfully
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_backtest_gate_rejection_calls_assessment_with_full_results(
        self,
        mock_operations_service,
        stub_workers,
        mock_training_service_good,
        mock_backtest_service_poor_sharpe,
    ):
        """Backtest gate rejection passes full results (training + backtest) to assessment."""
        parent_op = await mock_operations_service.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(parameters={"phase": "idle"}),
        )

        # Track calls to assessment worker
        assessment_calls = []
        original_run = stub_workers["assessment"].run

        async def tracking_run(*args, **kwargs):
            assessment_calls.append({"args": args, "kwargs": kwargs})
            return await original_run(*args, **kwargs)

        stub_workers["assessment"].run = tracking_run

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=stub_workers["design"],
            assessment_worker=stub_workers["assessment"],
            training_service=mock_training_service_good,
            backtest_service=mock_backtest_service_poor_sharpe,
        )

        await worker.run(parent_op.operation_id)

        # Check call to assessment
        assert len(assessment_calls) == 1
        call_kwargs = assessment_calls[0]["kwargs"]

        # Should have gate_rejection_reason
        assert "gate_rejection_reason" in call_kwargs
        assert call_kwargs["gate_rejection_reason"] is not None
        assert "backtest" in call_kwargs["gate_rejection_reason"].lower()

        # Should have results with BOTH training and backtest
        args = assessment_calls[0]["args"]
        results_arg = args[1] if len(args) > 1 else call_kwargs.get("results")
        assert results_arg.get("training") is not None
        assert results_arg.get("backtest") is not None  # Full results, not None
