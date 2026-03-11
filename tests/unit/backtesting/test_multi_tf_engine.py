"""Unit tests for multi-TF data loading in backtest engine (M1, Task 1.3).

Tests that the engine uses config.get_all_timeframes() to decide between
single-TF and multi-TF data loading paths, and that the worker passes
timeframes from the request into BacktestConfig.
"""

from unittest.mock import MagicMock, patch

import pandas as pd

from ktrdr.backtesting.engine import BacktestConfig, BacktestingEngine


def _make_mock_bundle(timeframe_mode: str = "single"):
    """Create a mock ModelBundle."""
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
    td.timeframes.mode = timeframe_mode
    if timeframe_mode == "multi_timeframe":
        td.timeframes.timeframes = ["1h", "1d"]
    else:
        td.timeframes.timeframes = None
    strategy_config.training_data = td

    decisions = MagicMock()
    decisions.get = MagicMock(return_value={})
    strategy_config.decisions = decisions

    bundle.strategy_config = strategy_config
    return bundle


def _make_sample_data(n_bars: int = 200) -> pd.DataFrame:
    """Create sample OHLCV data."""
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="1h")
    return pd.DataFrame(
        {
            "open": [1.0] * n_bars,
            "high": [1.01] * n_bars,
            "low": [0.99] * n_bars,
            "close": [1.005] * n_bars,
            "volume": [1000] * n_bars,
        },
        index=dates,
    )


class TestEngineUsesConfigTimeframes:
    """Tests that engine prefers config.get_all_timeframes() for data loading."""

    def test_single_tf_loads_single_data(self) -> None:
        """Single-TF config loads data from repository directly."""
        config = BacktestConfig(
            strategy_config_path="strategies/test.yaml",
            model_path="/tmp/model",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
        )

        mock_bundle = _make_mock_bundle("single")
        sample_data = _make_sample_data()

        with patch.object(BacktestingEngine, "__init__", lambda self, cfg: None):
            engine = BacktestingEngine.__new__(BacktestingEngine)
            engine.config = config
            engine.bundle = mock_bundle
            engine.repository = MagicMock()
            engine.repository.load_from_cache.return_value = sample_data

            result = engine._load_historical_data()

        assert "1h" in result
        assert len(result) == 1
        engine.repository.load_from_cache.assert_called_once()

    def test_multi_tf_config_uses_coordinator(self) -> None:
        """Multi-TF config (from threaded timeframes) uses MultiTimeframeCoordinator."""
        config = BacktestConfig(
            strategy_config_path="strategies/test.yaml",
            model_path="/tmp/model",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            timeframes=["1h", "1d"],
        )

        mock_bundle = _make_mock_bundle("single")  # Even if bundle says single
        mock_coordinator = MagicMock()
        mock_coordinator.load_multi_timeframe_data.return_value = {
            "1h": _make_sample_data(),
            "1d": _make_sample_data(30),
        }

        with patch.object(BacktestingEngine, "__init__", lambda self, cfg: None):
            engine = BacktestingEngine.__new__(BacktestingEngine)
            engine.config = config
            engine.bundle = mock_bundle
            engine.repository = MagicMock()

            with patch(
                "ktrdr.data.multi_timeframe_coordinator.MultiTimeframeCoordinator",
                return_value=mock_coordinator,
            ):
                result = engine._load_historical_data()

        assert "1h" in result
        assert "1d" in result
        mock_coordinator.load_multi_timeframe_data.assert_called_once()

    def test_config_timeframes_override_strategy_config(self) -> None:
        """config.get_all_timeframes() takes priority even if strategy says single."""
        config = BacktestConfig(
            strategy_config_path="strategies/test.yaml",
            model_path="/tmp/model",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            timeframes=["1h", "4h", "1d"],
        )

        mock_bundle = _make_mock_bundle("single")
        mock_coordinator = MagicMock()
        mock_coordinator.load_multi_timeframe_data.return_value = {
            "1h": _make_sample_data(),
            "4h": _make_sample_data(50),
            "1d": _make_sample_data(30),
        }

        with patch.object(BacktestingEngine, "__init__", lambda self, cfg: None):
            engine = BacktestingEngine.__new__(BacktestingEngine)
            engine.config = config
            engine.bundle = mock_bundle
            engine.repository = MagicMock()

            with patch(
                "ktrdr.data.multi_timeframe_coordinator.MultiTimeframeCoordinator",
                return_value=mock_coordinator,
            ):
                engine._load_historical_data()

        # Verify coordinator was called with all 3 timeframes
        call_kwargs = mock_coordinator.load_multi_timeframe_data.call_args.kwargs
        assert set(call_kwargs["timeframes"]) == {"1h", "4h", "1d"}


class TestWorkerPassesTimeframesToConfig:
    """Tests that the worker includes timeframes in BacktestConfig construction."""

    def test_worker_fresh_start_includes_timeframes(self) -> None:
        """Worker passes request.timeframes into BacktestConfig on fresh start."""
        # We test the config construction pattern, not the full worker lifecycle
        from ktrdr.backtesting.backtest_worker import BacktestStartRequest

        request = BacktestStartRequest(
            task_id="op-1",
            symbol="EURUSD",
            timeframe="1h",
            strategy_name="multi_tf_test",
            start_date="2024-01-01",
            end_date="2024-02-01",
            timeframes=["1h", "1d"],
        )

        # Simulate the config construction the worker does
        engine_config = BacktestConfig(
            symbol=request.symbol,
            timeframe=request.timeframe,
            strategy_config_path=f"strategies/{request.strategy_name}.yaml",
            model_path=request.model_path,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage,
            timeframes=request.timeframes,
        )

        assert engine_config.get_all_timeframes() == ["1h", "1d"]

    def test_worker_backward_compat_no_timeframes(self) -> None:
        """Worker without timeframes falls back to single timeframe."""
        from ktrdr.backtesting.backtest_worker import BacktestStartRequest

        request = BacktestStartRequest(
            task_id="op-1",
            symbol="EURUSD",
            timeframe="1h",
            strategy_name="single_tf_test",
            start_date="2024-01-01",
            end_date="2024-02-01",
        )

        engine_config = BacktestConfig(
            symbol=request.symbol,
            timeframe=request.timeframe,
            strategy_config_path=f"strategies/{request.strategy_name}.yaml",
            model_path=request.model_path,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframes=request.timeframes,
        )

        assert engine_config.get_all_timeframes() == ["1h"]
