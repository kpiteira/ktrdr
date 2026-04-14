"""Cadence and iteration state management for the squad loop.

Reads/writes cadence.md and iteration-count.txt in the shared directory.
File formats are compatible with v1's loop_runner.sh.
"""

from __future__ import annotations

from pathlib import Path

from ktrdr import get_logger

logger = get_logger(__name__)

VALID_CADENCES = {"full_squad", "quick_iteration", "synthesis", "pause"}
DEFAULT_CADENCE = "full_squad"


def read_cadence(shared_dir: Path | str) -> str:
    """Read cadence mode from {shared_dir}/loop/cadence.md.

    Returns DEFAULT_CADENCE if file missing or unparseable.
    Format: 'cadence: <mode>' (v1-compatible).
    """
    cadence_file = Path(shared_dir) / "loop" / "cadence.md"
    if not cadence_file.exists():
        return DEFAULT_CADENCE

    content = cadence_file.read_text().strip()
    if not content or "cadence:" not in content:
        return DEFAULT_CADENCE

    parsed = content.split("cadence:")[1].strip().split("\n")[0].strip()
    if parsed in VALID_CADENCES:
        return parsed

    logger.warning("Unknown cadence '%s', defaulting to %s", parsed, DEFAULT_CADENCE)
    return DEFAULT_CADENCE


def write_cadence(shared_dir: Path | str, cadence: str) -> None:
    """Write cadence mode to {shared_dir}/loop/cadence.md.

    Creates parent directories if needed.
    """
    cadence_file = Path(shared_dir) / "loop" / "cadence.md"
    cadence_file.parent.mkdir(parents=True, exist_ok=True)
    cadence_file.write_text(f"cadence: {cadence}\n")


def read_iteration_count(shared_dir: Path | str) -> int:
    """Read iteration counter from {shared_dir}/loop/iteration-count.txt.

    Returns 0 if file missing.
    """
    counter_file = Path(shared_dir) / "loop" / "iteration-count.txt"
    if not counter_file.exists():
        return 0

    content = counter_file.read_text().strip()
    try:
        return int(content)
    except ValueError:
        logger.warning("Invalid iteration count '%s', returning 0", content)
        return 0


def write_iteration_count(shared_dir: Path | str, count: int) -> None:
    """Write iteration counter to {shared_dir}/loop/iteration-count.txt."""
    counter_file = Path(shared_dir) / "loop" / "iteration-count.txt"
    counter_file.parent.mkdir(parents=True, exist_ok=True)
    counter_file.write_text(str(count))
