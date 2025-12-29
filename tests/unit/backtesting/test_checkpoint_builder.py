"""Unit tests for backtesting checkpoint builder."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from ktrdr.checkpoint.schemas import BacktestCheckpointState


class TestBuildBacktestCheckpointState:
    """Tests for build_backtest_checkpoint_state function."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock BacktestingEngine with realistic state."""
        engine = MagicMock()

        # Mock config
        engine.config = MagicMock()
        engine.config.symbol = "EURUSD"
        engine.config.timeframe = "1h"
        engine.config.start_date = "2023-01-01"
        engine.config.end_date = "2023-12-31"
        engine.config.initial_capital = 100000.0
        engine.config.commission = 0.001
        engine.config.slippage = 0.0005

        # Mock position_manager with cash
        engine.position_manager = MagicMock()
        engine.position_manager.current_capital = 95000.0
        engine.position_manager.current_position = None  # No open position
        engine.position_manager.trade_history = []

        # Mock performance_tracker with equity curve (list of dicts, not DataFrame)
        engine.performance_tracker = MagicMock()
        engine.performance_tracker.equity_curve = [
            {
                "timestamp": f"2023-01-01T{i:02d}:00:00",
                "portfolio_value": 100000.0 + i * 10,
            }
            for i in range(1000)
        ]

        return engine

    @pytest.fixture
    def mock_engine_with_position(self, mock_engine):
        """Create a mock engine with an open position."""
        position = MagicMock()
        position.status.value = "LONG"
        position.entry_price = 1.0850
        position.entry_time = pd.Timestamp("2023-06-10T10:00:00")
        position.quantity = 100
        position.current_price = 1.0900
        mock_engine.position_manager.current_position = position
        return mock_engine

    @pytest.fixture
    def mock_engine_with_trades(self, mock_engine):
        """Create a mock engine with trade history."""
        trades = [
            MagicMock(
                trade_id=1,
                symbol="EURUSD",
                side="BUY",
                entry_price=1.0800,
                entry_time=pd.Timestamp("2023-01-15T09:00:00"),
                exit_price=1.0850,
                exit_time=pd.Timestamp("2023-01-20T14:00:00"),
                quantity=100,
                net_pnl=500.0,
                gross_pnl=550.0,
                commission=30.0,
                slippage=20.0,
                holding_period_hours=125.0,
                max_favorable_excursion=600.0,
                max_adverse_excursion=-100.0,
            ),
            MagicMock(
                trade_id=2,
                symbol="EURUSD",
                side="SELL",
                entry_price=1.0900,
                entry_time=pd.Timestamp("2023-02-10T11:00:00"),
                exit_price=1.0820,
                exit_time=pd.Timestamp("2023-02-15T16:00:00"),
                quantity=100,
                net_pnl=780.0,
                gross_pnl=800.0,
                commission=10.0,
                slippage=10.0,
                holding_period_hours=125.0,
                max_favorable_excursion=900.0,
                max_adverse_excursion=-50.0,
            ),
        ]
        mock_engine.position_manager.trade_history = trades
        return mock_engine

    def test_extracts_bar_index(self, mock_engine):
        """Should extract current bar index."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        assert state.bar_index == 500

    def test_extracts_current_date(self, mock_engine):
        """Should extract current date as ISO string."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        assert state.current_date == "2023-06-15T14:00:00"

    def test_extracts_cash(self, mock_engine):
        """Should extract current cash balance."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        assert state.cash == 95000.0

    def test_operation_type_is_backtesting(self, mock_engine):
        """Should set operation_type to 'backtesting'."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        assert state.operation_type == "backtesting"

    def test_extracts_no_positions_when_flat(self, mock_engine):
        """Should have empty positions list when no position."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        assert state.positions == []

    def test_extracts_open_position(self, mock_engine_with_position):
        """Should capture open position when one exists."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine_with_position,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        assert len(state.positions) == 1
        pos = state.positions[0]
        assert pos["symbol"] == "EURUSD"
        assert pos["quantity"] == 100
        assert pos["entry_price"] == 1.0850
        assert "entry_date" in pos

    def test_extracts_trade_history(self, mock_engine_with_trades):
        """Should capture completed trades."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine_with_trades,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        assert len(state.trades) == 2
        assert state.trades[0]["trade_id"] == 1
        assert state.trades[0]["side"] == "BUY"
        assert state.trades[0]["net_pnl"] == 500.0
        assert state.trades[1]["trade_id"] == 2
        assert state.trades[1]["side"] == "SELL"

    def test_samples_equity_curve(self, mock_engine):
        """Should sample equity curve at reasonable intervals."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        # Should have sampled equity (not all 1000 points)
        assert len(state.equity_samples) > 0
        assert len(state.equity_samples) < 1000

        # Each sample should have bar_index and equity
        for sample in state.equity_samples:
            assert "bar_index" in sample
            assert "equity" in sample

    def test_includes_original_request(self, mock_engine):
        """Should include original request for resume."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        original_request = {
            "symbol": "EURUSD",
            "timeframe": "1h",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        }

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
            original_request=original_request,
        )

        assert state.original_request == original_request

    def test_creates_original_request_from_config_if_not_provided(self, mock_engine):
        """Should create original_request from config if not explicitly provided."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        # Should extract request from engine.config
        assert state.original_request["symbol"] == "EURUSD"
        assert state.original_request["timeframe"] == "1h"
        assert state.original_request["start_date"] == "2023-01-01"
        assert state.original_request["end_date"] == "2023-12-31"

    def test_returns_dataclass(self, mock_engine):
        """Should return BacktestCheckpointState instance."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        assert isinstance(state, BacktestCheckpointState)

    def test_handles_empty_equity_curve(self, mock_engine):
        """Should handle empty equity curve gracefully."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        mock_engine.performance_tracker.equity_curve = []

        state = build_backtest_checkpoint_state(
            engine=mock_engine,
            bar_index=0,
            current_timestamp=pd.Timestamp("2023-01-01T00:00:00"),
        )

        assert state.equity_samples == []

    def test_trade_serialization_includes_key_fields(self, mock_engine_with_trades):
        """Trade dictionaries should include all fields needed for restore."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine_with_trades,
            bar_index=500,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        trade = state.trades[0]
        required_fields = [
            "trade_id",
            "symbol",
            "side",
            "entry_price",
            "exit_price",
            "quantity",
            "net_pnl",
        ]
        for field in required_fields:
            assert field in trade, f"Missing required field: {field}"


class TestEquitySampling:
    """Tests for equity curve sampling behavior."""

    @pytest.fixture
    def mock_engine_large_equity(self):
        """Create engine with large equity curve."""
        engine = MagicMock()
        engine.config = MagicMock()
        engine.config.symbol = "EURUSD"
        engine.config.timeframe = "1h"
        engine.config.start_date = "2020-01-01"
        engine.config.end_date = "2024-01-01"
        engine.config.initial_capital = 100000.0

        engine.position_manager = MagicMock()
        engine.position_manager.current_capital = 150000.0
        engine.position_manager.current_position = None
        engine.position_manager.trade_history = []

        # Large equity curve (35,000 bars) - list of dicts, not DataFrame
        engine.performance_tracker = MagicMock()
        engine.performance_tracker.equity_curve = [
            {"timestamp": f"2020-01-01T{i:05d}", "portfolio_value": 100000.0 + i * 1.5}
            for i in range(35000)
        ]
        return engine

    def test_samples_large_equity_curve(self, mock_engine_large_equity):
        """Large equity curves should be sampled, not stored fully."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine_large_equity,
            bar_index=30000,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        # Should be sampled (not all 35000 points)
        assert len(state.equity_samples) < 500
        assert len(state.equity_samples) > 0

    def test_sampling_preserves_chronological_order(self, mock_engine_large_equity):
        """Samples should be in chronological order."""
        from ktrdr.backtesting.checkpoint_builder import build_backtest_checkpoint_state

        state = build_backtest_checkpoint_state(
            engine=mock_engine_large_equity,
            bar_index=30000,
            current_timestamp=pd.Timestamp("2023-06-15T14:00:00"),
        )

        bar_indices = [s["bar_index"] for s in state.equity_samples]
        assert bar_indices == sorted(bar_indices)
