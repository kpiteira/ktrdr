"""EnsembleBacktestRunner — multi-model regime-routed backtesting.

Orchestrates multiple ModelBundles, FeatureCaches, and DecisionFunctions
with a RegimeRouter to run per-bar: regime classification → routing →
signal model → position management.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from ktrdr.backtesting.decision_function import DecisionFunction
from ktrdr.backtesting.engine import BacktestConfig
from ktrdr.backtesting.feature_cache import FeatureCache
from ktrdr.backtesting.model_bundle import ModelBundle
from ktrdr.backtesting.position_manager import PositionManager, PositionStatus, Trade
from ktrdr.backtesting.regime_router import RegimeRouter
from ktrdr.config.ensemble_config import EnsembleConfiguration
from ktrdr.decision.base import Signal

logger = logging.getLogger(__name__)

REGIME_NAMES = ["trending_up", "trending_down", "ranging", "volatile"]


@dataclass
class EnsembleBacktestResults:
    """Results from an ensemble backtest with per-regime breakdown."""

    ensemble_name: str
    symbol: str
    timeframe: str
    total_bars: int
    trades: list[Trade]
    per_regime_metrics: dict[str, dict[str, Any]]
    transition_count: int
    transition_cost: float
    regime_sequence: list[dict[str, Any]]
    execution_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert results to serializable dictionary."""
        return {
            "ensemble_name": self.ensemble_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "total_bars": self.total_bars,
            "trade_count": len(self.trades),
            "per_regime_metrics": self.per_regime_metrics,
            "transition_count": self.transition_count,
            "transition_cost": self.transition_cost,
            "execution_time_seconds": self.execution_time_seconds,
        }


