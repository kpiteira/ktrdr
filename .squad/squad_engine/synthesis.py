"""Synthesis triggering and cycle execution.

Three trigger paths:
1. Director sets cadence to 'synthesis' (explicit request)
2. Emergency: context > 80% of 200K budget
3. Periodic: every N cycles (configurable, default 10)

Synthesis cycle: Scribe only, produces updated synthesis.md.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from ktrdr import get_logger
from squad_engine.context import CONTEXT_BUDGET_TOKENS, EMERGENCY_THRESHOLD

if TYPE_CHECKING:
    from squad_engine.loop import CycleResult

logger = get_logger(__name__)


def should_trigger_synthesis(
    cadence: str,
    context_tokens: int,
    iteration: int,
    synthesis_interval: int = 10,
) -> bool:
    """Check if synthesis should be triggered.

    Returns True if any of the three trigger paths fires:
    1. cadence == 'synthesis'
    2. context_tokens > 80% of budget (emergency)
    3. iteration is a multiple of synthesis_interval (periodic)
    """
    # pause should never trigger synthesis
    if cadence == "pause":
        return False

    # Path 1: Director explicit request
    if cadence == "synthesis":
        return True

    # Path 2: Emergency context budget
    threshold = int(CONTEXT_BUDGET_TOKENS * EMERGENCY_THRESHOLD)
    if context_tokens > threshold:
        logger.warning(
            "Emergency synthesis: %d tokens > %d threshold",
            context_tokens,
            threshold,
        )
        return True

    # Path 3: Periodic interval
    if iteration > 0 and iteration % synthesis_interval == 0:
        logger.info("Periodic synthesis at iteration %d", iteration)
        return True

    return False


async def run_synthesis_cycle(
    iteration: int,
    shared_dir: str | None = None,
    charter_dir: str | None = None,
) -> CycleResult:
    """Run a synthesis cycle — Scribe produces updated synthesis.md.

    Unlike research cycles, this spawns only the Scribe with the full
    experiments.md history. No Engineer, no consultants, no experiment execution.
    """
    from squad_engine.loop import CycleResult

    start_time = time.time()
    shared_path = Path(shared_dir) if shared_dir else None

    experiments_content = ""
    if shared_path:
        experiments_file = shared_path / "knowledge" / "experiments.md"
        if experiments_file.exists():
            experiments_content = experiments_file.read_text()

    try:
        synthesis_output = await _run_scribe_session(
            experiments_content=experiments_content,
            charter_dir=charter_dir,
        )

        # Write updated synthesis.md
        if shared_path:
            synthesis_file = shared_path / "knowledge" / "synthesis.md"
            synthesis_file.parent.mkdir(parents=True, exist_ok=True)
            synthesis_file.write_text(synthesis_output)

        return CycleResult(
            iteration=iteration,
            status="COMPLETE",
            agents_spawned=["scribe"],
            cadence_next="full_squad",  # Reset — prevent synthesis loop
            duration_seconds=time.time() - start_time,
        )

    except Exception as e:
        logger.exception("Synthesis cycle %d failed", iteration)
        return CycleResult(
            iteration=iteration,
            status="FAILED",
            error=str(e),
            cadence_next="full_squad",
            duration_seconds=time.time() - start_time,
        )


async def _run_scribe_session(
    experiments_content: str,
    charter_dir: str | None = None,
) -> str:
    """Run Scribe to produce synthesis.md from experiments.

    In production, this creates a PersistentAgentSession for the Scribe.
    Returns the synthesis text.
    """
    from squad_engine.session import PersistentAgentSession

    charter_base = Path(charter_dir) if charter_dir else (
        Path(__file__).resolve().parent.parent / "agents"
    )
    scribe_charter = charter_base / "scribe" / "charter.md"

    scribe = PersistentAgentSession(role="scribe", charter_path=scribe_charter)

    try:
        await scribe.start()
        prompt = (
            "Synthesize the following experiment history into a concise summary "
            "of patterns, best results, and open questions. Write this as an "
            "updated synthesis.md.\n\n"
            f"## Experiment History\n\n{experiments_content}"
        )
        result = await scribe.query(prompt)
        return result.output
    finally:
        await scribe.stop()
