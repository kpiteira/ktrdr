"""Unit tests for BacktestProgressBridge checkpoint state caching.

This module tests the checkpoint state caching functionality added in Task 3.7,
which enables cancellation checkpoints to contain full domain state (portfolio,
positions, trades) instead of just lightweight progress metadata.
"""

import pytest

from ktrdr.backtesting.progress_bridge import BacktestProgressBridge


@pytest.fixture
def progress_bridge():
    """Create BacktestProgressBridge for testing."""
    return BacktestProgressBridge(
        operation_id="backtest_op_001",
        symbol="AAPL",
        timeframe="1h",
        total_bars=10000,
    )


class TestBacktestProgressBridgeCheckpointCaching:
    """Test suite for checkpoint state caching in BacktestProgressBridge."""

    def test_set_latest_checkpoint_state_caches_data(self, progress_bridge):
        """Test that set_latest_checkpoint_state() caches checkpoint data."""
        checkpoint_data = {
            "current_bar_index": 5000,
            "current_timestamp": "2024-06-15T14:30:00",
            "current_price": 185.25,
            "portfolio_state": {
                "cash": 52000.0,
                "positions": [{"symbol": "AAPL", "shares": 100, "avg_price": 180.0}],
            },
            "trade_history": [
                {
                    "entry_price": 175.0,
                    "exit_price": 178.5,
                    "shares": 100,
                    "pnl": 350.0,
                }
            ],
            "performance_metrics": {
                "total_return": 0.075,
                "sharpe_ratio": 1.5,
            },
        }

        # Cache checkpoint state
        progress_bridge.set_latest_checkpoint_state(checkpoint_data)

        # Verify cached data is accessible (internal state check)
        assert progress_bridge._latest_checkpoint_data == checkpoint_data

    @pytest.mark.asyncio
    async def test_get_state_returns_cached_checkpoint_data(self, progress_bridge):
        """Test that get_state() returns cached checkpoint data."""
        checkpoint_data = {
            "current_bar_index": 5000,
            "portfolio_state": {
                "cash": 52000.0,
                "positions": [{"symbol": "AAPL", "shares": 100}],
            },
            "trade_history": [{"pnl": 350.0}],
        }

        # Cache state
        progress_bridge.set_latest_checkpoint_state(checkpoint_data)

        # Get state (should include cached data)
        state = await progress_bridge.get_state()

        # Verify state contains progress info
        assert state["operation_id"] == "backtest_op_001"
        assert state["operation_type"] == "backtesting"
        assert state["status"] == "running"

        # Verify state contains cached checkpoint data
        assert "checkpoint_data" in state
        assert state["checkpoint_data"]["current_bar_index"] == 5000
        assert state["checkpoint_data"]["portfolio_state"]["cash"] == 52000.0
        assert len(state["checkpoint_data"]["trade_history"]) == 1

    @pytest.mark.asyncio
    async def test_get_state_without_cached_data_returns_basic_state(
        self, progress_bridge
    ):
        """Test that get_state() returns basic state when no checkpoint cached."""
        # Update progress first
        progress_bridge.update_progress(
            current_bar=100,
            total_bars=10000,
            current_date="2024-01-01",
            current_pnl=1000.0,
            total_trades=5,
            win_rate=0.6,
        )

        # Get state without caching checkpoint data
        state = await progress_bridge.get_state()

        # Should return basic state
        assert state["operation_id"] == "backtest_op_001"
        assert state["operation_type"] == "backtesting"
        assert state["status"] == "running"
        assert "progress" in state
        assert state["progress"]["percentage"] > 0  # Some progress

    @pytest.mark.asyncio
    async def test_get_state_includes_current_progress(self, progress_bridge):
        """Test that get_state() includes current progress info."""
        # Update progress
        progress_bridge.update_progress(
            current_bar=5000,
            total_bars=10000,
            current_date="2024-06-15",
            current_pnl=5000.0,
            total_trades=25,
            win_rate=0.68,
        )

        # Get state (should include current progress)
        state = await progress_bridge.get_state()

        # Verify progress included
        assert "progress" in state
        assert state["progress"]["percentage"] == 50.0  # 5000/10000
        assert "Backtesting AAPL 1h" in state["progress"]["message"]

    @pytest.mark.asyncio
    async def test_multiple_set_checkpoint_state_updates_cache(self, progress_bridge):
        """Test that calling set_latest_checkpoint_state() multiple times updates cache."""
        # First checkpoint
        checkpoint_data_1 = {
            "current_bar_index": 1000,
            "portfolio_state": {"cash": 100000.0},
        }
        progress_bridge.set_latest_checkpoint_state(checkpoint_data_1)

        # Second checkpoint (should replace first)
        checkpoint_data_2 = {
            "current_bar_index": 5000,
            "portfolio_state": {"cash": 105000.0},
        }
        progress_bridge.set_latest_checkpoint_state(checkpoint_data_2)

        # Get state (should have second checkpoint)
        state = await progress_bridge.get_state()

        assert state["checkpoint_data"]["current_bar_index"] == 5000
        assert state["checkpoint_data"]["portfolio_state"]["cash"] == 105000.0

    @pytest.mark.asyncio
    async def test_get_state_started_at_included(self, progress_bridge):
        """Test that get_state() includes started_at timestamp if available."""
        from datetime import datetime

        progress_bridge.started_at = datetime.now()

        state = await progress_bridge.get_state()

        # Should include started_at
        assert state["started_at"] is not None
        assert isinstance(state["started_at"], str)  # ISO format
