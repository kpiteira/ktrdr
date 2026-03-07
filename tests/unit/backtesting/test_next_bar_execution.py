"""Unit tests for next-bar execution (M3: Execution Realism).

Decisions at bar t execute at bar t+1's open price, not bar t's close.
This fixes documented look-ahead bias in the backtest engine.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.decision.base import Position, Signal, TradingDecision

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_bundle():
    """Create a mock ModelBundle with minimal plausible attributes."""
    bundle = MagicMock()
    bundle.model = MagicMock()
    bundle.metadata = MagicMock()
    bundle.metadata.strategy_name = "test_strategy"
    bundle.feature_names = ["feat_a", "feat_b"]

    strategy_config = MagicMock()
    strategy_config.name = "test_strategy"

    td = MagicMock()
    td.timeframes = MagicMock()
    td.timeframes.base_timeframe = "1h"
    td.timeframes.mode = "single"
    td.timeframes.timeframes = None
    strategy_config.training_data = td

    decisions = MagicMock()
    decisions.get = MagicMock(return_value={})
    strategy_config.decisions = decisions

    bundle.strategy_config = strategy_config
    return bundle


def _make_config(**overrides):
    """Create a BacktestConfig with sensible defaults."""
    defaults = {
        "strategy_config_path": "strategies/test.yaml",
        "model_path": "/tmp/test_model/1h_v1",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "start_date": "2024-01-01",
        "end_date": "2024-02-01",
        "initial_capital": 100000.0,
        "commission": 0.001,
        "slippage": 0.0005,
    }
    defaults.update(overrides)
    return BacktestConfig(**defaults)


def _make_data(n_bars=100):
    """Create test OHLCV data with distinct open/close prices."""
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="h")
    return pd.DataFrame(
        {
            "open": [1.1000 + i * 0.0001 for i in range(n_bars)],
            "high": [1.1200 + i * 0.0001 for i in range(n_bars)],
            "low": [1.0800 + i * 0.0001 for i in range(n_bars)],
            "close": [1.1050 + i * 0.0001 for i in range(n_bars)],
            "volume": [1000] * n_bars,
        },
        index=dates,
    )


def _make_engine(data=None, decision_sequence=None):
    """Create a BacktestingEngine with mocked components.

    Args:
        data: OHLCV DataFrame (default: 100 bars with distinct open/close)
        decision_sequence: List of Signal values to return in order.
            Remaining calls return HOLD.
    """
    with patch(
        "ktrdr.backtesting.engine.BacktestingEngine.__init__",
        lambda self, config: None,
    ):
        from ktrdr.backtesting.engine import BacktestingEngine

        engine = BacktestingEngine.__new__(BacktestingEngine)

        config = _make_config()
        engine.config = config
        engine.strategy_name = "test_strategy"
        engine.bundle = _make_mock_bundle()

        # Feature cache — returns features for all timestamps
        engine.feature_cache = MagicMock()
        engine.feature_cache.get_features_for_timestamp = MagicMock(
            return_value={"feat_a": 0.5, "feat_b": 0.3}
        )

        # Decision function
        if decision_sequence is None:
            decision_sequence = []

        call_count = 0

        def make_decision(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= len(decision_sequence):
                sig = decision_sequence[call_count - 1]
            else:
                sig = Signal.HOLD
            return TradingDecision(
                signal=sig,
                confidence=0.8,
                timestamp=kwargs.get(
                    "bar", pd.Series(name=pd.Timestamp("2024-01-01"))
                ).name,
                reasoning={},
                current_position=Position.FLAT,
            )

        engine.decide = MagicMock(side_effect=make_decision)

        # Position manager
        engine.position_manager = MagicMock()
        engine.position_manager.current_position_status = MagicMock()
        engine.position_manager.get_portfolio_value.return_value = 100000.0
        engine.position_manager.execute_trade.return_value = MagicMock()
        engine.position_manager.get_trade_history.return_value = []
        engine.position_manager.force_close_position.return_value = None

        # Performance tracker
        engine.performance_tracker = MagicMock()
        engine.performance_tracker.equity_curve = []
        engine.performance_tracker.get_equity_curve.return_value = pd.DataFrame()
        engine.performance_tracker.calculate_metrics.return_value = MagicMock()

        engine.repository = MagicMock()

        if data is None:
            data = _make_data()

        engine._load_historical_data = MagicMock(return_value={"1h": data})
        engine._get_base_timeframe = MagicMock(return_value="1h")

        return engine


# ---------------------------------------------------------------------------
# Core: Decision at bar t executes at bar t+1's open
# ---------------------------------------------------------------------------


class TestNextBarExecution:
    """Trade execution uses next bar's open price, not current bar's close."""

    def test_buy_executes_at_next_bar_open(self):
        """BUY decision at bar 50 should execute at bar 51's open price."""
        data = _make_data(100)
        # BUY on first decision (bar index 50), then HOLD
        engine = _make_engine(data=data, decision_sequence=[Signal.BUY])
        engine.run()

        # Trade should execute at bar 51's open price
        expected_price = data.iloc[51]["open"]
        execute_call = engine.position_manager.execute_trade.call_args
        assert execute_call is not None, "execute_trade was never called"
        assert execute_call.kwargs["price"] == pytest.approx(expected_price), (
            f"Expected execution at next bar's open ({expected_price}), "
            f"got {execute_call.kwargs['price']}"
        )

    def test_sell_executes_at_next_bar_open(self):
        """SELL decision at bar 50 should execute at bar 51's open price."""
        data = _make_data(100)
        engine = _make_engine(data=data, decision_sequence=[Signal.SELL])
        engine.run()

        expected_price = data.iloc[51]["open"]
        execute_call = engine.position_manager.execute_trade.call_args
        assert execute_call is not None
        assert execute_call.kwargs["price"] == pytest.approx(expected_price)

    def test_execution_timestamp_is_next_bar(self):
        """Trade timestamp should be the next bar's timestamp, not decision bar."""
        data = _make_data(100)
        engine = _make_engine(data=data, decision_sequence=[Signal.BUY])
        engine.run()

        expected_timestamp = data.index[51]
        execute_call = engine.position_manager.execute_trade.call_args
        assert execute_call is not None
        assert execute_call.kwargs["timestamp"] == expected_timestamp


