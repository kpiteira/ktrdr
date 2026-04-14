"""Stall detection, de-duplication, and cycle history.

Detects when the squad is stuck (3 consecutive non-productive cycles)
and provides advisory warnings for repeated experiments.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ktrdr import get_logger

logger = get_logger(__name__)


def is_productive_cycle(cycle_result) -> bool:
    """Check if a cycle produced meaningful output.

    A cycle is productive if it completed successfully AND
    produced an experiment result.
    """
    if cycle_result.status != "COMPLETE":
        return False
    if cycle_result.experiment_result is None:
        return False
    return True


class StallDetector:
    """Track consecutive non-productive cycles.

    Triggers stall after max_non_productive consecutive non-productive cycles.
    A productive cycle resets the counter.
    """

    def __init__(self, max_non_productive: int = 3) -> None:
        self._max = max_non_productive
        self._consecutive = 0

    @property
    def consecutive_non_productive(self) -> int:
        return self._consecutive

    def check_stall(self, productive: bool) -> bool:
        """Update counter and return True if stall threshold reached."""
        if productive:
            self._consecutive = 0
            return False

        self._consecutive += 1
        if self._consecutive >= self._max:
            logger.warning(
                "Stall detected: %d consecutive non-productive cycles",
                self._consecutive,
            )
            return True
        return False


def write_fatal_error(shared_dir: Path | str, reason: str) -> None:
    """Write fatal-error.md with diagnostic information."""
    fatal_file = Path(shared_dir) / "loop" / "fatal-error.md"
    fatal_file.parent.mkdir(parents=True, exist_ok=True)
    fatal_file.write_text(
        f"# Fatal Error — Loop Stopped\n\n"
        f"**Reason:** {reason}\n\n"
        f"The squad loop has been stopped. Review the cycle history "
        f"and experiments.md to diagnose the issue.\n"
    )
    logger.error("Fatal error written: %s", reason)


def check_deduplication(strategy_name: str, experiments_content: str) -> str | None:
    """Check if a strategy name was already used in experiments.

    Returns a warning string if duplicate found, None otherwise.
    This is advisory — it warns but doesn't block.
    """
    if strategy_name in experiments_content:
        return (
            f"Strategy '{strategy_name}' appears in previous experiments. "
            f"Consider renaming or confirming you want to re-run."
        )
    return None


# ---------------------------------------------------------------------------
# Cycle History
# ---------------------------------------------------------------------------


@dataclass
class CycleHistoryEntry:
    """One entry in the cycle history log."""

    iteration: int
    status: str
    experiment: str | None
    agents_spawned: list[str]
    cost_usd: float
    timestamp: str


def read_cycle_history(shared_dir: Path | str) -> list[dict]:
    """Read cycle history from {shared_dir}/loop/cycle-history.json."""
    history_file = Path(shared_dir) / "loop" / "cycle-history.json"
    if not history_file.exists():
        return []

    try:
        return json.loads(history_file.read_text())
    except (json.JSONDecodeError, ValueError):
        logger.warning("Corrupt cycle history, returning empty")
        return []


def write_cycle_history_entry(shared_dir: Path | str, entry: CycleHistoryEntry) -> None:
    """Append an entry to {shared_dir}/loop/cycle-history.json."""
    history = read_cycle_history(shared_dir)
    history.append(asdict(entry))

    history_file = Path(shared_dir) / "loop" / "cycle-history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(history, indent=2))
