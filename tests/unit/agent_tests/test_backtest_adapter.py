"""Unit tests for BacktestWorkerAdapter.

Tests the adapter that connects the agent orchestrator to the
existing BacktestingService for real backtesting execution.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def mock_operations_service():
    """Create a mock OperationsService."""
    return AsyncMock()


@pytest.fixture
def mock_backtest_service():
    """Create a mock BacktestingService."""
    return AsyncMock()


def _make_operation(
    status: OperationStatus,
    result_summary: dict | None = None,
    error_message: str | None = None,
    progress: OperationProgress | None = None,
    metadata: dict | None = None,
) -> OperationInfo:
    """Helper to create mock OperationInfo objects."""
    op_metadata = OperationMetadata(
        symbol="EURUSD",
        timeframe="1h",
        parameters=metadata or {},
    )
    return OperationInfo(
        operation_id="op_backtesting_test_123",
        operation_type=OperationType.BACKTESTING,
        status=status,
        created_at=datetime.now(timezone.utc),
        result_summary=result_summary or {},
        error_message=error_message,
        progress=progress or OperationProgress(),
        metadata=op_metadata,
    )


def _make_parent_operation(
    strategy_name: str = "test_momentum_v1",
    strategy_path: str = "/app/strategies/test_momentum_v1.yaml",
    symbol: str = "EURUSD",
    timeframe: str = "1h",
) -> OperationInfo:
    """Helper to create mock parent (AGENT_RESEARCH) operation."""
    return OperationInfo(
        operation_id="op_agent_research_123",
        operation_type=OperationType.AGENT_RESEARCH,
        status=OperationStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        result_summary={},
        metadata=OperationMetadata(
            symbol=symbol,
            timeframe=timeframe,
            parameters={
                "strategy_name": strategy_name,
                "strategy_path": strategy_path,
            },
        ),
    )


class TestBacktestWorkerAdapter:
    """Tests for BacktestWorkerAdapter."""

    @pytest.mark.asyncio
    async def test_polls_until_completed_returns_metrics(
        self, mock_operations_service, mock_backtest_service
    ):
        """Polls until COMPLETED status returns metrics."""
        from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter

        # Set up backtest service to return operation ID
        mock_backtest_service.run_backtest.return_value = {
            "operation_id": "op_backtesting_test_123",
            "success": True,
        }

        # Set up get_operation to return parent first, then backtest status
        mock_operations_service.get_operation.side_effect = [
            # First call: get parent operation for context
            _make_parent_operation(),
            # Second call: backtest is RUNNING
            _make_operation(OperationStatus.RUNNING),
            # Third call: backtest COMPLETED with metrics
            _make_operation(
                OperationStatus.COMPLETED,
                result_summary={
                    "metrics": {
                        "sharpe_ratio": 1.2,
                        "win_rate": 0.55,
                        "max_drawdown": 15000.0,
                        "max_drawdown_pct": 0.15,
                        "total_return": 25000.0,
                        "total_trades": 42,
                    },
                },
            ),
        ]

        adapter = BacktestWorkerAdapter(
            operations_service=mock_operations_service,
            backtest_service=mock_backtest_service,
        )
        # Use short poll interval for tests
        adapter.POLL_INTERVAL = 0.01

        result = await adapter.run(
            parent_operation_id="op_agent_research_123",
            model_path="/app/models/test_momentum_v1/model.pt",
        )

        assert result["success"] is True
        assert result["sharpe_ratio"] == 1.2
        assert result["win_rate"] == 0.55
        assert result["max_drawdown"] == 0.15  # Adapter returns percentage
        assert result["total_return"] == 25000.0
        assert result["total_trades"] == 42

    @pytest.mark.asyncio
    async def test_raises_worker_error_on_failed_status(
        self, mock_operations_service, mock_backtest_service
    ):
        """Raises WorkerError on FAILED status."""
        from ktrdr.agents.workers.backtest_adapter import (
            BacktestWorkerAdapter,
            WorkerError,
        )

        mock_backtest_service.run_backtest.return_value = {
            "operation_id": "op_backtesting_test_123",
            "success": True,
        }

        mock_operations_service.get_operation.side_effect = [
            _make_parent_operation(),
            _make_operation(
                OperationStatus.FAILED,
                error_message="Backtest failed: No data available for period",
            ),
        ]

        adapter = BacktestWorkerAdapter(
            operations_service=mock_operations_service,
            backtest_service=mock_backtest_service,
        )
        adapter.POLL_INTERVAL = 0.01

        with pytest.raises(WorkerError) as exc_info:
            await adapter.run(
                parent_operation_id="op_agent_research_123",
                model_path="/app/models/test_momentum_v1/model.pt",
            )

        assert "Backtest failed" in str(exc_info.value)
        assert "No data available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_cancelled_error_on_cancelled_status(
        self, mock_operations_service, mock_backtest_service
    ):
        """Raises CancelledError on CANCELLED status."""
        from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter

        mock_backtest_service.run_backtest.return_value = {
            "operation_id": "op_backtesting_test_123",
            "success": True,
        }

        mock_operations_service.get_operation.side_effect = [
            _make_parent_operation(),
            _make_operation(OperationStatus.CANCELLED),
        ]

        adapter = BacktestWorkerAdapter(
            operations_service=mock_operations_service,
            backtest_service=mock_backtest_service,
        )
        adapter.POLL_INTERVAL = 0.01

        with pytest.raises(asyncio.CancelledError):
            await adapter.run(
                parent_operation_id="op_agent_research_123",
                model_path="/app/models/test_momentum_v1/model.pt",
            )

    @pytest.mark.asyncio
    async def test_passes_model_path_to_backtest_service(
        self, mock_operations_service, mock_backtest_service
    ):
        """Passes model_path to BacktestingService."""
        from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter

        mock_backtest_service.run_backtest.return_value = {
            "operation_id": "op_backtesting_test_123",
            "success": True,
        }

        mock_operations_service.get_operation.side_effect = [
            _make_parent_operation(
                strategy_name="test_strategy",
                strategy_path="/app/strategies/test_strategy.yaml",
                symbol="GBPUSD",
                timeframe="4h",
            ),
            _make_operation(
                OperationStatus.COMPLETED,
                result_summary={
                    "metrics": {
                        "sharpe_ratio": 1.0,
                        "win_rate": 0.50,
                        "max_drawdown_pct": 0.20,
                        "total_return": 10000.0,
                        "total_trades": 20,
                    },
                },
            ),
        ]

        adapter = BacktestWorkerAdapter(
            operations_service=mock_operations_service,
            backtest_service=mock_backtest_service,
        )
        adapter.POLL_INTERVAL = 0.01

        await adapter.run(
            parent_operation_id="op_agent_research_123",
            model_path="/app/models/test_strategy/v1/model.pt",
        )

        # Verify BacktestingService was called with correct params
        mock_backtest_service.run_backtest.assert_called_once()
        call_kwargs = mock_backtest_service.run_backtest.call_args.kwargs

        assert call_kwargs["model_path"] == "/app/models/test_strategy/v1/model.pt"
        assert call_kwargs["symbol"] == "GBPUSD"
        assert call_kwargs["timeframe"] == "4h"
        assert (
            call_kwargs["strategy_config_path"] == "/app/strategies/test_strategy.yaml"
        )

    @pytest.mark.asyncio
    async def test_cancels_child_on_parent_cancellation(
        self, mock_operations_service, mock_backtest_service
    ):
        """Cancels backtest operation if parent is cancelled."""
        from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter

        mock_backtest_service.run_backtest.return_value = {
            "operation_id": "op_backtesting_test_123",
            "success": True,
        }

        # First call returns parent, then hang on polling
        async def slow_get_operation(op_id):
            if op_id == "op_agent_research_123":
                return _make_parent_operation()
            await asyncio.sleep(10)
            return _make_operation(OperationStatus.RUNNING)

        mock_operations_service.get_operation.side_effect = slow_get_operation

        adapter = BacktestWorkerAdapter(
            operations_service=mock_operations_service,
            backtest_service=mock_backtest_service,
        )
        adapter.POLL_INTERVAL = 0.01

        # Start the run and then cancel it
        task = asyncio.create_task(
            adapter.run(
                parent_operation_id="op_agent_research_123",
                model_path="/app/models/test/model.pt",
            )
        )

        await asyncio.sleep(0.05)  # Let it start
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Verify cancel was called on the child operation
        mock_operations_service.cancel_operation.assert_called_once_with(
            "op_backtesting_test_123", "Parent cancelled"
        )

    @pytest.mark.asyncio
    async def test_returns_all_expected_metrics(
        self, mock_operations_service, mock_backtest_service
    ):
        """Returns all expected metrics (sharpe, win_rate, drawdown, etc.)."""
        from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter

        mock_backtest_service.run_backtest.return_value = {
            "operation_id": "op_backtesting_test_123",
            "success": True,
        }

        mock_operations_service.get_operation.side_effect = [
            _make_parent_operation(),
            _make_operation(
                OperationStatus.COMPLETED,
                result_summary={
                    "metrics": {
                        "sharpe_ratio": 1.5,
                        "win_rate": 0.58,
                        "max_drawdown": 12000.0,
                        "max_drawdown_pct": 0.12,
                        "total_return": 30000.0,
                        "total_return_pct": 0.30,
                        "total_trades": 50,
                    },
                },
            ),
        ]

        adapter = BacktestWorkerAdapter(
            operations_service=mock_operations_service,
            backtest_service=mock_backtest_service,
        )
        adapter.POLL_INTERVAL = 0.01

        result = await adapter.run(
            parent_operation_id="op_agent_research_123",
            model_path="/app/models/test/model.pt",
        )

        # Verify all required metrics are present
        assert "success" in result
        assert "backtest_op_id" in result
        assert "sharpe_ratio" in result
        assert "win_rate" in result
        assert "max_drawdown" in result
        assert "total_return" in result
        assert "total_trades" in result

        # Verify values
        assert result["success"] is True
        assert result["backtest_op_id"] == "op_backtesting_test_123"
        assert result["sharpe_ratio"] == 1.5
        assert result["win_rate"] == 0.58
        assert result["max_drawdown"] == 0.12  # Uses percentage
        assert result["total_return"] == 30000.0
        assert result["total_trades"] == 50


class TestBacktestWorkerAdapterEdgeCases:
    """Edge case tests for BacktestWorkerAdapter."""

    @pytest.mark.asyncio
    async def test_handles_missing_metrics_fields(
        self, mock_operations_service, mock_backtest_service
    ):
        """Uses defaults for missing metrics fields."""
        from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter

        mock_backtest_service.run_backtest.return_value = {
            "operation_id": "op_backtesting_test_123",
            "success": True,
        }

        # Minimal metrics - some fields missing
        mock_operations_service.get_operation.side_effect = [
            _make_parent_operation(),
            _make_operation(
                OperationStatus.COMPLETED,
                result_summary={
                    "metrics": {
                        "sharpe_ratio": 0.5,
                        # Missing: win_rate, max_drawdown, etc.
                    },
                },
            ),
        ]

        adapter = BacktestWorkerAdapter(
            operations_service=mock_operations_service,
            backtest_service=mock_backtest_service,
        )
        adapter.POLL_INTERVAL = 0.01

        result = await adapter.run(
            parent_operation_id="op_agent_research_123",
            model_path="/app/models/test/model.pt",
        )

        # Should use defaults for missing fields
        assert result["success"] is True
        assert result["sharpe_ratio"] == 0.5
        assert result["win_rate"] == 0  # Default
        assert result["max_drawdown"] == 1.0  # Default (100% worst case)
        assert result["total_return"] == 0  # Default
        assert result["total_trades"] == 0  # Default

    @pytest.mark.asyncio
    async def test_logs_progress_during_polling(
        self, mock_operations_service, mock_backtest_service
    ):
        """Logs progress information during polling."""
        from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter

        mock_backtest_service.run_backtest.return_value = {
            "operation_id": "op_backtesting_test_123",
            "success": True,
        }

        # Return progress updates then completion
        mock_operations_service.get_operation.side_effect = [
            _make_parent_operation(),
            _make_operation(
                OperationStatus.RUNNING,
                progress=OperationProgress(
                    percentage=25, current_step="Processing bars 250/1000"
                ),
            ),
            _make_operation(
                OperationStatus.RUNNING,
                progress=OperationProgress(
                    percentage=75, current_step="Processing bars 750/1000"
                ),
            ),
            _make_operation(
                OperationStatus.COMPLETED,
                result_summary={
                    "metrics": {
                        "sharpe_ratio": 1.0,
                        "win_rate": 0.50,
                        "max_drawdown_pct": 0.20,
                        "total_return": 10000.0,
                        "total_trades": 25,
                    },
                },
            ),
        ]

        adapter = BacktestWorkerAdapter(
            operations_service=mock_operations_service,
            backtest_service=mock_backtest_service,
        )
        adapter.POLL_INTERVAL = 0.01

        result = await adapter.run(
            parent_operation_id="op_agent_research_123",
            model_path="/app/models/test/model.pt",
        )

        assert result["success"] is True
        # Verify all polling calls happened (1 parent + 3 backtest polls)
        assert mock_operations_service.get_operation.call_count == 4

    @pytest.mark.asyncio
    async def test_returns_backtest_op_id_in_result(
        self, mock_operations_service, mock_backtest_service
    ):
        """Returns backtest_op_id in result."""
        from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter

        mock_backtest_service.run_backtest.return_value = {
            "operation_id": "op_backtesting_unique_456",
            "success": True,
        }

        mock_operations_service.get_operation.side_effect = [
            _make_parent_operation(),
            _make_operation(
                OperationStatus.COMPLETED,
                result_summary={
                    "metrics": {
                        "sharpe_ratio": 1.0,
                        "win_rate": 0.50,
                        "max_drawdown_pct": 0.20,
                        "total_return": 10000.0,
                        "total_trades": 20,
                    },
                },
            ),
        ]

        adapter = BacktestWorkerAdapter(
            operations_service=mock_operations_service,
            backtest_service=mock_backtest_service,
        )
        adapter.POLL_INTERVAL = 0.01

        result = await adapter.run(
            parent_operation_id="op_agent_research_123",
            model_path="/app/models/test/model.pt",
        )

        assert result["backtest_op_id"] == "op_backtesting_unique_456"
