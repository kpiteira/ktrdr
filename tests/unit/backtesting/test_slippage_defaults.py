"""Unit tests for slippage defaults standardization (M3: Execution Realism).

All backtest entry points should default to 0.0005 (0.05%) slippage.
"""

STANDARD_SLIPPAGE = 0.0005  # 0.05%


class TestSlippageDefaults:
    """All entry points default to 0.05% slippage."""

    def test_backtest_config_default(self):
        """BacktestConfig default slippage is 0.0005."""
        from ktrdr.backtesting.engine import BacktestConfig

        config = BacktestConfig(
            strategy_config_path="s.yaml",
            model_path="/p",
            symbol="X",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
        )
        assert config.slippage == STANDARD_SLIPPAGE

    def test_worker_request_default(self):
        """BacktestRequest (worker) default slippage is 0.0005."""
        from ktrdr.backtesting.backtest_worker import (
            BacktestStartRequest as BacktestRequest,
        )

        request = BacktestRequest(
            operation_id="op_test",
            symbol="EURUSD",
            timeframe="1h",
            strategy_name="test",
            start_date="2024-01-01",
            end_date="2024-02-01",
        )
        assert request.slippage == STANDARD_SLIPPAGE

    def test_api_model_default(self):
        """BacktestStartRequest (API) default slippage is 0.0005."""
        from ktrdr.api.models.backtesting import BacktestStartRequest

        request = BacktestStartRequest(
            strategy_name="test",
            start_date="2024-01-01",
            end_date="2024-02-01",
        )
        assert request.slippage == STANDARD_SLIPPAGE

    def test_explicit_slippage_overrides(self):
        """Explicitly provided slippage should override the default."""
        from ktrdr.backtesting.engine import BacktestConfig

        config = BacktestConfig(
            strategy_config_path="s.yaml",
            model_path="/p",
            symbol="X",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            slippage=0.002,
        )
        assert config.slippage == 0.002
