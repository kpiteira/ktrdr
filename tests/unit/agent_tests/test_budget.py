"""
Unit tests for budget tracking.

Tests cover:
- Spend tracking per day
- New day resets spend
- can_spend returns False when exhausted
- record_spend updates total
- Persistence to file
- Configurable daily limit via AGENT_DAILY_BUDGET env
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


class TestBudgetTracker:
    """Tests for BudgetTracker class."""

    @pytest.fixture
    def temp_budget_dir(self, tmp_path):
        """Create a temporary directory for budget files."""
        budget_dir = tmp_path / "budget"
        budget_dir.mkdir()
        return budget_dir

    @pytest.fixture
    def tracker(self, temp_budget_dir):
        """Create a BudgetTracker with temporary directory."""
        from ktrdr.agents.budget import BudgetTracker

        return BudgetTracker(daily_limit=5.0, data_dir=str(temp_budget_dir))

    # === Basic Functionality ===

    def test_default_daily_limit(self, temp_budget_dir):
        """Test default daily limit is $5.00."""
        from ktrdr.agents.budget import BudgetTracker

        tracker = BudgetTracker(data_dir=str(temp_budget_dir))
        assert tracker.daily_limit == 5.0

    def test_custom_daily_limit(self, temp_budget_dir):
        """Test custom daily limit is respected."""
        from ktrdr.agents.budget import BudgetTracker

        tracker = BudgetTracker(daily_limit=10.0, data_dir=str(temp_budget_dir))
        assert tracker.daily_limit == 10.0

    def test_daily_limit_from_env(self, temp_budget_dir):
        """Test daily limit from AGENT_DAILY_BUDGET env var."""
        from ktrdr.agents.budget import BudgetTracker

        with patch.dict(os.environ, {"AGENT_DAILY_BUDGET": "7.50"}):
            tracker = BudgetTracker(data_dir=str(temp_budget_dir))
            assert tracker.daily_limit == 7.50

    # === Spend Tracking ===

    def test_initial_spend_is_zero(self, tracker):
        """Test that initial spend is zero."""
        assert tracker.get_today_spend() == 0.0

    def test_record_spend_updates_total(self, tracker):
        """Test that record_spend updates the total."""
        tracker.record_spend(0.10, "op_test_1")
        assert tracker.get_today_spend() == 0.10

    def test_record_multiple_spends(self, tracker):
        """Test that multiple spends accumulate."""
        tracker.record_spend(0.10, "op_test_1")
        tracker.record_spend(0.15, "op_test_2")
        tracker.record_spend(0.05, "op_test_3")
        assert tracker.get_today_spend() == 0.30

    def test_get_remaining_budget(self, tracker):
        """Test remaining budget calculation."""
        assert tracker.get_remaining() == 5.0
        tracker.record_spend(1.50, "op_test_1")
        assert tracker.get_remaining() == 3.50

    def test_remaining_never_negative(self, tracker):
        """Test that remaining budget is never negative."""
        tracker.record_spend(10.0, "op_overspend")
        assert tracker.get_remaining() == 0.0

    # === can_spend Checks ===

    def test_can_spend_with_budget(self, tracker):
        """Test can_spend returns True when budget available."""
        can_spend, reason = tracker.can_spend(0.15)
        assert can_spend is True
        assert reason == "ok"

    def test_can_spend_when_exhausted(self, tracker):
        """Test can_spend returns False when budget exhausted."""
        tracker.record_spend(4.90, "op_big_spend")
        can_spend, reason = tracker.can_spend(0.15)
        assert can_spend is False
        assert "budget_exhausted" in reason

    def test_can_spend_exactly_remaining(self, tracker):
        """Test can_spend when request equals remaining."""
        tracker.record_spend(4.85, "op_spend")
        can_spend, reason = tracker.can_spend(0.15)
        assert can_spend is True

    def test_can_spend_just_over_remaining(self, tracker):
        """Test can_spend when request slightly exceeds remaining."""
        tracker.record_spend(4.86, "op_spend")
        can_spend, reason = tracker.can_spend(0.15)
        assert can_spend is False

    def test_can_spend_default_estimate(self, tracker):
        """Test can_spend with default estimate of $0.15."""
        tracker.record_spend(4.90, "op_spend")
        # Default estimate is 0.15, so should fail
        can_spend, reason = tracker.can_spend()
        assert can_spend is False

    # === Persistence ===

    def test_spend_persisted_to_file(self, tracker, temp_budget_dir):
        """Test that spend is persisted to file."""
        tracker.record_spend(0.25, "op_test")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        budget_file = temp_budget_dir / f"{today}.json"
        assert budget_file.exists()

        with open(budget_file) as f:
            data = json.load(f)
        assert data["total_spend"] == 0.25
        assert len(data["spend"]) == 1
        assert data["spend"][0]["amount"] == 0.25
        assert data["spend"][0]["operation_id"] == "op_test"

    def test_spend_survives_reload(self, temp_budget_dir):
        """Test that spend survives creating a new tracker instance."""
        from ktrdr.agents.budget import BudgetTracker

        # First tracker records spend
        tracker1 = BudgetTracker(daily_limit=5.0, data_dir=str(temp_budget_dir))
        tracker1.record_spend(0.30, "op_test_1")
        tracker1.record_spend(0.20, "op_test_2")

        # New tracker instance sees the same spend
        tracker2 = BudgetTracker(daily_limit=5.0, data_dir=str(temp_budget_dir))
        assert tracker2.get_today_spend() == 0.50

    def test_creates_data_dir_if_missing(self, tmp_path):
        """Test that data directory is created if it doesn't exist."""
        from ktrdr.agents.budget import BudgetTracker

        budget_dir = tmp_path / "new_budget_dir"
        assert not budget_dir.exists()

        tracker = BudgetTracker(daily_limit=5.0, data_dir=str(budget_dir))
        tracker.record_spend(0.10, "op_test")

        assert budget_dir.exists()

    # === New Day Reset ===

    def test_new_day_resets_spend(self, temp_budget_dir):
        """Test that spend resets on a new day."""
        from ktrdr.agents.budget import BudgetTracker

        # Create a file for yesterday
        yesterday = "2025-01-01"
        yesterday_file = temp_budget_dir / f"{yesterday}.json"
        with open(yesterday_file, "w") as f:
            json.dump(
                {
                    "date": yesterday,
                    "limit": 5.0,
                    "spend": [{"amount": 3.0, "operation_id": "op_old"}],
                    "total_spend": 3.0,
                },
                f,
            )

        # Today's tracker should have zero spend (different date)
        tracker = BudgetTracker(daily_limit=5.0, data_dir=str(temp_budget_dir))
        # Today is not 2025-01-01, so should be zero
        assert tracker.get_today_spend() == 0.0

    # === Status ===

    def test_get_status(self, tracker):
        """Test get_status returns comprehensive info."""
        tracker.record_spend(0.50, "op_test_1")
        tracker.record_spend(0.25, "op_test_2")

        status = tracker.get_status()

        assert status["daily_limit"] == 5.0
        assert status["today_spend"] == 0.75
        assert status["remaining"] == 4.25
        assert status["spend_events"] == 2
        assert "date" in status
        assert "cycles_affordable" in status

    def test_cycles_affordable_calculation(self, tracker):
        """Test cycles_affordable is calculated correctly."""
        # At $0.15 per cycle, $5 budget = 33 cycles
        status = tracker.get_status()
        assert status["cycles_affordable"] == 33

        tracker.record_spend(4.55, "op_big")
        status = tracker.get_status()
        # $0.45 remaining / $0.15 per cycle = 3 cycles
        assert status["cycles_affordable"] == 3


class TestBudgetTrackerSingleton:
    """Tests for budget tracker singleton."""

    def test_get_budget_tracker_returns_instance(self):
        """Test get_budget_tracker returns a BudgetTracker."""
        from ktrdr.agents.budget import get_budget_tracker

        tracker = get_budget_tracker()
        assert tracker is not None
        assert hasattr(tracker, "can_spend")
        assert hasattr(tracker, "record_spend")

    def test_get_budget_tracker_returns_same_instance(self):
        """Test singleton returns the same instance."""
        from ktrdr.agents.budget import get_budget_tracker

        tracker1 = get_budget_tracker()
        tracker2 = get_budget_tracker()
        assert tracker1 is tracker2
