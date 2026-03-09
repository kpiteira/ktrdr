"""Unit tests for multi-timeframe backtest configuration (M1, Task 1.1).

Tests the `timeframes` field on BacktestConfig and BacktestStartRequest,
and the `get_all_timeframes()` helper method.
"""

from ktrdr.backtesting.engine import BacktestConfig


class TestBacktestConfigTimeframes:
    """Tests for BacktestConfig.timeframes field and get_all_timeframes()."""

    def test_default_timeframes_is_empty_list(self) -> None:
        """BacktestConfig with no timeframes should default to empty list."""
        config = BacktestConfig(
            strategy_config_path="strategies/test.yaml",
            model_path="/tmp/model",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
        )
        assert config.timeframes == []

    def test_get_all_timeframes_falls_back_to_single(self) -> None:
        """When timeframes is empty, get_all_timeframes returns [timeframe]."""
        config = BacktestConfig(
            strategy_config_path="strategies/test.yaml",
            model_path="/tmp/model",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
        )
        assert config.get_all_timeframes() == ["1h"]

    def test_get_all_timeframes_returns_explicit_list(self) -> None:
        """When timeframes is set, get_all_timeframes returns it."""
        config = BacktestConfig(
            strategy_config_path="strategies/test.yaml",
            model_path="/tmp/model",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            timeframes=["1h", "1d"],
        )
        assert config.get_all_timeframes() == ["1h", "1d"]

    def test_existing_single_tf_config_unchanged(self) -> None:
        """Existing single-TF config construction still works without timeframes."""
        config = BacktestConfig(
            strategy_config_path="strategies/test.yaml",
            model_path="/tmp/model",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            initial_capital=50000.0,
            commission=0.002,
            slippage=0.001,
        )
        assert config.timeframe == "1h"
        assert config.initial_capital == 50000.0
        assert config.commission == 0.002
        assert config.slippage == 0.001

    def test_get_all_timeframes_three_timeframes(self) -> None:
        """Supports more than two timeframes."""
        config = BacktestConfig(
            strategy_config_path="strategies/test.yaml",
            model_path="/tmp/model",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            timeframes=["1h", "4h", "1d"],
        )
        assert config.get_all_timeframes() == ["1h", "4h", "1d"]


class TestBacktestStartRequestTimeframes:
    """Tests for BacktestStartRequest.timeframes field."""

    def test_default_timeframes_is_empty_list(self) -> None:
        """BacktestStartRequest with no timeframes defaults to empty list."""
        from ktrdr.backtesting.backtest_worker import BacktestStartRequest

        req = BacktestStartRequest(
            task_id="test-task-1",
            symbol="EURUSD",
            timeframe="1h",
            strategy_name="test_strategy",
            start_date="2024-01-01",
            end_date="2024-02-01",
        )
        assert req.timeframes == []

    def test_timeframes_serialization(self) -> None:
        """BacktestStartRequest serialization includes timeframes field."""
        from ktrdr.backtesting.backtest_worker import BacktestStartRequest

        req = BacktestStartRequest(
            task_id="test-task-1",
            symbol="EURUSD",
            timeframe="1h",
            strategy_name="test_strategy",
            start_date="2024-01-01",
            end_date="2024-02-01",
            timeframes=["1h", "1d"],
        )
        data = req.model_dump()
        assert data["timeframes"] == ["1h", "1d"]

    def test_timeframes_deserialization(self) -> None:
        """BacktestStartRequest can be created from dict with timeframes."""
        from ktrdr.backtesting.backtest_worker import BacktestStartRequest

        req = BacktestStartRequest.model_validate(
            {
                "task_id": "test-task-1",
                "symbol": "EURUSD",
                "timeframe": "1h",
                "strategy_name": "test_strategy",
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "timeframes": ["1h", "4h", "1d"],
            }
        )
        assert req.timeframes == ["1h", "4h", "1d"]

    def test_backward_compat_no_timeframes_in_payload(self) -> None:
        """Request without timeframes field works (backward compat)."""
        from ktrdr.backtesting.backtest_worker import BacktestStartRequest

        req = BacktestStartRequest.model_validate(
            {
                "task_id": "test-task-1",
                "symbol": "EURUSD",
                "timeframe": "1h",
                "strategy_name": "test_strategy",
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
            }
        )
        assert req.timeframes == []
