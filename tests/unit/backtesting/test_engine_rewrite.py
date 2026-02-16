"""Unit tests for BacktestingEngine rewrite (M3: Engine Rewrite).

Tests the new engine initialization (ModelBundle + FeatureCache + DecisionFunction),
the clean simulation loop, and infrastructure helpers.

Task 3.1: __init__ uses ModelBundle, FeatureCache, DecisionFunction directly
Task 3.2: run() is a clean pipeline with extracted helpers
Task 3.3: resume_from_context uses feature_cache, reset() has no orchestrator
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ktrdr.backtesting.engine import BacktestConfig

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

    # strategy_config is a StrategyConfigurationV3 Pydantic model
    strategy_config = MagicMock()
    strategy_config.name = "test_strategy"

    # training_data config for timeframe resolution
    td = MagicMock()
    td.timeframes = MagicMock()
    td.timeframes.base_timeframe = "1h"
    td.timeframes.mode = "single"
    td.timeframes.timeframes = None
    strategy_config.training_data = td

    # decisions config
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
        "verbose": False,
    }
    defaults.update(overrides)
    return BacktestConfig(**defaults)


# ---------------------------------------------------------------------------
# Task 3.1: __init__ tests
# ---------------------------------------------------------------------------


class TestEngineInitUsesModelBundle:
    """Verify __init__ creates components from ModelBundle, not DecisionOrchestrator."""

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_init_loads_model_bundle(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """ModelBundle.load() called with model_path during init."""
        mock_mb_cls.load.return_value = _make_mock_bundle()
        from ktrdr.backtesting.engine import BacktestingEngine

        config = _make_config()
        _engine = BacktestingEngine(config)  # noqa: F841

        mock_mb_cls.load.assert_called_once_with(config.model_path)

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_init_creates_feature_cache(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """FeatureCache created with bundle's strategy_config and metadata."""
        bundle = _make_mock_bundle()
        mock_mb_cls.load.return_value = bundle
        from ktrdr.backtesting.engine import BacktestingEngine

        _engine = BacktestingEngine(_make_config())  # noqa: F841

        mock_fc_cls.assert_called_once_with(
            config=bundle.strategy_config,
            model_metadata=bundle.metadata,
        )

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_init_creates_decision_function(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """DecisionFunction created with model, feature_names, and decisions config."""
        bundle = _make_mock_bundle()
        mock_mb_cls.load.return_value = bundle
        from ktrdr.backtesting.engine import BacktestingEngine

        _engine = BacktestingEngine(_make_config())  # noqa: F841

        mock_df_cls.assert_called_once()
        call_kwargs = mock_df_cls.call_args
        assert (
            call_kwargs[1]["model"] is bundle.model or call_kwargs[0][0] is bundle.model
        )

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_engine_has_bundle_attribute(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """engine.bundle is the loaded ModelBundle."""
        bundle = _make_mock_bundle()
        mock_mb_cls.load.return_value = bundle
        from ktrdr.backtesting.engine import BacktestingEngine

        engine = BacktestingEngine(_make_config())
        assert engine.bundle is bundle

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_engine_has_decide_attribute(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """engine.decide is a DecisionFunction instance."""
        mock_mb_cls.load.return_value = _make_mock_bundle()
        from ktrdr.backtesting.engine import BacktestingEngine

        engine = BacktestingEngine(_make_config())
        assert engine.decide is mock_df_cls.return_value

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_engine_has_feature_cache_attribute(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """engine.feature_cache is a FeatureCache instance."""
        mock_mb_cls.load.return_value = _make_mock_bundle()
        from ktrdr.backtesting.engine import BacktestingEngine

        engine = BacktestingEngine(_make_config())
        assert engine.feature_cache is mock_fc_cls.return_value

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_strategy_name_from_bundle(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """strategy_name comes from bundle metadata, not orchestrator."""
        bundle = _make_mock_bundle()
        bundle.metadata.strategy_name = "my_strategy_v3"
        mock_mb_cls.load.return_value = bundle
        from ktrdr.backtesting.engine import BacktestingEngine

        engine = BacktestingEngine(_make_config())
        assert engine.strategy_name == "my_strategy_v3"


class TestEngineNoOrchestratorImport:
    """Verify no DecisionOrchestrator import in engine.py."""

    def test_no_orchestrator_import(self):
        """engine.py should not import DecisionOrchestrator."""
        import inspect

        from ktrdr.backtesting import engine as engine_module

        source = inspect.getsource(engine_module)
        assert "from ..decision.orchestrator import" not in source
        assert "import DecisionOrchestrator" not in source

    def test_no_orchestrator_attribute(self):
        """BacktestingEngine should not have self.orchestrator attribute usage."""
        import inspect

        from ktrdr.backtesting import engine as engine_module

        source = inspect.getsource(engine_module.BacktestingEngine)
        assert "self.orchestrator" not in source


class TestGetBaseTimeframe:
    """_get_base_timeframe reads from bundle.strategy_config."""

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_returns_base_timeframe_from_config(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """Should return base_timeframe from strategy_config.training_data."""
        bundle = _make_mock_bundle()
        bundle.strategy_config.training_data.timeframes.base_timeframe = "4h"
        mock_mb_cls.load.return_value = bundle
        from ktrdr.backtesting.engine import BacktestingEngine

        engine = BacktestingEngine(_make_config(timeframe="1h"))
        assert engine._get_base_timeframe() == "4h"

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_fallback_to_config_timeframe(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """Should fall back to config.timeframe if no base_timeframe in strategy."""
        bundle = _make_mock_bundle()
        bundle.strategy_config.training_data.timeframes.base_timeframe = None
        mock_mb_cls.load.return_value = bundle
        from ktrdr.backtesting.engine import BacktestingEngine

        engine = BacktestingEngine(_make_config(timeframe="5m"))
        assert engine._get_base_timeframe() == "5m"


# ---------------------------------------------------------------------------
# Task 3.2: Simulation loop tests
# ---------------------------------------------------------------------------


class TestSimulationLoop:
    """Test the clean simulation loop."""

    @pytest.fixture
    def mock_engine(self):
        """Create a BacktestingEngine with mocked components for loop testing."""
        with patch(
            "ktrdr.backtesting.engine.BacktestingEngine.__init__",
            lambda self, config: None,
        ):
            from ktrdr.backtesting.engine import BacktestingEngine

            engine = BacktestingEngine.__new__(BacktestingEngine)

            config = _make_config()
            engine.config = config
            engine.strategy_name = "test_strategy"

            # Mock bundle
            engine.bundle = _make_mock_bundle()

            # Mock feature cache
            engine.feature_cache = MagicMock()
            # Return features for all timestamps
            engine.feature_cache.get_features_for_timestamp = MagicMock(
                return_value={"feat_a": 0.5, "feat_b": 0.3}
            )

            # Mock decision function — always HOLD
            from ktrdr.decision.base import Position, Signal, TradingDecision

            engine.decide = MagicMock(
                return_value=TradingDecision(
                    signal=Signal.HOLD,
                    confidence=0.4,
                    timestamp=pd.Timestamp("2024-01-01"),
                    reasoning={},
                    current_position=Position.FLAT,
                )
            )

            # Real-ish position manager mock
            engine.position_manager = MagicMock()
            engine.position_manager.current_position_status = MagicMock()
            engine.position_manager.get_portfolio_value.return_value = 100000.0
            engine.position_manager.get_trade_history.return_value = []
            engine.position_manager.force_close_position.return_value = None

            # Performance tracker
            engine.performance_tracker = MagicMock()
            engine.performance_tracker.equity_curve = []
            engine.performance_tracker.get_equity_curve.return_value = pd.DataFrame()
            engine.performance_tracker.calculate_metrics.return_value = MagicMock()

            # Data
            engine.repository = MagicMock()

            # Mock data loading
            dates = pd.date_range("2024-01-01", periods=100, freq="h")
            mock_data = pd.DataFrame(
                {
                    "open": [1.1] * 100,
                    "high": [1.12] * 100,
                    "low": [1.08] * 100,
                    "close": [1.1] * 100,
                    "volume": [1000] * 100,
                },
                index=dates,
            )
            engine._load_historical_data = MagicMock(return_value={"1h": mock_data})
            engine._get_base_timeframe = MagicMock(return_value="1h")

            return engine

    def test_run_calls_feature_cache_compute(self, mock_engine):
        """run() should call feature_cache.compute_all_features with multi_tf_data."""
        mock_engine.run()
        mock_engine.feature_cache.compute_all_features.assert_called_once()

    def test_run_calls_decide_for_each_bar(self, mock_engine):
        """run() should call decide() for each bar after warmup."""
        mock_engine.run()
        # 100 bars - 50 warmup = 50 calls (minus any None features)
        assert mock_engine.decide.call_count == 50

    def test_run_returns_backtest_results(self, mock_engine):
        """run() should return BacktestResults."""
        from ktrdr.backtesting.engine import BacktestResults

        result = mock_engine.run()
        assert isinstance(result, BacktestResults)

    def test_run_tracks_performance(self, mock_engine):
        """run() should call performance_tracker.update() for each processed bar."""
        mock_engine.run()
        assert mock_engine.performance_tracker.update.call_count == 50

    def test_run_force_closes_position(self, mock_engine):
        """run() should force-close open position at the end."""
        mock_engine.run()
        mock_engine.position_manager.force_close_position.assert_called_once()

    def test_last_signal_time_is_local(self):
        """last_signal_time should be a local variable in run(), not on self."""
        import inspect

        from ktrdr.backtesting import engine as engine_module

        source = inspect.getsource(engine_module.BacktestingEngine.run)
        # It should use "last_signal_time" as a local, not "self.last_signal_time"
        assert "self.last_signal_time" not in source

    def test_no_debug_tracking_variables(self):
        """run() should not have signal_counts, non_hold_signals, trade_attempts."""
        import inspect

        from ktrdr.backtesting import engine as engine_module

        source = inspect.getsource(engine_module.BacktestingEngine.run)
        assert "signal_counts" not in source
        assert "non_hold_signals" not in source
        assert "trade_attempts" not in source

    def test_no_verbose_print_blocks(self):
        """run() should not have self.config.verbose print blocks."""
        import inspect

        from ktrdr.backtesting import engine as engine_module

        source = inspect.getsource(engine_module.BacktestingEngine.run)
        assert "self.config.verbose" not in source


class TestSimulationLoopEdgeCases:
    """Edge case tests for the simulation loop."""

    def test_insufficient_data_raises_value_error(self):
        """run() should raise ValueError if data has fewer bars than warmup period."""
        with patch(
            "ktrdr.backtesting.engine.BacktestingEngine.__init__",
            lambda self, config: None,
        ):
            from ktrdr.backtesting.engine import BacktestingEngine

            engine = BacktestingEngine.__new__(BacktestingEngine)
            engine.config = _make_config()
            engine.strategy_name = "test_strategy"
            engine.bundle = _make_mock_bundle()
            engine.feature_cache = MagicMock()
            engine.position_manager = MagicMock()
            engine.performance_tracker = MagicMock()
            engine.repository = MagicMock()

            # Only 30 bars — less than 50 warmup
            dates = pd.date_range("2024-01-01", periods=30, freq="h")
            mock_data = pd.DataFrame(
                {
                    "open": [1.1] * 30,
                    "high": [1.12] * 30,
                    "low": [1.08] * 30,
                    "close": [1.1] * 30,
                    "volume": [1000] * 30,
                },
                index=dates,
            )
            engine._load_historical_data = MagicMock(return_value={"1h": mock_data})
            engine._get_base_timeframe = MagicMock(return_value="1h")

            with pytest.raises(ValueError, match="Insufficient data"):
                engine.run()


class TestSimulationLoopTradeExecution:
    """Test that run() executes trades correctly."""

    @pytest.fixture
    def trading_engine(self):
        """Create engine where DecisionFunction returns BUY then SELL."""
        with patch(
            "ktrdr.backtesting.engine.BacktestingEngine.__init__",
            lambda self, config: None,
        ):
            from ktrdr.backtesting.engine import BacktestingEngine
            from ktrdr.decision.base import Position, Signal, TradingDecision

            engine = BacktestingEngine.__new__(BacktestingEngine)

            config = _make_config()
            engine.config = config
            engine.strategy_name = "test_strategy"
            engine.bundle = _make_mock_bundle()

            engine.feature_cache = MagicMock()
            engine.feature_cache.get_features_for_timestamp = MagicMock(
                return_value={"feat_a": 0.5, "feat_b": 0.3}
            )

            # BUY on first call, HOLD on rest
            call_count = 0

            def make_decision(**kwargs):
                nonlocal call_count
                call_count += 1
                sig = Signal.BUY if call_count == 1 else Signal.HOLD
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

            # Position manager that tracks trades
            engine.position_manager = MagicMock()
            engine.position_manager.current_position_status = MagicMock()
            engine.position_manager.get_portfolio_value.return_value = 100000.0
            engine.position_manager.execute_trade.return_value = (
                MagicMock()
            )  # Trade executed
            engine.position_manager.get_trade_history.return_value = []
            engine.position_manager.force_close_position.return_value = None

            engine.performance_tracker = MagicMock()
            engine.performance_tracker.equity_curve = []
            engine.performance_tracker.get_equity_curve.return_value = pd.DataFrame()
            engine.performance_tracker.calculate_metrics.return_value = MagicMock()

            engine.repository = MagicMock()

            dates = pd.date_range("2024-01-01", periods=100, freq="h")
            mock_data = pd.DataFrame(
                {
                    "open": [1.1] * 100,
                    "high": [1.12] * 100,
                    "low": [1.08] * 100,
                    "close": [1.1] * 100,
                    "volume": [1000] * 100,
                },
                index=dates,
            )
            engine._load_historical_data = MagicMock(return_value={"1h": mock_data})
            engine._get_base_timeframe = MagicMock(return_value="1h")

            return engine

    def test_executes_trade_on_non_hold(self, trading_engine):
        """execute_trade called when signal is not HOLD."""
        trading_engine.run()
        trading_engine.position_manager.execute_trade.assert_called_once()


# ---------------------------------------------------------------------------
# Task 3.2: Infrastructure helpers tests
# ---------------------------------------------------------------------------


class TestInfrastructureHelpers:
    """Test extracted helper methods."""

    def test_report_progress_exists(self):
        """_report_progress helper method should exist."""
        from ktrdr.backtesting.engine import BacktestingEngine

        assert hasattr(BacktestingEngine, "_report_progress")

    def test_maybe_checkpoint_exists(self):
        """_maybe_checkpoint helper method should exist."""
        from ktrdr.backtesting.engine import BacktestingEngine

        assert hasattr(BacktestingEngine, "_maybe_checkpoint")

    def test_check_cancellation_exists(self):
        """_check_cancellation helper method should exist."""
        from ktrdr.backtesting.engine import BacktestingEngine

        assert hasattr(BacktestingEngine, "_check_cancellation")

    def test_force_close_position_exists(self):
        """_force_close_position helper method should exist."""
        from ktrdr.backtesting.engine import BacktestingEngine

        assert hasattr(BacktestingEngine, "_force_close_position")


# ---------------------------------------------------------------------------
# Task 3.3: resume_from_context + reset tests
# ---------------------------------------------------------------------------


class TestResumeUsesFeatureCache:
    """resume_from_context should use self.feature_cache, not orchestrator."""

    @pytest.fixture
    def mock_engine(self):
        """Create engine with feature_cache for resume testing."""
        with patch(
            "ktrdr.backtesting.engine.BacktestingEngine.__init__",
            lambda self, config: None,
        ):
            from ktrdr.backtesting.engine import BacktestingEngine

            engine = BacktestingEngine.__new__(BacktestingEngine)

            engine.config = MagicMock()
            engine.config.timeframe = "1h"
            engine.repository = MagicMock()
            engine.feature_cache = MagicMock()  # NEW: uses feature_cache
            engine.bundle = _make_mock_bundle()

            engine.position_manager = MagicMock()
            engine.position_manager.current_capital = 100000.0
            engine.position_manager.current_position = None
            engine.position_manager.trade_history = []
            engine.position_manager.next_trade_id = 1
            engine.performance_tracker = MagicMock()
            engine.performance_tracker.equity_curve = []

            mock_data = pd.DataFrame(
                {
                    "open": [1.0] * 100,
                    "high": [1.1] * 100,
                    "low": [0.9] * 100,
                    "close": [1.05] * 100,
                    "volume": [1000] * 100,
                },
                index=pd.date_range("2023-01-01", periods=100, freq="h"),
            )
            engine._load_historical_data = MagicMock(return_value={"1h": mock_data})
            engine._get_base_timeframe = MagicMock(return_value="1h")

            return engine

    def test_resume_calls_feature_cache(self, mock_engine):
        """resume_from_context calls feature_cache.compute_all_features."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=500,
            cash=100000.0,
            original_request={"symbol": "EURUSD"},
        )
        mock_engine.resume_from_context(context)
        mock_engine.feature_cache.compute_all_features.assert_called_once()


class TestResetNoOrchestrator:
    """reset() should not reference self.orchestrator."""

    def test_reset_source_no_orchestrator(self):
        """reset() method should not reference self.orchestrator."""
        import inspect

        from ktrdr.backtesting.engine import BacktestingEngine

        source = inspect.getsource(BacktestingEngine.reset)
        assert "self.orchestrator" not in source

    @patch("ktrdr.backtesting.engine.ModelBundle")
    @patch("ktrdr.backtesting.engine.FeatureCache")
    @patch("ktrdr.backtesting.engine.DecisionFunction")
    @patch("ktrdr.backtesting.engine.DataRepository")
    def test_reset_resets_position_and_perf(
        self, mock_repo_cls, mock_df_cls, mock_fc_cls, mock_mb_cls
    ):
        """reset() should reset position_manager and performance_tracker."""
        mock_mb_cls.load.return_value = _make_mock_bundle()
        from ktrdr.backtesting.engine import BacktestingEngine

        engine = BacktestingEngine(_make_config())

        # Replace with mocks to track reset calls
        engine.position_manager = MagicMock()
        engine.performance_tracker = MagicMock()
        engine.reset()

        engine.position_manager.reset.assert_called_once()
        engine.performance_tracker.reset.assert_called_once()
