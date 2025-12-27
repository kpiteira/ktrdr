"""Unit tests for backtest checkpoint restore functionality."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest


class TestBacktestResumeContext:
    """Tests for BacktestResumeContext dataclass."""

    def test_context_has_required_fields(self):
        """Context should have all required fields for resume."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        # Create context with required fields
        context = BacktestResumeContext(
            start_bar=5001,
            cash=100000.0,
            original_request={"symbol": "EURUSD", "timeframe": "1h"},
        )

        assert context.start_bar == 5001
        assert context.cash == 100000.0
        assert context.original_request == {"symbol": "EURUSD", "timeframe": "1h"}

    def test_context_has_optional_fields(self):
        """Context should support optional positions, trades, and equity."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=5001,
            cash=95000.0,
            original_request={"symbol": "EURUSD"},
            positions=[{"symbol": "EURUSD", "quantity": 1000, "entry_price": 1.1000}],
            trades=[{"symbol": "EURUSD", "side": "BUY", "quantity": 500, "pnl": 100.0}],
            equity_samples=[{"bar_index": 0, "equity": 100000.0}],
        )

        assert len(context.positions) == 1
        assert context.positions[0]["symbol"] == "EURUSD"
        assert len(context.trades) == 1
        assert context.trades[0]["pnl"] == 100.0
        assert len(context.equity_samples) == 1

    def test_context_defaults_for_optional_fields(self):
        """Optional fields should have sensible defaults."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=5001,
            cash=100000.0,
            original_request={"symbol": "EURUSD"},
        )

        assert context.positions == []
        assert context.trades == []
        assert context.equity_samples == []


class TestRestoreFromCheckpoint:
    """Tests for restore_from_checkpoint function."""

    @pytest.fixture
    def mock_checkpoint_service(self):
        """Create a mock CheckpointService."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def sample_checkpoint_data(self):
        """Create sample backtest checkpoint data."""
        from ktrdr.checkpoint.checkpoint_service import CheckpointData

        return CheckpointData(
            operation_id="op_backtest_123",
            checkpoint_type="periodic",
            created_at=datetime.now(),
            state={
                "operation_type": "backtesting",
                "bar_index": 5000,
                "current_date": "2023-06-15T14:00:00",
                "cash": 105000.0,
                "positions": [
                    {
                        "symbol": "EURUSD",
                        "quantity": 1000,
                        "entry_price": 1.1000,
                        "entry_date": "2023-06-10T10:00:00",
                    }
                ],
                "trades": [
                    {
                        "symbol": "EURUSD",
                        "side": "BUY",
                        "quantity": 500,
                        "price": 1.0950,
                        "date": "2023-05-01T09:00:00",
                        "pnl": 250.0,
                    }
                ],
                "equity_samples": [
                    {"bar_index": 0, "equity": 100000.0},
                    {"bar_index": 100, "equity": 100500.0},
                    {"bar_index": 200, "equity": 101000.0},
                ],
                "original_request": {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                },
            },
            artifacts_path=None,  # No artifacts for backtesting
            artifacts=None,
        )

    @pytest.mark.asyncio
    async def test_loads_checkpoint_from_service(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should load checkpoint from CheckpointService."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        _context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_123",
        )

        # Should load without artifacts (load_artifacts=False for backtesting)
        mock_checkpoint_service.load_checkpoint.assert_called_once_with(
            "op_backtest_123", load_artifacts=False
        )
        assert _context is not None

    @pytest.mark.asyncio
    async def test_raises_when_no_checkpoint(self, mock_checkpoint_service):
        """Should raise when checkpoint not found."""
        from ktrdr.backtesting.checkpoint_restore import (
            CheckpointNotFoundError,
            restore_from_checkpoint,
        )

        mock_checkpoint_service.load_checkpoint.return_value = None

        with pytest.raises(CheckpointNotFoundError) as exc_info:
            await restore_from_checkpoint(
                checkpoint_service=mock_checkpoint_service,
                operation_id="op_backtest_123",
            )

        assert "op_backtest_123" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_start_bar_is_checkpoint_bar_plus_one(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Resume should start from checkpoint bar + 1 (per design D7)."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_123",
        )

        # Checkpoint at bar 5000, resume from bar 5001
        assert context.start_bar == 5001

    @pytest.mark.asyncio
    async def test_cash_restored(self, mock_checkpoint_service, sample_checkpoint_data):
        """Should restore cash from checkpoint."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_123",
        )

        assert context.cash == 105000.0

    @pytest.mark.asyncio
    async def test_positions_restored(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should restore positions from checkpoint."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_123",
        )

        assert len(context.positions) == 1
        assert context.positions[0]["symbol"] == "EURUSD"
        assert context.positions[0]["quantity"] == 1000
        assert context.positions[0]["entry_price"] == 1.1000

    @pytest.mark.asyncio
    async def test_trades_restored(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should restore trade history from checkpoint."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_123",
        )

        assert len(context.trades) == 1
        assert context.trades[0]["pnl"] == 250.0

    @pytest.mark.asyncio
    async def test_equity_samples_restored(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should restore equity samples from checkpoint."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_123",
        )

        assert len(context.equity_samples) == 3
        assert context.equity_samples[0]["equity"] == 100000.0

    @pytest.mark.asyncio
    async def test_original_request_restored(
        self, mock_checkpoint_service, sample_checkpoint_data
    ):
        """Should restore original request for data reload."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_123",
        )

        assert context.original_request["symbol"] == "EURUSD"
        assert context.original_request["timeframe"] == "1h"
        assert context.original_request["start_date"] == "2023-01-01"
        assert context.original_request["end_date"] == "2023-12-31"


class TestRestoreWithEmptyOptionalFields:
    """Tests for restore when optional fields are missing."""

    @pytest.fixture
    def mock_checkpoint_service(self):
        """Create a mock CheckpointService."""
        return AsyncMock()

    @pytest.fixture
    def minimal_checkpoint_data(self):
        """Create minimal backtest checkpoint data (no positions/trades)."""
        from ktrdr.checkpoint.checkpoint_service import CheckpointData

        return CheckpointData(
            operation_id="op_backtest_minimal",
            checkpoint_type="cancellation",
            created_at=datetime.now(),
            state={
                "operation_type": "backtesting",
                "bar_index": 1000,
                "current_date": "2023-02-15T10:00:00",
                "cash": 100000.0,
                # No positions, trades, equity_samples, or original_request
            },
            artifacts_path=None,
            artifacts=None,
        )

    @pytest.mark.asyncio
    async def test_empty_positions_when_not_in_checkpoint(
        self, mock_checkpoint_service, minimal_checkpoint_data
    ):
        """Should return empty positions when not in checkpoint."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = minimal_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_minimal",
        )

        assert context.positions == []

    @pytest.mark.asyncio
    async def test_empty_trades_when_not_in_checkpoint(
        self, mock_checkpoint_service, minimal_checkpoint_data
    ):
        """Should return empty trades when not in checkpoint."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = minimal_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_minimal",
        )

        assert context.trades == []

    @pytest.mark.asyncio
    async def test_empty_equity_samples_when_not_in_checkpoint(
        self, mock_checkpoint_service, minimal_checkpoint_data
    ):
        """Should return empty equity samples when not in checkpoint."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = minimal_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_minimal",
        )

        assert context.equity_samples == []

    @pytest.mark.asyncio
    async def test_empty_original_request_when_not_in_checkpoint(
        self, mock_checkpoint_service, minimal_checkpoint_data
    ):
        """Should return empty original_request when not in checkpoint."""
        from ktrdr.backtesting.checkpoint_restore import restore_from_checkpoint

        mock_checkpoint_service.load_checkpoint.return_value = minimal_checkpoint_data

        context = await restore_from_checkpoint(
            checkpoint_service=mock_checkpoint_service,
            operation_id="op_backtest_minimal",
        )

        assert context.original_request == {}


