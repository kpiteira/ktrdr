"""Regime router for ensemble backtesting.

Routes to per-regime signal models based on regime classification output.
Implements stability filter to prevent costly regime flicker (Scenario 7).
"""

from dataclasses import dataclass

from ktrdr.backtesting.position_manager import PositionStatus
from ktrdr.config.ensemble_config import CompositionConfig

REGIME_NAMES = ["trending_up", "trending_down", "ranging", "volatile"]


@dataclass
class TransitionAction:
    """What to do during a regime transition."""

    close_position: bool
    from_regime: str
    to_regime: str


@dataclass
class RouteDecision:
    """Result of regime routing."""

    active_regime: str
    regime_confidence: float
    active_model: str | None
    transition: TransitionAction | None
    reasoning: str


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
    ) -> RouteDecision:
        """Determine which signal model to run for this bar.

        1. Find dominant regime (highest probability above threshold)
        2. Apply stability filter: require N consecutive bars before transitioning
        3. If stable transition: apply transition policy (close_and_switch / let_run)
        4. Look up route rule for active regime
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
            active_regime, proposed_confidence, transition, reasoning
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
    ) -> RouteDecision:
        """Build a RouteDecision from the active regime."""
        rule = self._composition.rules.get(active_regime)
        active_model = rule.model if rule else None

        return RouteDecision(
            active_regime=active_regime,
            regime_confidence=confidence,
            active_model=active_model,
            transition=transition,
            reasoning=reasoning,
        )
