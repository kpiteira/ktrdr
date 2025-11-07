"""Unit tests for BacktestProgressBridge.

This test suite verifies Task 2.2 requirements:
- Inherits from ProgressBridge
- Implements update_progress() method
- Thread-safe via base class
- Provides get_status() interface
"""

import pytest

from ktrdr.async_infrastructure.progress_bridge import ProgressBridge
from ktrdr.backtesting.progress_bridge import BacktestProgressBridge


class TestBacktestProgressBridgeInitialization:
    """Test BacktestProgressBridge initialization."""

    def test_inherits_from_progress_bridge(self):
        """Test that BacktestProgressBridge inherits from ProgressBridge."""
        bridge = BacktestProgressBridge(
            operation_id="test-op-123",
            symbol="AAPL",
            timeframe="1h",
            total_bars=1000,
        )

        assert isinstance(bridge, ProgressBridge)

    def test_initialization_with_required_parameters(self):
        """Test initialization with all required parameters."""
        bridge = BacktestProgressBridge(
            operation_id="test-op-456",
            symbol="EURUSD",
            timeframe="1d",
            total_bars=500,
        )

        assert bridge.operation_id == "test-op-456"
        assert bridge.symbol == "EURUSD"
        assert bridge.timeframe == "1d"
        assert bridge.total_bars == 500

    def test_initialization_stores_metadata(self):
        """Test that initialization stores all metadata correctly."""
        bridge = BacktestProgressBridge(
            operation_id="op-abc",
            symbol="TEST",
            timeframe="5m",
            total_bars=10000,
        )

        # Verify all instance variables are set
        assert hasattr(bridge, "operation_id")
        assert hasattr(bridge, "symbol")
        assert hasattr(bridge, "timeframe")
        assert hasattr(bridge, "total_bars")


class TestBacktestProgressBridgeUpdateProgress:
    """Test update_progress() functionality."""

    @pytest.fixture
    def bridge(self):
        """Create a BacktestProgressBridge for testing."""
        return BacktestProgressBridge(
            operation_id="test-op", symbol="AAPL", timeframe="1h", total_bars=1000
        )

    def test_update_progress_method_exists(self, bridge):
        """Test that update_progress() method exists."""
        assert hasattr(bridge, "update_progress")
        assert callable(bridge.update_progress)

    def test_update_progress_accepts_required_parameters(self, bridge):
        """Test that update_progress() accepts all required parameters."""
        # Should not raise any exception
        bridge.update_progress(
            current_bar=100,
            total_bars=1000,
            current_date="2024-01-15",
            current_pnl=1234.56,
            total_trades=5,
            win_rate=0.60,
        )

    def test_update_progress_calculates_percentage_correctly(self, bridge):
        """Test that update_progress() calculates percentage correctly."""
        bridge.update_progress(
            current_bar=250,
            total_bars=1000,
            current_date="2024-01-15",
            current_pnl=500.0,
            total_trades=2,
            win_rate=0.50,
        )

        status = bridge.get_status()
        assert "percentage" in status
        assert status["percentage"] == 25.0  # 250/1000 * 100

    def test_update_progress_with_zero_total_bars_does_not_crash(self, bridge):
        """Test that zero total_bars doesn't cause division by zero."""
        # Should handle gracefully (use max(1, total_bars))
        bridge.update_progress(
            current_bar=0,
            total_bars=0,
            current_date="2024-01-15",
            current_pnl=0.0,
            total_trades=0,
            win_rate=0.0,
        )

        status = bridge.get_status()
        assert "percentage" in status
        # Should be 0.0 (0 / max(1, 0) * 100)
        assert status["percentage"] == 0.0

    def test_update_progress_creates_formatted_message(self, bridge):
        """Test that update_progress() creates properly formatted message."""
        bridge.update_progress(
            current_bar=500,
            total_bars=1000,
            current_date="2024-01-20 10:30:00",
            current_pnl=2500.0,
            total_trades=10,
            win_rate=0.70,
        )

        status = bridge.get_status()
        assert "message" in status
        # Message should include symbol, timeframe, and date
        assert "AAPL" in status["message"]
        assert "1h" in status["message"]
        assert "2024-01-20" in status["message"]

    def test_update_progress_includes_all_fields_in_state(self, bridge):
        """Test that all progress fields are included in state."""
        bridge.update_progress(
            current_bar=750,
            total_bars=1000,
            current_date="2024-01-25",
            current_pnl=3500.50,
            total_trades=15,
            win_rate=0.67,
        )

        status = bridge.get_status()

        # All required fields should be present
        assert "percentage" in status
        assert "message" in status
        assert "current_bar" in status
        assert "total_bars" in status
        assert "current_date" in status
        assert "current_pnl" in status
        assert "total_trades" in status
        assert "win_rate" in status

        # Verify values
        assert status["current_bar"] == 750
        assert status["total_bars"] == 1000
        assert status["current_date"] == "2024-01-25"
        assert status["current_pnl"] == 3500.50
        assert status["total_trades"] == 15
        assert status["win_rate"] == 0.67

    def test_update_progress_includes_timestamp(self, bridge):
        """Test that update_progress() includes timestamp in state."""
        bridge.update_progress(
            current_bar=100,
            total_bars=1000,
            current_date="2024-01-15",
            current_pnl=100.0,
            total_trades=1,
            win_rate=1.0,
        )

        status = bridge.get_status()
        assert "timestamp" in status
        # Timestamp should be ISO format
        assert "T" in status["timestamp"]  # ISO format has T separator

    def test_update_progress_multiple_times_updates_state(self, bridge):
        """Test that calling update_progress() multiple times updates the state."""
        # First update
        bridge.update_progress(
            current_bar=100,
            total_bars=1000,
            current_date="2024-01-15",
            current_pnl=100.0,
            total_trades=1,
            win_rate=0.50,
        )

        status1 = bridge.get_status()
        assert status1["current_bar"] == 100

        # Second update
        bridge.update_progress(
            current_bar=500,
            total_bars=1000,
            current_date="2024-01-20",
            current_pnl=500.0,
            total_trades=5,
            win_rate=0.60,
        )

        status2 = bridge.get_status()
        assert status2["current_bar"] == 500
        assert status2["percentage"] == 50.0

    def test_update_progress_with_negative_pnl(self, bridge):
        """Test that negative P&L is handled correctly."""
        bridge.update_progress(
            current_bar=500,
            total_bars=1000,
            current_date="2024-01-20",
            current_pnl=-1500.75,
            total_trades=8,
            win_rate=0.375,
        )

        status = bridge.get_status()
        assert status["current_pnl"] == -1500.75

    def test_update_progress_with_zero_win_rate(self, bridge):
        """Test that zero win rate is handled correctly."""
        bridge.update_progress(
            current_bar=100,
            total_bars=1000,
            current_date="2024-01-15",
            current_pnl=-500.0,
            total_trades=5,
            win_rate=0.0,
        )

        status = bridge.get_status()
        assert status["win_rate"] == 0.0


