"""Outer loop — runs multiple cycles with cadence management.

Replaces loop_runner.sh (810 lines of shell) with a Python loop that
manages cadence, synthesis triggers, stall detection, and de-duplication.

Entry point: run_loop() or `python -m squad_engine.loop_runner`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ktrdr import get_logger
from squad_engine.cadence import (
    read_cadence,
    write_cadence,
    write_iteration_count,
)
from squad_engine.context import CHARS_PER_TOKEN
from squad_engine.loop import CycleResult, run_cycle
from squad_engine.stall import (
    CycleHistoryEntry,
    StallDetector,
    is_productive_cycle,
    write_cycle_history_entry,
    write_fatal_error,
)
from squad_engine.synthesis import (
    run_synthesis_cycle,
    should_trigger_synthesis,
)

logger = get_logger(__name__)


@dataclass
class LoopResult:
    """Structured output from a completed loop run."""

    iterations_run: int = 0
    experiments_completed: int = 0
    stall_detected: bool = False
    final_cadence: str = "full_squad"
    total_cost_usd: float = 0.0
    status: str = "completed"  # completed | paused | max_iterations | stalled | interrupted | error


async def run_loop(
    shared_dir: str | None = None,
    charter_dir: str | None = None,
    max_iterations: int = 20,
    synthesis_interval: int = 10,
) -> LoopResult:
    """Run the outer squad loop with cadence management.

    Reads cadence at the start of each iteration:
    - pause → exit with status=paused
    - synthesis → run synthesis cycle
    - full_squad / quick_iteration → run research cycle

    Also checks emergency and periodic synthesis triggers.
    Handles KeyboardInterrupt for clean shutdown.

    Returns LoopResult with aggregate stats.
    """
    shared_path = Path(shared_dir) if shared_dir else None
    result = LoopResult()
    stall_detector = StallDetector(max_non_productive=3)

    try:
        for iteration in range(1, max_iterations + 1):
            # 1. Read cadence
            cadence = read_cadence(shared_path) if shared_path else "full_squad"

            # Check for pause
            if cadence == "pause":
                result.status = "paused"
                result.final_cadence = "pause"
                logger.info("Loop paused at iteration %d", iteration)
                break

            # 2. Check synthesis triggers (emergency + periodic)
            context_tokens = _estimate_context_tokens(shared_path)
            needs_synthesis = should_trigger_synthesis(
                cadence=cadence,
                context_tokens=context_tokens,
                iteration=iteration,
                synthesis_interval=synthesis_interval,
            )

            # 3. Run appropriate cycle type
            if needs_synthesis:
                cycle_result = await run_synthesis_cycle(
                    iteration=iteration,
                    shared_dir=shared_dir,
                    charter_dir=charter_dir,
                )
            else:
                cycle_result = await run_cycle(
                    iteration=iteration,
                    shared_dir=shared_dir,
                    charter_dir=charter_dir,
                )

            # 4. Accumulate results
            result.iterations_run += 1
            result.total_cost_usd += cycle_result.total_cost_usd
            if cycle_result.experiment_result:
                result.experiments_completed += 1

            # 5. Write cycle history
            if shared_path:
                _write_history(shared_path, cycle_result)

            # 6. Check stall detection
            productive = is_productive_cycle(cycle_result)
            if stall_detector.check_stall(productive):
                reason = f"{stall_detector.consecutive_non_productive} consecutive non-productive cycles"
                if shared_path:
                    write_fatal_error(shared_path, reason)
                result.status = "stalled"
                result.stall_detected = True
                logger.warning("Loop stalled at iteration %d: %s", iteration, reason)
                break

            # 7. Write cadence from cycle result for next iteration
            if shared_path:
                write_cadence(shared_path, cycle_result.cadence_next)
                write_iteration_count(shared_path, iteration)

            result.final_cadence = cycle_result.cadence_next

            logger.info(
                "Iteration %d/%d complete (cadence_next=%s, cost=$%.4f)",
                iteration,
                max_iterations,
                cycle_result.cadence_next,
                cycle_result.total_cost_usd,
            )
        else:
            # Loop completed all iterations without break
            result.status = "max_iterations"

    except KeyboardInterrupt:
        logger.info("Loop interrupted by user after %d iterations", result.iterations_run)
        result.status = "interrupted"

    return result


def _estimate_context_tokens(shared_path: Path | None) -> int:
    """Estimate current context size from KB files."""
    if not shared_path:
        return 0

    experiments_file = shared_path / "knowledge" / "experiments.md"
    if not experiments_file.exists():
        return 0

    return len(experiments_file.read_text()) // CHARS_PER_TOKEN


def _write_history(shared_path: Path, cycle_result: CycleResult) -> None:
    """Write a cycle history entry from a CycleResult."""
    # Extract experiment name from result if available
    experiment_name = None
    if cycle_result.experiment_result and isinstance(cycle_result.experiment_result, dict):
        experiment_name = cycle_result.experiment_result.get("strategy") or "unnamed"

    entry = CycleHistoryEntry(
        iteration=cycle_result.iteration,
        status=cycle_result.status,
        experiment=experiment_name,
        agents_spawned=cycle_result.agents_spawned,
        cost_usd=cycle_result.total_cost_usd,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    write_cycle_history_entry(shared_path, entry)
