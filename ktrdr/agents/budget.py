"""Budget tracking for agent operations.

Tracks daily spend for Claude API calls and enforces budget limits.
Budget is stored in a JSON file per day to survive restarts.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ktrdr import get_logger

logger = get_logger(__name__)


class BudgetTracker:
    """Tracks and enforces daily budget for agent operations.

    Budget is stored in a JSON file per day:
    - data/budget/2025-12-13.json

    Each file contains:
    {
        "date": "2025-12-13",
        "limit": 5.00,
        "spend": [
            {"amount": 0.065, "operation_id": "op_...", "timestamp": "..."},
            ...
        ],
        "total_spend": 0.15
    }
    """

    def __init__(
        self,
        daily_limit: float | None = None,
        data_dir: str | None = None,
    ):
        """Initialize the budget tracker.

        Args:
            daily_limit: Daily budget limit in dollars. Defaults to
                KTRDR_AGENT_DAILY_BUDGET env var or $5.00.
            data_dir: Directory for budget files. Defaults to KTRDR_AGENT_BUDGET_DIR
                env var or "data/budget".
        """
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        self.daily_limit = daily_limit or settings.daily_budget
        resolved_dir = data_dir if data_dir else settings.budget_dir
        self.data_dir = Path(resolved_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_today_file(self) -> Path:
        """Get path to today's budget file."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.data_dir / f"{today}.json"

    def _load_today(self) -> dict[str, Any]:
        """Load today's budget data."""
        path = self._get_today_file()
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "limit": self.daily_limit,
            "spend": [],
            "total_spend": 0.0,
        }

    def _save_today(self, data: dict[str, Any]) -> None:
        """Save today's budget data."""
        path = self._get_today_file()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_today_spend(self) -> float:
        """Get total spend for today.

        Returns:
            Total spend in dollars for the current day.
        """
        data = self._load_today()
        return data.get("total_spend", 0.0)

    def get_remaining(self) -> float:
        """Get remaining budget for today.

        Returns:
            Remaining budget in dollars (never negative).
        """
        return max(0, self.daily_limit - self.get_today_spend())

    def can_spend(self, estimated_amount: float = 0.15) -> tuple[bool, str]:
        """Check if we can afford estimated spend.

        Args:
            estimated_amount: Estimated cost in dollars. Defaults to $0.15 per cycle.

        Returns:
            Tuple of (can_spend, reason). reason is "ok" if can spend,
            otherwise describes why budget is exhausted.
        """
        remaining = self.get_remaining()
        if remaining < estimated_amount:
            return (
                False,
                f"budget_exhausted (${remaining:.2f} remaining, need ${estimated_amount:.2f})",
            )
        return True, "ok"

    def record_spend(self, amount: float, operation_id: str) -> None:
        """Record a spend event.

        Args:
            amount: Amount spent in dollars.
            operation_id: Operation that incurred the spend.
        """
        data = self._load_today()
        data["spend"].append(
            {
                "amount": amount,
                "operation_id": operation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        data["total_spend"] = sum(s["amount"] for s in data["spend"])
        self._save_today(data)

        remaining = self.daily_limit - data["total_spend"]
        logger.info(
            f"Budget spend recorded: ${amount:.2f} for {operation_id} "
            f"(total: ${data['total_spend']:.2f}, remaining: ${remaining:.2f})"
        )

    def get_status(self) -> dict[str, Any]:
        """Get full budget status.

        Returns:
            Dict with limit, spend, remaining, cycle estimates.
        """
        data = self._load_today()
        total_spend = data.get("total_spend", 0.0)
        remaining = max(0, self.daily_limit - total_spend)
        cycles_affordable = int(remaining / 0.15) if remaining > 0 else 0

        return {
            "date": data.get("date"),
            "daily_limit": self.daily_limit,
            "today_spend": total_spend,
            "remaining": remaining,
            "cycles_affordable": cycles_affordable,
            "spend_events": len(data.get("spend", [])),
        }


# Singleton instance
_budget_tracker: BudgetTracker | None = None


def get_budget_tracker() -> BudgetTracker:
    """Get the budget tracker singleton.

    Returns:
        The shared BudgetTracker instance.
    """
    global _budget_tracker
    if _budget_tracker is None:
        _budget_tracker = BudgetTracker()
    return _budget_tracker