class EnsembleBacktestRunner:
    """Orchestrates multi-model backtesting with regime routing.

    Loads all model bundles, creates per-model FeatureCaches and
    DecisionFunctions, runs per-bar loop with regime classification →
    routing → signal model → position management. Shares one
    PositionManager across all regime-routed models.
    """

    def __init__(
        self,
        ensemble_config: EnsembleConfiguration,
        backtest_config: BacktestConfig,
    ) -> None:
        self.ensemble_config = ensemble_config
        self.backtest_config = backtest_config
        # Context gate tracking — evaluated once per daily bar close
        self._current_context_probs: dict[str, float] | None = None
        self._last_context_date: date | None = None

    def _load_models(self) -> dict[str, ModelBundle]:
        """Load all model bundles referenced in ensemble config."""
        bundles: dict[str, ModelBundle] = {}
        for name, model_ref in self.ensemble_config.models.items():
            logger.info(f"Loading model '{name}' from {model_ref.model_path}")
            bundles[name] = ModelBundle.load(model_ref.model_path)
        return bundles

    def _create_feature_caches(
        self,
        bundles: dict[str, ModelBundle],
    ) -> dict[str, FeatureCache]:
        """Create one FeatureCache per model (each has different indicators/features)."""
        caches: dict[str, FeatureCache] = {}
        for name, bundle in bundles.items():
            caches[name] = FeatureCache(
                config=bundle.strategy_config,
                model_metadata=bundle.metadata,
            )
        return caches

    def _create_decision_functions(
        self,
        bundles: dict[str, ModelBundle],
    ) -> dict[str, DecisionFunction]:
        """Create one DecisionFunction per model with appropriate output_type."""
        fns: dict[str, DecisionFunction] = {}
        for name, bundle in bundles.items():
            # Extract decisions config from strategy config
            decisions = getattr(bundle.strategy_config, "decisions", {})
            if hasattr(decisions, "model_dump"):
                decisions_config = decisions.model_dump()
            elif isinstance(decisions, dict):
                decisions_config = decisions
            else:
                decisions_config = {}

            output_type = bundle.metadata.output_type

            # Inject ensemble-level allow_short_from_flat for signal models
            if self.ensemble_config.composition.allow_short_from_flat:
                if output_type == "classification":
                    decisions_config["allow_short_from_flat"] = True

            fns[name] = DecisionFunction(
                model=bundle.model,
                feature_names=bundle.feature_names,
                decisions_config=decisions_config,
                output_type=output_type,
            )
        return fns

    def _interpret_regime_output(self, decision: Any) -> dict[str, float]:
        """Convert regime DecisionFunction output to regime probabilities.

        The DecisionFunction for regime models returns probabilities with
        uppercase keys (TRENDING_UP, etc.) in reasoning["nn_probabilities"].
        The RegimeRouter expects lowercase keys.
        """
        nn_probs: dict[str, float] = decision.reasoning.get("nn_probabilities", {})
        return {name: float(nn_probs.get(name.upper(), 0.0)) for name in REGIME_NAMES}

    def _interpret_context_output(self, decision: Any) -> dict[str, float]:
        """Convert context DecisionFunction output to context probabilities.

        The DecisionFunction for context models returns probabilities with
        uppercase keys (BULLISH, BEARISH, NEUTRAL) in reasoning["nn_probabilities"].
        The RegimeRouter expects lowercase keys.
        """
        nn_probs: dict[str, float] = decision.reasoning.get("nn_probabilities", {})
        return {
            "bullish": float(nn_probs.get("BULLISH", 0.0)),
            "bearish": float(nn_probs.get("BEARISH", 0.0)),
            "neutral": float(nn_probs.get("NEUTRAL", 0.0)),
        }

    def _maybe_update_context(
        self,
        timestamp: pd.Timestamp,
        feature_caches: dict[str, Any],
        decision_functions: dict[str, Any],
        position: PositionStatus,
        bar: pd.Series,
    ) -> None:
        """Re-evaluate context model when daily bar closes.

        Context is evaluated once per daily bar change, not every hourly bar.
        The result is held constant for all bars within the same day.
        """
        context_gate = self.ensemble_config.composition.context_gate
        if context_gate is None:
            return

        bar_date = timestamp.date()
        if self._last_context_date is not None and bar_date <= self._last_context_date:
            return  # Same day — use cached context

        # New day — re-evaluate context model
        context_features = feature_caches[context_gate].get_features_for_timestamp(
            timestamp
        )
        if context_features is not None:
            context_decision = decision_functions[context_gate](
                features=context_features,
                position=position,
                bar=bar,
            )
            self._current_context_probs = self._interpret_context_output(
                context_decision
            )
            logger.debug(
                f"Context updated for {bar_date}: {self._current_context_probs}"
            )
        self._last_context_date = bar_date

    def _run_bar(
        self,
        timestamp: pd.Timestamp,
        bar: pd.Series,
        feature_caches: dict[str, FeatureCache],
        decision_functions: dict[str, Any],
        router: RegimeRouter,
        position_manager: PositionManager,
    ) -> dict[str, Any]:
        """Execute one bar of the ensemble backtest.

        Returns:
            Dict with keys: regime, signal, transition, active_model
        """
        gate_model_name = self.ensemble_config.composition.gate_model

        # 0. Update context if daily bar closed (once per day)
        self._maybe_update_context(
            timestamp=timestamp,
            feature_caches=feature_caches,
            decision_functions=decision_functions,
            position=position_manager.current_position_status,
            bar=bar,
        )

        # 1. Get regime features and classify
        regime_features = feature_caches[gate_model_name].get_features_for_timestamp(
            timestamp
        )
        if regime_features is None:
            return {
                "regime": None,
                "signal": Signal.HOLD,
                "transition": None,
                "active_model": None,
            }

        regime_decision = decision_functions[gate_model_name](
            features=regime_features,
            position=position_manager.current_position_status,
            bar=bar,
        )
        regime_probs = self._interpret_regime_output(regime_decision)

        # 2. Route to signal model (with optional context)
        route = router.route(
            regime_probs=regime_probs,
            previous_regime=router._confirmed_regime,
            current_position=position_manager.current_position_status,
            context_probs=self._current_context_probs,
        )

        # 3. Handle transition — close position if required
        if route.transition and route.transition.close_position:
            # Close current position
            pos = position_manager.current_position_status
            if pos == PositionStatus.LONG:
                close_signal = Signal.SELL
            elif pos == PositionStatus.SHORT:
                close_signal = Signal.BUY
            else:
                close_signal = Signal.HOLD

            if close_signal != Signal.HOLD:
                position_manager.execute_trade(
                    signal=close_signal,
                    price=bar["close"],
                    timestamp=timestamp,
                    symbol=self.backtest_config.symbol,
                    decision_metadata={
                        "reason": "regime_transition",
                        "from_regime": route.transition.from_regime,
                        "to_regime": route.transition.to_regime,
                    },
                )

        # 4. Run signal model (or HOLD for FLAT routes)
        final_signal = Signal.HOLD
        if route.active_model is not None:
            signal_features = feature_caches[
                route.active_model
            ].get_features_for_timestamp(timestamp)
            if signal_features is not None:
                signal_decision = decision_functions[route.active_model](
                    features=signal_features,
                    position=position_manager.current_position_status,
                    bar=bar,
                )
                final_signal = signal_decision.signal

                # 5. Apply context-adjusted threshold if modifier present
                if route.threshold_modifier and final_signal != Signal.HOLD:
                    base_threshold = getattr(
                        decision_functions[route.active_model],
                        "confidence_threshold",
                        0.5,
                    )
                    adjusted_threshold = route.threshold_modifier.apply(
                        base_threshold, final_signal
                    )
                    if signal_decision.confidence < adjusted_threshold:
                        final_signal = Signal.HOLD

        return {
            "regime": route.active_regime,
            "signal": final_signal,
            "transition": route.transition,
            "active_model": route.active_model,
        }

    async def run(self) -> EnsembleBacktestResults:
        """Execute the full ensemble backtest.

        Returns:
            EnsembleBacktestResults with per-regime breakdown
        """
        execution_start = time.time()

        logger.info(
            f"Starting ensemble backtest: {self.ensemble_config.name} | "
            f"{self.backtest_config.symbol} {self.backtest_config.timeframe} | "
            f"{self.backtest_config.start_date} to {self.backtest_config.end_date}"
        )

        # 1. Load all models
        bundles = self._load_models()

        # 2. Create per-model feature caches and decision functions
        feature_caches = self._create_feature_caches(bundles)
        decision_functions = self._create_decision_functions(bundles)

        # 3. Load OHLCV data for all required timeframes
        from ktrdr.data.repository import DataRepository

        repo = DataRepository()
        base_tf = self.backtest_config.timeframe

        # Collect all timeframes needed across ensemble models
        required_tfs: set[str] = {base_tf}
        for _name, bundle in bundles.items():
            for tf in bundle.metadata.training_timeframes:
                required_tfs.add(tf)

        # Load each required timeframe
        multi_tf_data: dict[str, pd.DataFrame] = {}
        for tf in required_tfs:
            multi_tf_data[tf] = repo.load_from_cache(
                symbol=self.backtest_config.symbol,
                timeframe=tf,
                start_date=self.backtest_config.start_date,
                end_date=self.backtest_config.end_date,
            )
        data = multi_tf_data[base_tf]

        # 4. Compute features for all models
        # Each model's cache gets the full multi-TF dict; it selects
        # the timeframe(s) it needs based on its strategy config.
        for _name, cache in feature_caches.items():
            cache.compute_all_features(multi_tf_data)

        # 5. Create router and position manager
        router = RegimeRouter(self.ensemble_config.composition)
        position_manager = PositionManager(
            initial_capital=self.backtest_config.initial_capital,
            commission=self.backtest_config.commission,
            slippage=self.backtest_config.slippage,
        )

        # 6. Per-bar simulation
        start_idx = 50  # Indicator warm-up
        regime_bars: dict[str, int] = dict.fromkeys(REGIME_NAMES, 0)
        regime_trades: dict[str, list[Trade]] = {name: [] for name in REGIME_NAMES}
        transition_count = 0
        regime_sequence: list[dict[str, Any]] = []

        for idx in range(start_idx, len(data)):
            bar = data.iloc[idx]
            timestamp: pd.Timestamp = bar.name  # type: ignore[assignment]

            bar_result = self._run_bar(
                timestamp=timestamp,
                bar=bar,
                feature_caches=feature_caches,
                decision_functions=decision_functions,
                router=router,
                position_manager=position_manager,
            )

            regime = bar_result.get("regime")
            if regime:
                regime_bars[regime] = regime_bars.get(regime, 0) + 1

            # Track transitions
            if bar_result.get("transition"):
                transition_count += 1
                regime_sequence.append(
                    {
                        "timestamp": str(timestamp),
                        "from": bar_result["transition"].from_regime,
                        "to": bar_result["transition"].to_regime,
                    }
                )

            # Execute signal
            signal = bar_result.get("signal", Signal.HOLD)
            if signal != Signal.HOLD:
                trade = position_manager.execute_trade(
                    signal=signal,
                    price=bar["close"],
                    timestamp=timestamp,
                    symbol=self.backtest_config.symbol,
                )
                if trade and regime:
                    if regime not in regime_trades:
                        regime_trades[regime] = []
                    regime_trades[regime].append(trade)

            # Mark-to-market
            position_manager.update_position(bar["close"], timestamp)

        # 7. Force close any open position
        if position_manager.current_position_status != PositionStatus.FLAT:
            last_bar = data.iloc[-1]
            close_signal = (
                Signal.SELL
                if position_manager.current_position_status == PositionStatus.LONG
                else Signal.BUY
            )
            position_manager.execute_trade(
                signal=close_signal,
                price=last_bar["close"],
                timestamp=last_bar.name,  # type: ignore[arg-type]
                symbol=self.backtest_config.symbol,
            )

        # 8. Build per-regime metrics
        all_trades = position_manager.get_trade_history()
        per_regime_metrics: dict[str, dict[str, Any]] = {}
        for regime in REGIME_NAMES:
            trades = regime_trades.get(regime, [])
            per_regime_metrics[regime] = {
                "bars": regime_bars.get(regime, 0),
                "trades": len(trades),
            }

        execution_time = time.time() - execution_start

        return EnsembleBacktestResults(
            ensemble_name=self.ensemble_config.name,
            symbol=self.backtest_config.symbol,
            timeframe=self.backtest_config.timeframe,
            total_bars=len(data) - start_idx,
            trades=all_trades,
            per_regime_metrics=per_regime_metrics,
            transition_count=transition_count,
            transition_cost=0.0,  # TODO: Calculate from transition trades
            regime_sequence=regime_sequence,
            execution_time_seconds=execution_time,
        )
