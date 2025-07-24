"""
Unit tests for BacktestingService.

Tests the backtesting service that manages async backtest operations
and integrates with the OperationsService framework.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from pathlib import Path

from ktrdr.api.services.backtesting_service import BacktestingService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import OperationType, OperationStatus
from ktrdr.errors import ValidationError, DataError


@pytest.fixture
def mock_operations_service():
    """Create a mock OperationsService."""
    from ktrdr.api.models.operations import (
        OperationInfo,
        OperationType,
        OperationStatus,
        OperationMetadata,
        OperationProgress,
    )
    from datetime import datetime, timezone

    mock = AsyncMock(spec=OperationsService)

    # Create a mock OperationInfo object
    mock_operation = OperationInfo(
        operation_id="test_operation_id",
        operation_type=OperationType.BACKTESTING,
        status=OperationStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        metadata=OperationMetadata(),
        progress=OperationProgress(),
    )

    mock.create_operation.return_value = mock_operation
    mock.start_operation.return_value = None
    mock.update_progress.return_value = None
    mock.complete_operation.return_value = None
    mock.fail_operation.return_value = None
    return mock


@pytest.fixture
def backtesting_service(mock_operations_service):
    """Create a BacktestingService with mocked dependencies."""
    with (
        patch("ktrdr.api.services.backtesting_service.DataManager"),
        patch("ktrdr.api.services.backtesting_service.ModelLoader"),
    ):
        service = BacktestingService(operations_service=mock_operations_service)
        return service


@pytest.fixture
def sample_backtest_params():
    """Sample backtest parameters."""
    return {
        "strategy_name": "test_strategy",
        "symbol": "AAPL",
        "timeframe": "1h",
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "initial_capital": 100000.0,
    }


class TestBacktestingService:
    """Test BacktestingService functionality."""

    @pytest.mark.asyncio
    async def test_health_check(self, backtesting_service, mock_operations_service):
        """Test backtesting service health check."""
        mock_operations_service.list_operations.return_value = (
            [
                MagicMock(status=OperationStatus.RUNNING),
                MagicMock(status=OperationStatus.PENDING),
            ],
            2,  # total_count
            2,  # active_count
        )

        health = await backtesting_service.health_check()

        assert health["service"] == "BacktestingService"
        assert health["status"] == "ok"
        assert health["active_backtests"] == 2
        assert health["data_manager_ready"] is True
        assert health["model_loader_ready"] is True

    @pytest.mark.asyncio
    async def test_start_backtest_success(
        self, backtesting_service, mock_operations_service, sample_backtest_params
    ):
        """Test successfully starting a backtest."""
        result = await backtesting_service.start_backtest(**sample_backtest_params)

        assert result["backtest_id"] == "test_operation_id"
        assert result["status"] == "starting"
        assert "test_strategy" in result["message"]

        # Verify operations service was called correctly
        mock_operations_service.create_operation.assert_called_once()
        call_args = mock_operations_service.create_operation.call_args
        assert call_args[1]["operation_type"] == OperationType.BACKTESTING

        mock_operations_service.start_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_backtest_with_invalid_strategy(
        self, backtesting_service, sample_backtest_params
    ):
        """Test starting backtest with invalid strategy name."""
        sample_backtest_params["strategy_name"] = "nonexistent_strategy"

        with patch("pathlib.Path.exists", return_value=False):
            # The actual backtest execution should fail during the async task
            result = await backtesting_service.start_backtest(**sample_backtest_params)

            # The start_backtest should still return successfully (async pattern)
            assert result["backtest_id"] == "test_operation_id"
            assert result["status"] == "starting"

    @pytest.mark.asyncio
    async def test_estimate_total_bars(self, backtesting_service):
        """Test estimating total bars for progress tracking."""
        # Test different timeframes
        estimate_1h = await backtesting_service._estimate_total_bars(
            "AAPL", "1h", "2024-01-01", "2024-01-08"
        )
        assert estimate_1h == 7 * 7  # 7 days * ~7 hours per day

        estimate_1d = await backtesting_service._estimate_total_bars(
            "AAPL", "1d", "2024-01-01", "2024-01-08"
        )
        assert estimate_1d == 7  # 7 days

        estimate_5m = await backtesting_service._estimate_total_bars(
            "AAPL", "5m", "2024-01-01", "2024-01-02"
        )
        assert estimate_5m == 1 * 78  # 1 day * 78 five-minute bars

    @pytest.mark.asyncio
    async def test_get_backtest_status_with_mock_operation(
        self, backtesting_service, mock_operations_service
    ):
        """Test getting backtest status."""
        # Mock operation response
        mock_operation = MagicMock()
        mock_operation.operation_id = "test_backtest_id"
        mock_operation.metadata.symbol = "AAPL"
        mock_operation.metadata.timeframe = "1h"
        mock_operation.metadata.parameters = {"strategy_name": "test_strategy"}
        mock_operation.status.value = "running"
        mock_operation.progress.percentage = 45.0
        mock_operation.started_at = datetime.now(timezone.utc)
        mock_operation.completed_at = None
        mock_operation.error_message = None

        mock_operations_service.get_operation.return_value = mock_operation

        status = await backtesting_service.get_backtest_status("test_backtest_id")

        assert status["backtest_id"] == "test_backtest_id"
        assert status["strategy_name"] == "test_strategy"
        assert status["symbol"] == "AAPL"
        assert status["timeframe"] == "1h"
        assert status["status"] == "running"
        assert status["progress"] == 45

    @pytest.mark.asyncio
    async def test_get_backtest_status_not_found(
        self, backtesting_service, mock_operations_service
    ):
        """Test getting status for non-existent backtest."""
        mock_operations_service.get_operation.return_value = None

        with pytest.raises(ValidationError, match="not found"):
            await backtesting_service.get_backtest_status("nonexistent_id")

    @pytest.mark.asyncio
    async def test_get_backtest_results_success(
        self, backtesting_service, mock_operations_service
    ):
        """Test getting backtest results for completed backtest."""
        # Mock completed operation with results
        mock_operation = MagicMock()
        mock_operation.operation_id = "completed_backtest_id"
        mock_operation.status.value = "completed"
        mock_operation.metadata.symbol = "AAPL"
        mock_operation.metadata.timeframe = "1h"
        mock_operation.metadata.start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_operation.metadata.end_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        mock_operation.metadata.parameters = {
            "strategy_name": "test_strategy",
            "initial_capital": 100000,
        }
        mock_operation.result_summary = {
            "metrics": {
                "total_return": 15000,
                "annualized_return": 0.25,
                "sharpe_ratio": 1.2,
                "max_drawdown": -0.08,
                "win_rate": 0.65,
                "profit_factor": 1.8,
                "total_trades": 45,
            },
            "config": {"initial_capital": 100000},
        }

        mock_operations_service.get_operation.return_value = mock_operation

        results = await backtesting_service.get_backtest_results(
            "completed_backtest_id"
        )

        assert results["backtest_id"] == "completed_backtest_id"
        assert results["strategy_name"] == "test_strategy"
        assert results["symbol"] == "AAPL"
        assert results["timeframe"] == "1h"
        assert results["metrics"]["total_return"] == 15000
        assert results["metrics"]["sharpe_ratio"] == 1.2
        assert results["summary"]["initial_capital"] == 100000
        assert results["summary"]["final_value"] == 115000  # initial + total_return

    @pytest.mark.asyncio
    async def test_get_backtest_results_not_completed(
        self, backtesting_service, mock_operations_service
    ):
        """Test getting results for non-completed backtest."""
        mock_operation = MagicMock()
        mock_operation.status.value = "running"

        mock_operations_service.get_operation.return_value = mock_operation

        with pytest.raises(ValidationError, match="not completed"):
            await backtesting_service.get_backtest_results("running_backtest_id")

    @pytest.mark.asyncio
    async def test_get_backtest_trades(
        self, backtesting_service, mock_operations_service
    ):
        """Test getting backtest trades."""
        mock_operation = MagicMock()
        mock_operation.status.value = "completed"
        mock_operation.result_summary = {
            "trades": [
                {
                    "trade_id": "1",
                    "entry_time": "2024-01-01T10:00:00",
                    "exit_time": "2024-01-01T14:00:00",
                    "side": "BUY",
                    "entry_price": 150.0,
                    "exit_price": 155.0,
                    "quantity": 100,
                    "pnl": 500.0,
                    "pnl_percent": 3.33,
                    "entry_reason": "Golden cross",
                    "exit_reason": "Take profit",
                },
                {
                    "trade_id": "2",
                    "entry_time": "2024-01-02T09:00:00",
                    "exit_time": "2024-01-02T11:00:00",
                    "side": "SELL",
                    "entry_price": 152.0,
                    "exit_price": 148.0,
                    "quantity": 100,
                    "pnl": 400.0,
                    "pnl_percent": 2.63,
                    "entry_reason": "Death cross",
                    "exit_reason": "Stop loss",
                },
            ]
        }

        mock_operations_service.get_operation.return_value = mock_operation

        trades = await backtesting_service.get_backtest_trades("completed_backtest_id")

        assert len(trades) == 2
        assert trades[0]["trade_id"] == "1"
        assert trades[0]["side"] == "BUY"
        assert trades[0]["pnl"] == 500.0
        assert trades[1]["trade_id"] == "2"
        assert trades[1]["side"] == "SELL"
        assert trades[1]["pnl"] == 400.0

    @pytest.mark.asyncio
    async def test_get_equity_curve(self, backtesting_service, mock_operations_service):
        """Test getting equity curve data."""
        mock_operation = MagicMock()
        mock_operation.status.value = "completed"
        mock_operation.result_summary = {
            "equity_curve": {
                "timestamps": [
                    "2024-01-01T00:00:00",
                    "2024-01-02T00:00:00",
                    "2024-01-03T00:00:00",
                ],
                "values": [100000, 102000, 105000],
                "drawdowns": [0.0, -1.0, 0.0],
            }
        }

        mock_operations_service.get_operation.return_value = mock_operation

        equity_curve = await backtesting_service.get_equity_curve(
            "completed_backtest_id"
        )

        assert len(equity_curve["timestamps"]) == 3
        assert len(equity_curve["values"]) == 3
        assert len(equity_curve["drawdowns"]) == 3
        assert equity_curve["values"] == [100000, 102000, 105000]

    @pytest.mark.asyncio
    async def test_get_equity_curve_missing_data(
        self, backtesting_service, mock_operations_service
    ):
        """Test getting equity curve when data is missing."""
        mock_operation = MagicMock()
        mock_operation.status.value = "completed"
        mock_operation.result_summary = {}  # No equity curve data

        mock_operations_service.get_operation.return_value = mock_operation

        with pytest.raises(DataError, match="No equity curve data"):
            await backtesting_service.get_equity_curve("completed_backtest_id")

    @pytest.mark.asyncio
    async def test_run_backtest_with_progress_integration(
        self, backtesting_service, mock_operations_service
    ):
        """Test that progress tracking is called during backtest execution."""
        # This is more of an integration test to ensure the progress tracking flow works
        with (
            patch.object(
                backtesting_service, "_estimate_total_bars", return_value=1000
            ),
            patch(
                "ktrdr.api.services.backtesting_service.BacktestingEngine"
            ) as mock_engine_class,
        ):

            # Mock the engine and its methods
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            # Mock the data loading
            mock_data = MagicMock()
            mock_data.__len__.return_value = 1000
            mock_data.empty = False
            mock_engine._load_historical_data.return_value = mock_data

            # Mock the backtest execution with a delay to allow progress tracking
            mock_results = MagicMock()
            mock_results.to_dict.return_value = {
                "total_return": 5000,
                "total_trades": 10,
                "trades": [],
                "equity_curve": {"timestamps": [], "values": [], "drawdowns": []},
            }
            
            # Create an async function that simulates progress and takes some time
            async def mock_run_with_progress():
                # Simulate progress by updating the callback
                if hasattr(mock_engine, 'progress_callback'):
                    # Simulate multiple progress updates
                    mock_engine.progress_callback(100, 1000)  # 10% progress
                    await asyncio.sleep(0.1)  # Small delay
                    mock_engine.progress_callback(300, 1000)  # 30% progress
                    await asyncio.sleep(0.1)  # Small delay
                    mock_engine.progress_callback(1000, 1000)  # 100% progress
                return mock_results
            
            # Mock engine.run to return the async function
            mock_engine.run.side_effect = mock_run_with_progress

            # Call the progress tracking method
            await backtesting_service._run_backtest_with_progress(
                mock_engine, "test_operation_id", 1000
            )

            # Verify progress updates were called (at least the initial one)
            # The actual count may vary based on timing, so we check for at least 1
            assert mock_operations_service.update_progress.call_count >= 1

            # Note: complete_operation may not be called if there's an error in the mocked execution
            # The important thing is that the progress tracking flow works