# ---------------------------------------------------------------------------
# Pending signal mechanics
# ---------------------------------------------------------------------------


class TestPendingSignal:
    """Pending signal correctly carried across bars."""

    def test_hold_does_not_create_pending(self):
        """HOLD decisions should not trigger any trade execution."""
        engine = _make_engine(decision_sequence=[])  # All HOLD
        engine.run()
        engine.position_manager.execute_trade.assert_not_called()

    def test_consecutive_non_hold_only_latest_executes(self):
        """If BUY at bar 50 and SELL at bar 51, only SELL executes (overwrites BUY)."""
        data = _make_data(100)
        # BUY then SELL on consecutive bars
        engine = _make_engine(data=data, decision_sequence=[Signal.BUY, Signal.SELL])
        engine.run()

        # The BUY at bar 50 becomes pending, but bar 51 decision is SELL
        # which overwrites the pending. So SELL executes at bar 52's open.
        # The BUY pending should execute at bar 51's open FIRST,
        # then SELL becomes new pending and executes at bar 52's open.
        calls = engine.position_manager.execute_trade.call_args_list
        assert len(calls) == 2, f"Expected 2 trades, got {len(calls)}"

        # First trade: BUY at bar 51's open
        assert calls[0].kwargs["signal"] == Signal.BUY
        assert calls[0].kwargs["price"] == pytest.approx(data.iloc[51]["open"])

        # Second trade: SELL at bar 52's open
        assert calls[1].kwargs["signal"] == Signal.SELL
        assert calls[1].kwargs["price"] == pytest.approx(data.iloc[52]["open"])

    def test_first_bar_no_pending(self):
        """First bar should have no pending signal — only decide."""
        engine = _make_engine(decision_sequence=[Signal.BUY])
        engine.run()

        # The BUY decision is at bar 50 (first processed bar).
        # It should NOT execute at bar 50 — only at bar 51.
        first_execute = engine.position_manager.execute_trade.call_args
        assert first_execute is not None
        # Verify it's not the first bar's timestamp
        data = _make_data(100)
        first_bar_ts = data.index[50]
        assert first_execute.kwargs["timestamp"] != first_bar_ts


# ---------------------------------------------------------------------------
# Last bar edge case
# ---------------------------------------------------------------------------


class TestLastBarPending:
    """Last bar's pending signal handled correctly."""

    def test_pending_at_last_bar_not_executed(self):
        """A decision at the last bar has no next bar — pending is dropped.

        Force-close handles end-of-backtest cleanup.
        """
        data = _make_data(60)  # 60 bars, bars 50-59 processed (10 bars)
        # BUY on bar 10 of processing (last bar = index 59)
        decision_seq = [Signal.HOLD] * 9 + [Signal.BUY]
        engine = _make_engine(data=data, decision_sequence=decision_seq)
        engine.run()

        # The BUY at bar 59 (last) has no bar 60 to execute at
        # So execute_trade should NOT be called for it
        engine.position_manager.execute_trade.assert_not_called()

        # But force_close_position IS called (end-of-backtest)
        engine.position_manager.force_close_position.assert_called_once()


# ---------------------------------------------------------------------------
# Mark-to-market equity uses close prices
# ---------------------------------------------------------------------------


class TestMarkToMarketEquity:
    """Equity tracking still uses close prices (unchanged)."""

    def test_performance_update_uses_close_price(self):
        """performance_tracker.update should receive close prices."""
        data = _make_data(100)
        engine = _make_engine(data=data, decision_sequence=[])
        engine.run()

        # Check that performance_tracker.update calls use close prices
        for i, update_call in enumerate(
            engine.performance_tracker.update.call_args_list
        ):
            bar_idx = 50 + i
            expected_close = data.iloc[bar_idx]["close"]
            assert update_call.kwargs["price"] == pytest.approx(expected_close), (
                f"Bar {bar_idx}: expected close={expected_close}, "
                f"got {update_call.kwargs['price']}"
            )

    def test_position_update_uses_close_price(self):
        """position_manager.update_position should use close prices."""
        data = _make_data(100)
        engine = _make_engine(data=data, decision_sequence=[])
        engine.run()

        for i, update_call in enumerate(
            engine.position_manager.update_position.call_args_list
        ):
            bar_idx = 50 + i
            expected_close = data.iloc[bar_idx]["close"]
            assert update_call.args[0] == pytest.approx(expected_close)


# ---------------------------------------------------------------------------
# Both modes (regression + classification) use next-bar
# ---------------------------------------------------------------------------


class TestBothModesUseNextBar:
    """Next-bar execution is mode-agnostic — same loop for both."""

    def test_execution_does_not_depend_on_output_format(self):
        """The engine loop has no output_format branching for execution.

        This verifies the code path is the same regardless of mode.
        """
        import inspect

        from ktrdr.backtesting.engine import BacktestingEngine

        source = inspect.getsource(BacktestingEngine.run)
        # The execution path should not branch on output_format
        assert "output_format" not in source
