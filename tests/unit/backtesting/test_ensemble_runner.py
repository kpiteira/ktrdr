"""Tests for EnsembleBacktestRunner — multi-model regime-routed backtesting."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.backtesting.ensemble_runner import (
    EnsembleBacktestResults,
    EnsembleBacktestRunner,
)
from ktrdr.backtesting.position_manager import PositionStatus
from ktrdr.backtesting.regime_router import RouteDecision, TransitionAction
from ktrdr.config.ensemble_config import (
    CompositionConfig,
    EnsembleConfiguration,
    ModelReference,
    RouteRule,
)
from ktrdr.decision.base import Position, Signal, TradingDecision


def _make_ensemble_config() -> EnsembleConfiguration:
    """Create a minimal ensemble config for testing."""
    return EnsembleConfiguration(
        name="test_ensemble",
        description="Test ensemble",
        models={
            "regime": ModelReference(
                name="regime",
                model_path="models/regime_v1",
                output_type="regime_classification",
            ),
            "trend_long": ModelReference(
                name="trend_long",
                model_path="models/trend_long_v1",
                output_type="classification",
            ),
            "mean_reversion": ModelReference(
                name="mean_reversion",
                model_path="models/mean_rev_v1",
                output_type="classification",
            ),
        },
        composition=CompositionConfig(
            type="regime_route",
            gate_model="regime",
            regime_threshold=0.4,
            stability_bars=3,
            rules={
                "trending_up": RouteRule(model="trend_long"),
                "trending_down": RouteRule(model="trend_long"),
                "ranging": RouteRule(model="mean_reversion"),
                "volatile": RouteRule(action="FLAT"),
            },
            on_regime_transition="close_and_switch",
        ),
    )


def _make_backtest_config() -> BacktestConfig:
    return BacktestConfig(
        strategy_config_path="",
        model_path=None,
        symbol="EURUSD",
        timeframe="1h",
        start_date="2024-01-01",
        end_date="2024-02-01",
        initial_capital=100000.0,
    )


def _make_ohlcv_data(n_bars: int = 200) -> pd.DataFrame:
    """Create synthetic OHLCV data for testing."""
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "open": [1.1000 + i * 0.0001 for i in range(n_bars)],
            "high": [1.1010 + i * 0.0001 for i in range(n_bars)],
            "low": [1.0990 + i * 0.0001 for i in range(n_bars)],
            "close": [1.1005 + i * 0.0001 for i in range(n_bars)],
            "volume": [1000] * n_bars,
        },
        index=dates,
    )


def _make_mock_bundle(
    output_type: str = "classification",
    feature_names: list[str] | None = None,
) -> MagicMock:
    """Create a mock ModelBundle."""
    bundle = MagicMock()
    bundle.metadata.output_type = output_type
    bundle.metadata.resolved_features = feature_names or ["f1", "f2"]
    bundle.metadata.context_data_config = None
    bundle.feature_names = feature_names or ["f1", "f2"]
    bundle.model = MagicMock()
    # strategy_config needed for FeatureCache
    bundle.strategy_config = MagicMock()
    return bundle


def _make_regime_decision(
    regime: str = "trending_up", confidence: float = 0.8
) -> TradingDecision:
    """Create a mock regime classification decision."""
    probs = {
        "TRENDING_UP": 0.05,
        "TRENDING_DOWN": 0.05,
        "RANGING": 0.05,
        "VOLATILE": 0.05,
    }
    probs[regime.upper()] = confidence
    return TradingDecision(
        signal=Signal.HOLD,
        confidence=confidence,
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        reasoning={"nn_probabilities": probs},
        current_position=Position.FLAT,
    )


def _make_signal_decision(
    signal: Signal = Signal.BUY, confidence: float = 0.7
) -> TradingDecision:
    """Create a mock signal model decision."""
    return TradingDecision(
        signal=signal,
        confidence=confidence,
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        reasoning={"nn_probabilities": {"BUY": 0.7, "HOLD": 0.2, "SELL": 0.1}},
        current_position=Position.FLAT,
    )


class TestEnsembleBacktestRunnerInit:
    """Tests for EnsembleBacktestRunner initialization."""

    def test_creates_with_valid_config(self) -> None:
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        assert runner.ensemble_config.name == "test_ensemble"

    def test_stores_backtest_config(self) -> None:
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        assert runner.backtest_config.symbol == "EURUSD"


class TestLoadModels:
    """Tests for model loading."""

    @patch("ktrdr.backtesting.ensemble_runner.ModelBundle")
    def test_loads_all_model_bundles(self, mock_bundle_cls: MagicMock) -> None:
        mock_bundle_cls.load.return_value = _make_mock_bundle()
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        bundles = runner._load_models()
        assert len(bundles) == 3
        assert "regime" in bundles
        assert "trend_long" in bundles
        assert "mean_reversion" in bundles


class TestCreateFeatureCaches:
    """Tests for per-model feature cache creation."""

    def test_creates_separate_cache_per_model(self) -> None:
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        bundles = {
            "regime": _make_mock_bundle("regime_classification"),
            "trend_long": _make_mock_bundle(),
            "mean_reversion": _make_mock_bundle(),
        }
        with patch("ktrdr.backtesting.ensemble_runner.FeatureCache") as MockCache:
            caches = runner._create_feature_caches(bundles)
        assert len(caches) == 3
        assert MockCache.call_count == 3


class TestCreateDecisionFunctions:
    """Tests for per-model decision function creation."""

    def test_creates_decision_function_per_model(self) -> None:
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        bundles = {
            "regime": _make_mock_bundle("regime_classification"),
            "trend_long": _make_mock_bundle(),
        }
        with patch("ktrdr.backtesting.ensemble_runner.DecisionFunction") as MockDF:
            fns = runner._create_decision_functions(bundles)
        assert len(fns) == 2
        # Regime model should pass output_type="regime_classification"
        calls = MockDF.call_args_list
        regime_call = [
            c for c in calls if c.kwargs.get("output_type") == "regime_classification"
        ]
        assert len(regime_call) == 1


class TestInterpretRegimeOutput:
    """Tests for extracting regime probabilities from decision output."""

    def test_extracts_regime_probabilities(self) -> None:
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        decision = _make_regime_decision("trending_up", 0.65)
        probs = runner._interpret_regime_output(decision)
        assert probs["trending_up"] == pytest.approx(0.65)
        assert "trending_down" in probs
        assert "ranging" in probs
        assert "volatile" in probs


class TestBarExecution:
    """Tests for per-bar execution logic."""

    def test_regime_model_runs_every_bar(self) -> None:
        """Verify the regime model is invoked for every bar."""
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        # Mock components
        regime_fn = MagicMock(return_value=_make_regime_decision())
        signal_fn = MagicMock(return_value=_make_signal_decision())
        decision_fns = {
            "regime": regime_fn,
            "trend_long": signal_fn,
            "mean_reversion": signal_fn,
        }

        regime_cache = MagicMock()
        regime_cache.get_features_for_timestamp.return_value = {"f1": 0.5, "f2": 0.3}
        signal_cache = MagicMock()
        signal_cache.get_features_for_timestamp.return_value = {"f1": 0.5, "f2": 0.3}
        caches = {
            "regime": regime_cache,
            "trend_long": signal_cache,
            "mean_reversion": signal_cache,
        }

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
        )

        pm = MagicMock()
        pm.current_position_status = PositionStatus.FLAT

        bar = pd.Series(
            {"open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "volume": 1000},
            name=pd.Timestamp("2024-01-15 10:00", tz="UTC"),
        )

        runner._run_bar(
            timestamp=bar.name,
            bar=bar,
            feature_caches=caches,
            decision_functions=decision_fns,
            router=router,
            position_manager=pm,
        )

        regime_fn.assert_called_once()
        signal_fn.assert_called_once()

    def test_flat_route_produces_hold(self) -> None:
        """When router returns active_model=None (FLAT), signal model should NOT run."""
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        regime_fn = MagicMock(return_value=_make_regime_decision("volatile", 0.8))
        signal_fn = MagicMock(return_value=_make_signal_decision())
        decision_fns = {
            "regime": regime_fn,
            "trend_long": signal_fn,
            "mean_reversion": signal_fn,
        }

        regime_cache = MagicMock()
        regime_cache.get_features_for_timestamp.return_value = {"f1": 0.5}
        caches = {
            "regime": regime_cache,
            "trend_long": MagicMock(),
            "mean_reversion": MagicMock(),
        }

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="volatile",
            regime_confidence=0.8,
            active_model=None,  # FLAT route
            transition=None,
            reasoning="volatile → FLAT",
        )

        pm = MagicMock()
        pm.current_position_status = PositionStatus.FLAT

        bar = pd.Series(
            {"open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "volume": 1000},
            name=pd.Timestamp("2024-01-15 10:00", tz="UTC"),
        )

        result = runner._run_bar(
            timestamp=bar.name,
            bar=bar,
            feature_caches=caches,
            decision_functions=decision_fns,
            router=router,
            position_manager=pm,
        )

        # Signal model should NOT have been called
        signal_fn.assert_not_called()
        assert result["signal"] == Signal.HOLD

    def test_transition_closes_position(self) -> None:
        """When router returns transition with close_position=True, position is closed."""
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        regime_fn = MagicMock(return_value=_make_regime_decision("ranging", 0.7))
        signal_fn = MagicMock(return_value=_make_signal_decision(Signal.HOLD))
        decision_fns = {
            "regime": regime_fn,
            "trend_long": signal_fn,
            "mean_reversion": signal_fn,
        }

        regime_cache = MagicMock()
        regime_cache.get_features_for_timestamp.return_value = {"f1": 0.5}
        signal_cache = MagicMock()
        signal_cache.get_features_for_timestamp.return_value = {"f1": 0.5}
        caches = {
            "regime": regime_cache,
            "trend_long": signal_cache,
            "mean_reversion": signal_cache,
        }

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="ranging",
            regime_confidence=0.7,
            active_model="mean_reversion",
            transition=TransitionAction(
                close_position=True,
                from_regime="trending_up",
                to_regime="ranging",
            ),
            reasoning="transition",
        )

        pm = MagicMock()
        pm.current_position_status = PositionStatus.LONG

        bar = pd.Series(
            {"open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "volume": 1000},
            name=pd.Timestamp("2024-01-15 10:00", tz="UTC"),
        )

        runner._run_bar(
            timestamp=bar.name,
            bar=bar,
            feature_caches=caches,
            decision_functions=decision_fns,
            router=router,
            position_manager=pm,
        )

        # Position manager should have been called to close the position
        pm.execute_trade.assert_called()
        close_call = pm.execute_trade.call_args_list[0]
        assert close_call.kwargs["signal"] == Signal.SELL  # Close LONG = SELL


class TestEnsembleBacktestResults:
    """Tests for EnsembleBacktestResults dataclass."""

    def test_results_include_per_regime_metrics(self) -> None:
        results = EnsembleBacktestResults(
            ensemble_name="test",
            symbol="EURUSD",
            timeframe="1h",
            total_bars=1000,
            trades=[],
            per_regime_metrics={
                "trending_up": {"trades": 5, "pnl": 100.0},
                "ranging": {"trades": 10, "pnl": -50.0},
            },
            transition_count=3,
            transition_cost=0.0,
            regime_sequence=[],
            execution_time_seconds=1.0,
        )
        assert "trending_up" in results.per_regime_metrics
        assert results.transition_count == 3

    def test_results_to_dict(self) -> None:
        results = EnsembleBacktestResults(
            ensemble_name="test",
            symbol="EURUSD",
            timeframe="1h",
            total_bars=100,
            trades=[],
            per_regime_metrics={},
            transition_count=0,
            transition_cost=0.0,
            regime_sequence=[],
            execution_time_seconds=0.5,
        )
        d = results.to_dict()
        assert d["ensemble_name"] == "test"
        assert "per_regime_metrics" in d
        assert "transition_count" in d
