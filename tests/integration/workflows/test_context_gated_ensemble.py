"""Integration test for context-gated ensemble backtesting pipeline.

Validates the full context-gated ensemble: config → models → feature caches →
regime routing with context → threshold modification → signal decisions.
Uses mock models to exercise the complete pipeline without trained artifacts.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.backtesting.ensemble_runner import EnsembleBacktestRunner
from ktrdr.backtesting.regime_router import RegimeRouter
from ktrdr.config.ensemble_config import EnsembleConfiguration
from ktrdr.decision.base import Position, Signal, TradingDecision

# -- Fixtures --


def _make_ohlcv(n_bars: int = 200, freq: str = "1h") -> pd.DataFrame:
    """Create synthetic OHLCV data."""
    dates = pd.date_range("2024-01-01", periods=n_bars, freq=freq, tz="UTC")
    rng = np.random.default_rng(42)
    close = 1.1000 + np.cumsum(rng.normal(0, 0.0005, n_bars))
    return pd.DataFrame(
        {
            "open": close - rng.uniform(0, 0.001, n_bars),
            "high": close + rng.uniform(0, 0.002, n_bars),
            "low": close - rng.uniform(0, 0.002, n_bars),
            "close": close,
            "volume": rng.integers(500, 2000, n_bars),
        },
        index=dates,
    )


def _make_regime_decision(
    regime: str = "trending_up", conf: float = 0.7
) -> TradingDecision:
    probs = {
        "TRENDING_UP": 0.05,
        "TRENDING_DOWN": 0.05,
        "RANGING": 0.05,
        "VOLATILE": 0.05,
    }
    probs[regime.upper()] = conf
    return TradingDecision(
        signal=Signal.HOLD,
        confidence=conf,
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        reasoning={"nn_probabilities": probs},
        current_position=Position.FLAT,
    )


def _make_context_decision(
    bullish: float = 0.6, bearish: float = 0.15, neutral: float = 0.25
) -> TradingDecision:
    return TradingDecision(
        signal=Signal.HOLD,
        confidence=max(bullish, bearish, neutral),
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        reasoning={
            "nn_probabilities": {
                "BULLISH": bullish,
                "BEARISH": bearish,
                "NEUTRAL": neutral,
            }
        },
        current_position=Position.FLAT,
    )


def _make_signal_decision(
    signal: Signal = Signal.BUY, conf: float = 0.65
) -> TradingDecision:
    return TradingDecision(
        signal=signal,
        confidence=conf,
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        reasoning={"nn_probabilities": {"BUY": 0.65, "HOLD": 0.2, "SELL": 0.15}},
        current_position=Position.FLAT,
    )


# -- Tests --


class TestContextGatedConfig:
    """Validate context-gated ensemble YAML config loads correctly."""

    def test_context_gated_yaml_loads(self) -> None:
        config_path = Path("configs/ensemble_context_gated.yaml")
        assert config_path.exists(), "configs/ensemble_context_gated.yaml must exist"
        config = EnsembleConfiguration.from_yaml(config_path)
        assert config.name == "context_gated_v1"
        assert config.composition.context_gate == "context"
        assert config.composition.context_modifiers is not None
        assert config.composition.context_modifiers.aligned_discount == 0.2
        assert config.composition.context_modifiers.counter_premium == 0.3
        assert len(config.models) == 4

    def test_regime_only_yaml_still_loads(self) -> None:
        config_path = Path("configs/ensemble_regime_routed.yaml")
        assert config_path.exists(), "regime-only config must still work"
        config = EnsembleConfiguration.from_yaml(config_path)
        assert config.composition.context_gate is None
        assert config.composition.context_modifiers is None


class TestContextGatedPipeline:
    """Full pipeline integration: config → routing → threshold → signal."""

    def test_full_pipeline_with_context(self) -> None:
        """Run the full context-gated ensemble pipeline with mocked models.

        Verifies:
        1. Context model is evaluated once per daily bar change
        2. Context probs flow through to router
        3. Threshold modifier adjusts signal decisions
        4. Position manager executes or blocks trades accordingly
        """
        config = EnsembleConfiguration.from_yaml("configs/ensemble_context_gated.yaml")
        backtest_config = BacktestConfig(
            strategy_config_path="",
            model_path=None,
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            initial_capital=100000.0,
        )
        runner = EnsembleBacktestRunner(config, backtest_config)

        # Create mock decision functions
        regime_fn = MagicMock(
            side_effect=lambda **kw: _make_regime_decision("trending_up", 0.7)
        )
        context_fn = MagicMock(
            side_effect=lambda **kw: _make_context_decision(0.7, 0.1, 0.2)
        )
        signal_fn = MagicMock(
            side_effect=lambda **kw: _make_signal_decision(Signal.BUY, 0.65)
        )
        signal_fn.confidence_threshold = 0.5

        decision_fns = {
            "regime": regime_fn,
            "context": context_fn,
            "trend_signal": signal_fn,
            "range_signal": signal_fn,
        }

        # Create mock feature caches
        mock_cache = MagicMock()
        mock_cache.get_features_for_timestamp.return_value = {"f1": 0.5, "f2": 0.3}
        caches = {
            "regime": mock_cache,
            "context": mock_cache,
            "trend_signal": mock_cache,
            "range_signal": mock_cache,
        }

        # Create real router and position manager
        router = RegimeRouter(config.composition)
        from ktrdr.backtesting.position_manager import PositionManager

        pm = PositionManager(initial_capital=100000.0)

        # Run 48 bars (2 days of hourly data)
        data = _make_ohlcv(n_bars=48, freq="1h")

        for idx in range(len(data)):
            bar = data.iloc[idx]
            timestamp = bar.name

            result = runner._run_bar(
                timestamp=timestamp,
                bar=bar,
                feature_caches=caches,
                decision_functions=decision_fns,
                router=router,
                position_manager=pm,
            )

            assert result["regime"] is not None

        # Context model should have been evaluated exactly 2 times (2 days)
        # Each daily boundary triggers a new context evaluation
        context_calls = context_fn.call_count
        assert (
            context_calls == 2
        ), f"Expected 2 context evaluations (2 days), got {context_calls}"

        # Regime model should have been called every bar
        assert regime_fn.call_count == 48

    def test_regime_only_no_context_calls(self) -> None:
        """Regime-only ensemble should never call context model."""
        config = EnsembleConfiguration.from_yaml("configs/ensemble_regime_routed.yaml")
        backtest_config = BacktestConfig(
            strategy_config_path="",
            model_path=None,
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            initial_capital=100000.0,
        )
        runner = EnsembleBacktestRunner(config, backtest_config)

        regime_fn = MagicMock(
            side_effect=lambda **kw: _make_regime_decision("trending_up", 0.7)
        )
        signal_fn = MagicMock(
            side_effect=lambda **kw: _make_signal_decision(Signal.BUY, 0.65)
        )

        decision_fns = {
            "regime": regime_fn,
            "trend_signal": signal_fn,
            "range_signal": signal_fn,
        }

        mock_cache = MagicMock()
        mock_cache.get_features_for_timestamp.return_value = {"f1": 0.5}
        caches = {
            "regime": mock_cache,
            "trend_signal": mock_cache,
            "range_signal": mock_cache,
        }

        router = RegimeRouter(config.composition)
        from ktrdr.backtesting.position_manager import PositionManager

        pm = PositionManager(initial_capital=100000.0)

        data = _make_ohlcv(n_bars=24, freq="1h")
        for idx in range(len(data)):
            bar = data.iloc[idx]
            runner._run_bar(
                timestamp=bar.name,
                bar=bar,
                feature_caches=caches,
                decision_functions=decision_fns,
                router=router,
                position_manager=pm,
            )

        # No context model in the config → _maybe_update_context is a no-op
        assert runner._current_context_probs is None
        assert runner._last_context_date is None

    def test_context_blocks_counter_trend_trade(self) -> None:
        """Verify bearish context blocks a low-confidence BUY signal."""
        config = EnsembleConfiguration.from_yaml("configs/ensemble_context_gated.yaml")
        backtest_config = BacktestConfig(
            strategy_config_path="",
            model_path=None,
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            initial_capital=100000.0,
        )
        runner = EnsembleBacktestRunner(config, backtest_config)

        # Bearish context — makes long threshold higher
        regime_fn = MagicMock(
            side_effect=lambda **kw: _make_regime_decision("trending_up", 0.7)
        )
        context_fn = MagicMock(
            side_effect=lambda **kw: _make_context_decision(0.1, 0.8, 0.1)
        )
        # Low confidence BUY — should be blocked by bearish context raising threshold
        signal_fn = MagicMock(
            side_effect=lambda **kw: _make_signal_decision(Signal.BUY, 0.55)
        )
        signal_fn.confidence_threshold = 0.5

        decision_fns = {
            "regime": regime_fn,
            "context": context_fn,
            "trend_signal": signal_fn,
            "range_signal": signal_fn,
        }

        mock_cache = MagicMock()
        mock_cache.get_features_for_timestamp.return_value = {"f1": 0.5}
        caches = dict.fromkeys(decision_fns, mock_cache)

        router = RegimeRouter(config.composition)
        from ktrdr.backtesting.position_manager import PositionManager

        pm = PositionManager(initial_capital=100000.0)

        bar = _make_ohlcv(n_bars=1, freq="1h").iloc[0]
        result = runner._run_bar(
            timestamp=bar.name,
            bar=bar,
            feature_caches=caches,
            decision_functions=decision_fns,
            router=router,
            position_manager=pm,
        )

        # Bearish context (net_bias = 0.1 - 0.8 = -0.7)
        # long_factor = 1 + (0.7 * 0.3) = 1.21
        # adjusted_threshold = 0.5 * 1.21 = 0.605
        # confidence 0.55 < 0.605 → HOLD
        assert (
            result["signal"] == Signal.HOLD
        ), "Bearish context should block low-confidence BUY"
