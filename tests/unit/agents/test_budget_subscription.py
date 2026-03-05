"""Tests for budget tracking with subscription model.

Task 5.3: With containerized agents on subscription pricing, budget
tracking should not block evolution runs.
"""

import pytest


class TestBudgetDisabledWithZeroLimit:
    """When daily_limit is 0, budget tracking is disabled."""

    @pytest.fixture
    def tracker_disabled(self, tmp_path):
        """Create a BudgetTracker with budget disabled (limit=0)."""
        from ktrdr.agents.budget import BudgetTracker

        budget_dir = tmp_path / "budget"
        budget_dir.mkdir()
        return BudgetTracker(daily_limit=0.0, data_dir=str(budget_dir))

    def test_can_spend_always_true_when_disabled(self, tracker_disabled):
        """can_spend returns True regardless of spend when limit is 0."""
        can_spend, reason = tracker_disabled.can_spend()
        assert can_spend is True
        assert reason == "ok"

    def test_can_spend_true_even_after_recording(self, tracker_disabled):
        """can_spend still True after recording spend when disabled."""
        tracker_disabled.record_spend(100.0, "op_expensive")
        can_spend, reason = tracker_disabled.can_spend(50.0)
        assert can_spend is True

    def test_remaining_is_unlimited_when_disabled(self, tracker_disabled):
        """get_remaining returns infinity-like value when disabled."""
        remaining = tracker_disabled.get_remaining()
        assert remaining == float("inf")

    def test_status_shows_disabled(self, tracker_disabled):
        """get_status indicates budget tracking is disabled."""
        status = tracker_disabled.get_status()
        assert status["budget_disabled"] is True
        assert status["remaining"] == float("inf")
        assert status["cycles_affordable"] == -1  # unlimited

    def test_record_spend_still_works_when_disabled(self, tracker_disabled):
        """Spend is still recorded for auditing even when disabled."""
        tracker_disabled.record_spend(0.50, "op_test")
        assert tracker_disabled.get_today_spend() == 0.50


class TestExistingBudgetBehaviorPreserved:
    """Verify non-zero limits still enforce budgets."""

    @pytest.fixture
    def tracker(self, tmp_path):
        from ktrdr.agents.budget import BudgetTracker

        budget_dir = tmp_path / "budget"
        budget_dir.mkdir()
        return BudgetTracker(daily_limit=5.0, data_dir=str(budget_dir))

    def test_can_spend_false_when_exhausted(self, tracker):
        """Budget enforcement still works with non-zero limit."""
        tracker.record_spend(4.90, "op_big")
        can_spend, reason = tracker.can_spend(0.15)
        assert can_spend is False

    def test_status_not_disabled(self, tracker):
        """Status does not show disabled for non-zero limits."""
        status = tracker.get_status()
        assert status.get("budget_disabled") is False