class TestBacktestWorkerRestoreMethod:
    """Tests for BacktestWorker.restore_from_checkpoint method integration."""

    @pytest.fixture
    def sample_checkpoint_data(self):
        """Create sample checkpoint data for worker tests."""
        from ktrdr.checkpoint.checkpoint_service import CheckpointData

        return CheckpointData(
            operation_id="op_worker_test",
            checkpoint_type="cancellation",
            created_at=datetime.now(),
            state={
                "operation_type": "backtesting",
                "bar_index": 7500,
                "current_date": "2023-08-20T16:00:00",
                "cash": 98000.0,
                "positions": [],
                "trades": [{"pnl": -2000.0}],
                "equity_samples": [{"bar_index": 7500, "equity": 98000.0}],
                "original_request": {"symbol": "GBPUSD"},
            },
            artifacts_path=None,
            artifacts=None,
        )

    @pytest.mark.asyncio
    async def test_worker_has_restore_method(self):
        """BacktestWorker should have restore_from_checkpoint method."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        # Check the method exists on the class
        assert hasattr(BacktestWorker, "restore_from_checkpoint")

    @pytest.mark.asyncio
    async def test_worker_restore_returns_context(self, sample_checkpoint_data):
        """Worker restore should return BacktestResumeContext."""
        from unittest.mock import MagicMock, patch

        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        # Create mock checkpoint service
        mock_checkpoint_service = AsyncMock()
        mock_checkpoint_service.load_checkpoint.return_value = sample_checkpoint_data

        # Mock the BacktestWorker to avoid full initialization
        with patch(
            "ktrdr.backtesting.backtest_worker.BacktestWorker.__init__",
            lambda self: None,
        ):
            from ktrdr.backtesting.backtest_worker import BacktestWorker

            worker = BacktestWorker()
            worker._checkpoint_service = mock_checkpoint_service
            worker._get_checkpoint_service = MagicMock(
                return_value=mock_checkpoint_service
            )

            context = await worker.restore_from_checkpoint("op_worker_test")

            assert isinstance(context, BacktestResumeContext)
            assert context.start_bar == 7501  # bar_index + 1
            assert context.cash == 98000.0
