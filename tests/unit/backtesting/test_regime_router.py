"""Tests for RegimeRouter — regime-based model routing with stability filter."""

import pytest

from ktrdr.backtesting.position_manager import PositionStatus
from ktrdr.backtesting.regime_router import (
    RegimeRouter,
    RouteDecision,
)
from ktrdr.config.ensemble_config import CompositionConfig, RouteRule


@pytest.fixture
def composition() -> CompositionConfig:
    """Standard composition config for testing."""
    return CompositionConfig(
        type="regime_route",
        gate_model="regime",
        regime_threshold=0.4,
        stability_bars=3,
        rules={
            "trending_up": RouteRule(model="trend_long"),
            "trending_down": RouteRule(model="trend_short"),
            "ranging": RouteRule(model="mean_reversion"),
            "volatile": RouteRule(action="FLAT"),
        },
        on_regime_transition="close_and_switch",
    )


@pytest.fixture
def router(composition: CompositionConfig) -> RegimeRouter:
    return RegimeRouter(composition)


class TestDominantRegime:
    """Tests for identifying the dominant regime from probabilities."""

    def test_highest_prob_above_threshold(self, router: RegimeRouter) -> None:
        result = router.route(
            regime_probs={
                "trending_up": 0.65,
                "trending_down": 0.10,
                "ranging": 0.20,
                "volatile": 0.05,
            },
            previous_regime=None,
            current_position=PositionStatus.FLAT,
        )
        assert result.active_regime == "trending_up"
        assert result.regime_confidence == pytest.approx(0.65)

    def test_below_threshold_defaults_to_volatile(self, router: RegimeRouter) -> None:
        """When no class is above threshold, default to volatile (most conservative)."""
        result = router.route(
            regime_probs={
                "trending_up": 0.30,
                "trending_down": 0.30,
                "ranging": 0.30,
                "volatile": 0.10,
            },
            previous_regime=None,
            current_position=PositionStatus.FLAT,
        )
        assert result.active_regime == "volatile"

    def test_correct_model_for_each_regime(
        self, composition: CompositionConfig
    ) -> None:
        """Each regime routes to the correct signal model."""
        for regime, expected_model in [
            ("trending_up", "trend_long"),
            ("trending_down", "trend_short"),
            ("ranging", "mean_reversion"),
        ]:
            # Fresh router per regime to avoid stability filter state
            r = RegimeRouter(composition)
            probs = dict.fromkeys(
                ["trending_up", "trending_down", "ranging", "volatile"], 0.05
            )
            probs[regime] = 0.80
            result = r.route(
                probs, previous_regime=None, current_position=PositionStatus.FLAT
            )
            assert result.active_model == expected_model, (
                f"Regime {regime} should route to {expected_model}"
            )

    def test_flat_action_returns_no_model(self, router: RegimeRouter) -> None:
        result = router.route(
            regime_probs={
                "trending_up": 0.05,
                "trending_down": 0.05,
                "ranging": 0.05,
                "volatile": 0.85,
            },
            previous_regime=None,
            current_position=PositionStatus.FLAT,
        )
        assert result.active_model is None