class TestBacktestProgressBridgeThreadSafety:
    """Test thread safety (inherited from ProgressBridge)."""

    def test_get_status_returns_copy_not_reference(self):
        """Test that get_status() returns a copy, not a reference."""
        bridge = BacktestProgressBridge(
            operation_id="test-op", symbol="AAPL", timeframe="1h", total_bars=1000
        )

        bridge.update_progress(
            current_bar=100,
            total_bars=1000,
            current_date="2024-01-15",
            current_pnl=100.0,
            total_trades=1,
            win_rate=0.50,
        )

        status1 = bridge.get_status()
        status2 = bridge.get_status()

        # Should be equal but not the same object
        assert status1 == status2
        assert status1 is not status2

    def test_modifying_returned_status_does_not_affect_internal_state(self):
        """Test that modifying returned status doesn't affect bridge state."""
        bridge = BacktestProgressBridge(
            operation_id="test-op", symbol="AAPL", timeframe="1h", total_bars=1000
        )

        bridge.update_progress(
            current_bar=100,
            total_bars=1000,
            current_date="2024-01-15",
            current_pnl=100.0,
            total_trades=1,
            win_rate=0.50,
        )

        status = bridge.get_status()
        original_bar = status["current_bar"]

        # Modify returned status
        status["current_bar"] = 999

        # Get status again - should be unchanged
        new_status = bridge.get_status()
        assert new_status["current_bar"] == original_bar


class TestBacktestProgressBridgeGetMetrics:
    """Test get_metrics() interface (inherited from ProgressBridge)."""

    def test_get_metrics_method_exists(self):
        """Test that get_metrics() method exists (inherited)."""
        bridge = BacktestProgressBridge(
            operation_id="test-op", symbol="AAPL", timeframe="1h", total_bars=1000
        )

        assert hasattr(bridge, "get_metrics")
        assert callable(bridge.get_metrics)

    def test_get_metrics_returns_empty_initially(self):
        """Test that get_metrics() returns empty list initially."""
        bridge = BacktestProgressBridge(
            operation_id="test-op", symbol="AAPL", timeframe="1h", total_bars=1000
        )

        metrics, cursor = bridge.get_metrics(0)

        assert metrics == []
        assert cursor == 0


class TestBacktestProgressBridgeEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_100_percent_progress(self):
        """Test that 100% progress works correctly."""
        bridge = BacktestProgressBridge(
            operation_id="test-op", symbol="AAPL", timeframe="1h", total_bars=1000
        )

        bridge.update_progress(
            current_bar=1000,
            total_bars=1000,
            current_date="2024-01-31",
            current_pnl=5000.0,
            total_trades=50,
            win_rate=0.60,
        )

        status = bridge.get_status()
        assert status["percentage"] == 100.0

    def test_over_100_percent_progress(self):
        """Test handling of progress > 100%."""
        bridge = BacktestProgressBridge(
            operation_id="test-op", symbol="AAPL", timeframe="1h", total_bars=1000
        )

        bridge.update_progress(
            current_bar=1100,
            total_bars=1000,
            current_date="2024-01-31",
            current_pnl=5000.0,
            total_trades=50,
            win_rate=0.60,
        )

        status = bridge.get_status()
        # Should allow >100% (use approximate comparison for floating point)
        assert abs(status["percentage"] - 110.0) < 0.001

    def test_empty_date_string(self):
        """Test handling of empty date string."""
        bridge = BacktestProgressBridge(
            operation_id="test-op", symbol="AAPL", timeframe="1h", total_bars=1000
        )

        bridge.update_progress(
            current_bar=100,
            total_bars=1000,
            current_date="",
            current_pnl=100.0,
            total_trades=1,
            win_rate=0.50,
        )

        status = bridge.get_status()
        assert status["current_date"] == ""
