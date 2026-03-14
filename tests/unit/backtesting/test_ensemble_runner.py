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
from ktrdr.backtesting.regime_router import (
    RouteDecision,
    ThresholdModifier,
    TransitionAction,
)
from ktrdr.config.ensemble_config import (
    CompositionConfig,
    ContextModifiers,
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


CONTEXT_CLASS_NAMES = ["BULLISH", "BEARISH", "NEUTRAL"]


def _make_context_ensemble_config() -> EnsembleConfiguration:
    """Create ensemble config with context gate for testing."""
    return EnsembleConfiguration(
        name="test_context_ensemble",
        description="Test ensemble with context gate",
        models={
            "regime": ModelReference(
                name="regime",
                model_path="models/regime_v1",
                output_type="regime_classification",
            ),
            "context": ModelReference(
                name="context",
                model_path="models/context_v1",
                output_type="context_classification",
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
            context_gate="context",
            context_modifiers=ContextModifiers(
                aligned_discount=0.2,
                counter_premium=0.3,
                neutral_effect=0.05,
            ),
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


def _make_context_decision(
    bullish: float = 0.6, bearish: float = 0.1, neutral: float = 0.3
) -> TradingDecision:
    """Create a mock context classification decision."""
    probs = {"BULLISH": bullish, "BEARISH": bearish, "NEUTRAL": neutral}
    return TradingDecision(
        signal=Signal.HOLD,
        confidence=max(probs.values()),
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        reasoning={"nn_probabilities": probs},
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


class TestInterpretContextOutput:
    """Tests for context probability extraction from DecisionFunction output."""

    def test_extracts_context_probabilities(self) -> None:
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_context_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )
        decision = _make_context_decision(bullish=0.65, bearish=0.15, neutral=0.20)
        probs = runner._interpret_context_output(decision)
        assert probs["bullish"] == pytest.approx(0.65)
        assert probs["bearish"] == pytest.approx(0.15)
        assert probs["neutral"] == pytest.approx(0.20)


class TestContextEvaluation:
    """Tests for context model evaluation timing and threshold application."""

    def _setup_context_bar_test(
        self,
        context_probs: dict[str, float] | None = None,
        signal_decision: TradingDecision | None = None,
    ) -> tuple:
        """Set up common test infrastructure for context bar tests."""
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_context_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )

        regime_fn = MagicMock(return_value=_make_regime_decision("trending_up", 0.8))
        context_fn = MagicMock(
            return_value=_make_context_decision(bullish=0.7, bearish=0.1, neutral=0.2)
        )
        sig = signal_decision or _make_signal_decision(Signal.BUY, 0.7)
        signal_fn = MagicMock(return_value=sig)

        decision_fns = {
            "regime": regime_fn,
            "context": context_fn,
            "trend_long": signal_fn,
            "mean_reversion": signal_fn,
        }

        regime_cache = MagicMock()
        regime_cache.get_features_for_timestamp.return_value = {"f1": 0.5}
        context_cache = MagicMock()
        context_cache.get_features_for_timestamp.return_value = {"f1": 0.5}
        signal_cache = MagicMock()
        signal_cache.get_features_for_timestamp.return_value = {"f1": 0.5}

        caches = {
            "regime": regime_cache,
            "context": context_cache,
            "trend_long": signal_cache,
            "mean_reversion": signal_cache,
        }

        pm = MagicMock()
        pm.current_position_status = PositionStatus.FLAT

        return runner, decision_fns, caches, pm, context_fn, signal_fn

    def test_context_evaluated_once_per_day(self) -> None:
        """Context model should be evaluated once per daily bar change."""
        runner, decision_fns, caches, pm, context_fn, _ = self._setup_context_bar_test()

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
        )
        router._confirmed_regime = "trending_up"

        # Bar 1 at 10:00 Jan 15 — first call, should evaluate context
        bar1 = pd.Series(
            {"open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "volume": 1000},
            name=pd.Timestamp("2024-01-15 10:00", tz="UTC"),
        )
        runner._run_bar(
            timestamp=bar1.name,
            bar=bar1,
            feature_caches=caches,
            decision_functions=decision_fns,
            router=router,
            position_manager=pm,
        )
        assert context_fn.call_count == 1

        # Bar 2 at 11:00 Jan 15 — same day, should NOT re-evaluate
        bar2 = pd.Series(
            {"open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "volume": 1000},
            name=pd.Timestamp("2024-01-15 11:00", tz="UTC"),
        )
        runner._run_bar(
            timestamp=bar2.name,
            bar=bar2,
            feature_caches=caches,
            decision_functions=decision_fns,
            router=router,
            position_manager=pm,
        )
        assert context_fn.call_count == 1  # Still 1 — same day

        # Bar 3 at 10:00 Jan 16 — new day, should re-evaluate
        bar3 = pd.Series(
            {"open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "volume": 1000},
            name=pd.Timestamp("2024-01-16 10:00", tz="UTC"),
        )
        runner._run_bar(
            timestamp=bar3.name,
            bar=bar3,
            feature_caches=caches,
            decision_functions=decision_fns,
            router=router,
            position_manager=pm,
        )
        assert context_fn.call_count == 2  # Now 2 — new day

    def test_context_probs_passed_to_router(self) -> None:
        """Context probs should be passed to router on every bar."""
        runner, decision_fns, caches, pm, _, _ = self._setup_context_bar_test()

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
        )
        router._confirmed_regime = "trending_up"

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

        # Router should have received context_probs
        router.route.assert_called_once()
        call_kwargs = router.route.call_args.kwargs
        assert "context_probs" in call_kwargs
        assert call_kwargs["context_probs"]["bullish"] == pytest.approx(0.7)

    def test_threshold_modifier_converts_to_hold(self) -> None:
        """Signal below context-adjusted threshold should become HOLD."""
        # Signal with low confidence that should be blocked by adjusted threshold
        low_conf_signal = _make_signal_decision(Signal.BUY, confidence=0.55)
        runner, decision_fns, caches, pm, _, signal_fn = self._setup_context_bar_test(
            signal_decision=low_conf_signal
        )
        # Set confidence_threshold on signal model mock so getattr works
        signal_fn.confidence_threshold = 0.5

        # Router returns a threshold modifier that raises long threshold
        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
            # Bearish context: raises long threshold
            threshold_modifier=ThresholdModifier(long_factor=1.3, short_factor=0.8),
        )
        router._confirmed_regime = "trending_up"

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

        # confidence 0.55 * base_threshold 0.5 → adjusted 0.65 → 0.55 < 0.65 → HOLD
        assert result["signal"] == Signal.HOLD

    def test_without_context_gate_behavior_unchanged(self) -> None:
        """Regime-only ensemble should produce identical behavior (backward compat)."""
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_ensemble_config(),  # No context gate
            backtest_config=_make_backtest_config(),
        )

        regime_fn = MagicMock(return_value=_make_regime_decision("trending_up", 0.8))
        signal_fn = MagicMock(return_value=_make_signal_decision(Signal.BUY, 0.7))
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
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
        )
        router._confirmed_regime = "trending_up"

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

        # No context model should be evaluated
        assert result["signal"] == Signal.BUY
        # Router should NOT have received context_probs
        call_kwargs = router.route.call_args.kwargs
        assert call_kwargs.get("context_probs") is None


def _make_regression_signal_decision(
    predicted_return: float,
    trade_threshold: float = 0.0004,
) -> TradingDecision:
    """Create a regression-style signal decision with predicted_return in reasoning."""
    if predicted_return > trade_threshold:
        signal = Signal.BUY
    elif predicted_return < -trade_threshold:
        signal = Signal.SELL
    else:
        signal = Signal.HOLD

    confidence = min(abs(predicted_return) / (3 * trade_threshold), 1.0)
    return TradingDecision(
        signal=signal,
        confidence=confidence,
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        reasoning={"predicted_return": predicted_return},
        current_position=Position.FLAT,
    )


class TestRegressionThresholdModifier:
    """Tests for context-gate threshold modifier with regression signal models.

    For regression models, the context gate should adjust trade_threshold
    (not confidence_threshold) to make it easier/harder to enter positions
    based on daily context.
    """

    def _setup_regression_bar_test(
        self,
        predicted_return: float = 0.0005,
        trade_threshold: float = 0.0004,
    ) -> tuple:
        """Set up common infrastructure for regression threshold modifier tests."""
        runner = EnsembleBacktestRunner(
            ensemble_config=_make_context_ensemble_config(),
            backtest_config=_make_backtest_config(),
        )

        regime_fn = MagicMock(return_value=_make_regime_decision("trending_up", 0.8))
        context_fn = MagicMock(
            return_value=_make_context_decision(bullish=0.7, bearish=0.1, neutral=0.2)
        )
        sig = _make_regression_signal_decision(predicted_return, trade_threshold)
        signal_fn = MagicMock(return_value=sig)
        # Mark signal function as regression with trade_threshold
        signal_fn.output_format = "regression"
        signal_fn.trade_threshold = trade_threshold

        decision_fns = {
            "regime": regime_fn,
            "context": context_fn,
            "trend_long": signal_fn,
            "mean_reversion": signal_fn,
        }

        regime_cache = MagicMock()
        regime_cache.get_features_for_timestamp.return_value = {"f1": 0.5}
        context_cache = MagicMock()
        context_cache.get_features_for_timestamp.return_value = {"f1": 0.5}
        signal_cache = MagicMock()
        signal_cache.get_features_for_timestamp.return_value = {"f1": 0.5}

        caches = {
            "regime": regime_cache,
            "context": context_cache,
            "trend_long": signal_cache,
            "mean_reversion": signal_cache,
        }

        pm = MagicMock()
        pm.current_position_status = PositionStatus.FLAT

        return runner, decision_fns, caches, pm

    def test_regression_buy_blocked_by_counter_trend_modifier(self) -> None:
        """Bearish context should raise BUY trade_threshold, blocking marginal BUY."""
        # predicted_return = 0.0005, trade_threshold = 0.0004
        # BUY signal because 0.0005 > 0.0004
        # With bearish context: long_factor=1.5 raises threshold to 0.0006
        # 0.0005 < 0.0006 → should become HOLD
        runner, decision_fns, caches, pm = self._setup_regression_bar_test(
            predicted_return=0.0005, trade_threshold=0.0004
        )

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
            # Bearish context: raises long threshold, lowers short threshold
            threshold_modifier=ThresholdModifier(long_factor=1.5, short_factor=0.7),
        )
        router._confirmed_regime = "trending_up"

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

        # BUY should be blocked: predicted_return 0.0005 < adjusted threshold 0.0006
        assert result["signal"] == Signal.HOLD

    def test_regression_sell_blocked_by_bullish_modifier(self) -> None:
        """Bullish context should raise SELL trade_threshold, blocking marginal SELL."""
        # predicted_return = -0.0005 → SELL (below -0.0004)
        # Bullish context: short_factor=1.5 raises threshold to 0.0006
        # |-0.0005| < 0.0006 → should become HOLD
        runner, decision_fns, caches, pm = self._setup_regression_bar_test(
            predicted_return=-0.0005, trade_threshold=0.0004
        )

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
            # Bullish context: lowers long threshold, raises short threshold
            threshold_modifier=ThresholdModifier(long_factor=0.7, short_factor=1.5),
        )
        router._confirmed_regime = "trending_up"

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

        # SELL should be blocked: |predicted_return| 0.0005 < adjusted threshold 0.0006
        assert result["signal"] == Signal.HOLD

    def test_regression_buy_passes_with_aligned_modifier(self) -> None:
        """Bullish context should lower BUY trade_threshold, allowing marginal BUY."""
        # predicted_return = 0.00035 → HOLD (below 0.0004 threshold)
        # Bullish context: long_factor=0.7 lowers threshold to 0.00028
        # 0.00035 > 0.00028 → should become BUY
        runner, decision_fns, caches, pm = self._setup_regression_bar_test(
            predicted_return=0.00035, trade_threshold=0.0004
        )

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
            # Bullish context: lowers long threshold
            threshold_modifier=ThresholdModifier(long_factor=0.7, short_factor=1.5),
        )
        router._confirmed_regime = "trending_up"

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

        # BUY should pass: predicted_return 0.00035 > adjusted threshold 0.00028
        assert result["signal"] == Signal.BUY

    def test_regression_strong_signal_unaffected_by_modifier(self) -> None:
        """Strong regression signal should pass regardless of counter-trend modifier."""
        # predicted_return = 0.002 → strong BUY (5x threshold of 0.0004)
        # Even with bearish long_factor=1.5, threshold = 0.0006
        # 0.002 >> 0.0006 → still BUY
        runner, decision_fns, caches, pm = self._setup_regression_bar_test(
            predicted_return=0.002, trade_threshold=0.0004
        )

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
            threshold_modifier=ThresholdModifier(long_factor=1.5, short_factor=0.7),
        )
        router._confirmed_regime = "trending_up"

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

        # Strong BUY should pass even with counter-trend modifier
        assert result["signal"] == Signal.BUY

    def test_regression_no_modifier_unchanged(self) -> None:
        """Without threshold_modifier, regression signal should pass through unchanged."""
        runner, decision_fns, caches, pm = self._setup_regression_bar_test(
            predicted_return=0.0005, trade_threshold=0.0004
        )

        router = MagicMock()
        router.route.return_value = RouteDecision(
            active_regime="trending_up",
            regime_confidence=0.8,
            active_model="trend_long",
            transition=None,
            reasoning="test",
            # No threshold_modifier
        )
        router._confirmed_regime = "trending_up"

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

        # BUY should pass through without modification
        assert result["signal"] == Signal.BUY
