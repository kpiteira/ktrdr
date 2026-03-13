"""Regime router for ensemble backtesting.

Routes to per-regime signal models based on regime classification output.
Implements stability filter to prevent costly regime flicker (Scenario 7).
"""

from dataclasses import dataclass, field

from ktrdr.backtesting.position_manager import PositionStatus
from ktrdr.config.ensemble_config import CompositionConfig
from ktrdr.decision.base import Signal

REGIME_NAMES = ["trending_up", "trending_down", "ranging", "volatile"]


@dataclass
class TransitionAction:
    """What to do during a regime transition."""

    close_position: bool
    from_regime: str
    to_regime: str


@dataclass
class ThresholdModifier:
    """Direction-specific threshold adjustments from context analysis.

    Multiplies the base confidence threshold for signal decisions:
    - long_factor < 1.0 means lower threshold (easier to go long)
    - short_factor > 1.0 means higher threshold (harder to go short)
    """

    long_factor: float
    short_factor: float

    def apply(self, base_threshold: float, signal: Signal) -> float:
        """Apply direction-specific modifier to base threshold."""
        if signal == Signal.BUY:
            return base_threshold * self.long_factor
        elif signal == Signal.SELL:
            return base_threshold * self.short_factor
        return base_threshold


@dataclass
class RouteDecision:
    """Result of regime routing."""

    active_regime: str
    regime_confidence: float
    active_model: str | None
    transition: TransitionAction | None
    reasoning: str
    threshold_modifier: ThresholdModifier | None = field(default=None)


class RegimeRouter:
    """Routes to per-regime signal models based on regime classification output.

    Applies a stability filter requiring N consecutive bars of a new regime
    before transitioning, preventing costly flicker between regimes.
    """

    def __init__(self, composition: CompositionConfig) -> None:
        self._composition = composition
        self._pending_regime: str | None = None
        self._regime_counter: int = 0
        self._confirmed_regime: str | None = None

    def route(
        self,
        regime_probs: dict[str, float],
        previous_regime: str | None,
        current_position: PositionStatus,
        context_probs: dict[str, float] | None = None,
    ) -> RouteDecision:
        """Determine which signal model to run for this bar.

        1. Find dominant regime (highest probability above threshold)
        2. Apply stability filter: require N consecutive bars before transitioning
        3. If stable transition: apply transition policy (close_and_switch / let_run)
        4. Look up route rule for active regime
        5. If context_probs provided, compute threshold modifier
        """
        # Determine proposed regime from probabilities
        proposed_regime = self._get_dominant_regime(regime_probs)
        proposed_confidence = regime_probs.get(proposed_regime, 0.0)

        # On first call, establish regime immediately
        if self._confirmed_regime is None:
            self._confirmed_regime = proposed_regime
            self._pending_regime = None
            self._regime_counter = 0
            return self._build_decision(
                proposed_regime,
                proposed_confidence,
                transition=None,
                reasoning=f"Initial regime: {proposed_regime} (confidence: {proposed_confidence:.2f})",
                context_probs=context_probs,
            )

        # Apply stability filter
        transition = None
        active_regime = self._confirmed_regime

        if proposed_regime != self._confirmed_regime:
            # New regime proposed — track stability
            if proposed_regime == self._pending_regime:
                self._regime_counter += 1
            else:
                # Different pending regime or first divergence — start counting
                self._pending_regime = proposed_regime
                self._regime_counter = 1

            if self._regime_counter >= self._composition.stability_bars:
                # Stable transition confirmed
                close = self._composition.on_regime_transition == "close_and_switch"
                transition = TransitionAction(
                    close_position=close,
                    from_regime=self._confirmed_regime,
                    to_regime=proposed_regime,
                )
                active_regime = proposed_regime
                self._confirmed_regime = proposed_regime
                self._pending_regime = None
                self._regime_counter = 0
            # else: stay on confirmed regime
        else:
            # Same as confirmed — reset pending
            self._pending_regime = None
            self._regime_counter = 0

        if transition:
            reasoning = (
                f"Regime transition: {transition.from_regime} → {transition.to_regime} "
                f"(stable for {self._composition.stability_bars} bars)"
            )
        elif self._pending_regime:
            reasoning = (
                f"Regime: {active_regime} (pending {self._pending_regime}, "
                f"{self._regime_counter}/{self._composition.stability_bars} bars)"
            )
        else:
            reasoning = (
                f"Regime: {active_regime} (confidence: {proposed_confidence:.2f})"
            )

        return self._build_decision(
            active_regime,
            proposed_confidence,
            transition,
            reasoning,
            context_probs=context_probs,
        )

    def _get_dominant_regime(self, regime_probs: dict[str, float]) -> str:
        """Find the regime with highest probability above threshold.

        If no regime exceeds the threshold, defaults to 'volatile' (most conservative).
        """
        threshold = self._composition.regime_threshold
        best_regime = None
        best_prob = -1.0

        for regime, prob in regime_probs.items():
            if prob >= threshold and prob > best_prob:
                best_regime = regime
                best_prob = prob

        return best_regime if best_regime is not None else "volatile"

    def _build_decision(
        self,
        active_regime: str,
        confidence: float,
        transition: TransitionAction | None,
        reasoning: str,
        context_probs: dict[str, float] | None = None,
    ) -> RouteDecision:
        """Build a RouteDecision from the active regime."""
        rule = self._composition.rules.get(active_regime)
        active_model = rule.model if rule else None

        # Compute context-based threshold modifier if available
        threshold_modifier = None
        if context_probs and self._composition.context_modifiers:
            threshold_modifier = self._compute_threshold_modifier(context_probs)

        return RouteDecision(
            active_regime=active_regime,
            regime_confidence=confidence,
            active_model=active_model,
            transition=transition,
            reasoning=reasoning,
            threshold_modifier=threshold_modifier,
        )

    def _compute_threshold_modifier(
        self, context_probs: dict[str, float]
    ) -> ThresholdModifier:
        """Compute direction-specific threshold adjustments from context.

        Net bias (bullish - bearish) drives asymmetric adjustments:
        - Positive bias (bullish): lowers long thresholds, raises short thresholds
        - Negative bias (bearish): lowers short thresholds, raises long thresholds
        """
        bullish_conf = context_probs.get("bullish", 0.0)
        bearish_conf = context_probs.get("bearish", 0.0)
        # Caller guarantees context_modifiers is not None
        assert self._composition.context_modifiers is not None
        mods = self._composition.context_modifiers

        net_bias = bullish_conf - bearish_conf  # Range: [-1, +1]

        if net_bias > 0:  # Bullish context
            long_factor = 1.0 - (net_bias * mods.aligned_discount)
            short_factor = 1.0 + (net_bias * mods.counter_premium)
        else:  # Bearish context
            long_factor = 1.0 + (abs(net_bias) * mods.counter_premium)
            short_factor = 1.0 - (abs(net_bias) * mods.aligned_discount)

        return ThresholdModifier(long_factor=long_factor, short_factor=short_factor)