class TestStabilityFilter:
    """Tests for the stability filter that prevents regime flicker."""

    def test_no_transition_before_n_bars(self, router: RegimeRouter) -> None:
        """Stability filter prevents transition before N consecutive bars."""
        trending_up = {
            "trending_up": 0.80,
            "trending_down": 0.05,
            "ranging": 0.10,
            "volatile": 0.05,
        }
        ranging = {
            "trending_up": 0.05,
            "trending_down": 0.05,
            "ranging": 0.80,
            "volatile": 0.10,
        }

        # Establish trending_up as current regime
        router.route(
            trending_up, previous_regime=None, current_position=PositionStatus.FLAT
        )

        # Switch to ranging — should NOT transition for first 2 bars (stability_bars=3)
        result1 = router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )
        assert result1.active_regime == "trending_up"  # Still old regime
        assert result1.transition is None

        result2 = router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )
        assert result2.active_regime == "trending_up"
        assert result2.transition is None

    def test_transition_after_n_bars(self, router: RegimeRouter) -> None:
        """Stability filter allows transition after N consecutive bars."""
        trending_up = {
            "trending_up": 0.80,
            "trending_down": 0.05,
            "ranging": 0.10,
            "volatile": 0.05,
        }
        ranging = {
            "trending_up": 0.05,
            "trending_down": 0.05,
            "ranging": 0.80,
            "volatile": 0.10,
        }

        # Establish current regime
        router.route(
            trending_up, previous_regime=None, current_position=PositionStatus.FLAT
        )

        # 3 consecutive bars of ranging (stability_bars=3)
        router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )
        router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )
        result = router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )

        assert result.active_regime == "ranging"
        assert result.transition is not None
        assert result.transition.from_regime == "trending_up"
        assert result.transition.to_regime == "ranging"

    def test_flicker_resets_counter(self, router: RegimeRouter) -> None:
        """Flickering back to old regime resets the stability counter."""
        trending_up = {
            "trending_up": 0.80,
            "trending_down": 0.05,
            "ranging": 0.10,
            "volatile": 0.05,
        }
        ranging = {
            "trending_up": 0.05,
            "trending_down": 0.05,
            "ranging": 0.80,
            "volatile": 0.10,
        }

        # Establish current regime
        router.route(
            trending_up, previous_regime=None, current_position=PositionStatus.FLAT
        )

        # 2 bars of ranging
        router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )
        router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )

        # Flicker back to trending_up — resets counter
        router.route(
            trending_up,
            previous_regime="trending_up",
            current_position=PositionStatus.FLAT,
        )

        # 2 more bars of ranging — should NOT transition yet (counter reset)
        result1 = router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )
        assert result1.active_regime == "trending_up"

        result2 = router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )
        assert result2.active_regime == "trending_up"

        # 3rd bar — NOW transition
        result3 = router.route(
            ranging, previous_regime="trending_up", current_position=PositionStatus.FLAT
        )
        assert result3.active_regime == "ranging"
        assert result3.transition is not None


class TestTransitionHandling:
    """Tests for transition policies."""

    def test_close_and_switch_closes_position(self, router: RegimeRouter) -> None:
        trending_up = {
            "trending_up": 0.80,
            "trending_down": 0.05,
            "ranging": 0.10,
            "volatile": 0.05,
        }
        ranging = {
            "trending_up": 0.05,
            "trending_down": 0.05,
            "ranging": 0.80,
            "volatile": 0.10,
        }

        router.route(
            trending_up, previous_regime=None, current_position=PositionStatus.FLAT
        )

        # Transition after stability period
        for _ in range(3):
            result = router.route(
                ranging,
                previous_regime="trending_up",
                current_position=PositionStatus.LONG,
            )

        assert result.transition is not None
        assert result.transition.close_position is True

    def test_let_run_does_not_close(self, composition: CompositionConfig) -> None:
        let_run_comp = composition.model_copy(
            update={"on_regime_transition": "let_run"}
        )
        router = RegimeRouter(let_run_comp)

        trending_up = {
            "trending_up": 0.80,
            "trending_down": 0.05,
            "ranging": 0.10,
            "volatile": 0.05,
        }
        ranging = {
            "trending_up": 0.05,
            "trending_down": 0.05,
            "ranging": 0.80,
            "volatile": 0.10,
        }

        router.route(
            trending_up, previous_regime=None, current_position=PositionStatus.FLAT
        )

        for _ in range(3):
            result = router.route(
                ranging,
                previous_regime="trending_up",
                current_position=PositionStatus.LONG,
            )

        assert result.transition is not None
        assert result.transition.close_position is False


class TestRouteDecision:
    """Tests for RouteDecision structure."""

    def test_has_reasoning(self, router: RegimeRouter) -> None:
        result = router.route(
            regime_probs={
                "trending_up": 0.80,
                "trending_down": 0.05,
                "ranging": 0.10,
                "volatile": 0.05,
            },
            previous_regime=None,
            current_position=PositionStatus.FLAT,
        )
        assert isinstance(result, RouteDecision)
        assert isinstance(result.reasoning, str)
        assert len(result.reasoning) > 0

    def test_no_transition_on_same_regime(self, router: RegimeRouter) -> None:
        trending_up = {
            "trending_up": 0.80,
            "trending_down": 0.05,
            "ranging": 0.10,
            "volatile": 0.05,
        }
        router.route(
            trending_up, previous_regime=None, current_position=PositionStatus.FLAT
        )
        result = router.route(
            trending_up,
            previous_regime="trending_up",
            current_position=PositionStatus.FLAT,
        )
        assert result.transition is None
        assert result.active_regime == "trending_up"
