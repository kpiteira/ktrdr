"""Outer loop — runs one ORIENT → WORK → LEARN cycle.

The Director is a Claude Code session with both native tools (Read, Write,
Bash, etc.) and squad-specific MCP tools (spawn_agent, validate_strategy,
execute_experiment, cycle_complete). It reads KB files directly with native
tools during ORIENT, and delegates work to Engineer/Scribe via spawn_agent.

Python provides tool implementations but makes no routing decisions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from ktrdr import get_logger
from ktrdr.agents.runtime.protocol import AgentResult
from squad_engine.agent_manager import AgentManager
from squad_engine.context import ContextLoader
from squad_engine.director_prompt import build_director_prompt
from squad_engine.squad_tools import CycleState, create_squad_mcp_server

logger = get_logger(__name__)


@dataclass
class CycleResult:
    """Structured output from a completed cycle."""

    iteration: int
    status: str = "COMPLETE"  # COMPLETE | FAILED | ABORTED
    total_cost_usd: float = 0.0
    agents_spawned: list[str] = field(default_factory=list)
    experiment_result: dict | None = None
    cadence_next: str = "full_squad"
    error: str | None = None
    duration_seconds: float = 0.0


async def run_cycle(
    iteration: int,
    shared_dir: str | None = None,
    charter_dir: str | None = None,
    _agent_manager: AgentManager | None = None,
    _director_response: AgentResult | None = None,
) -> CycleResult:
    """Run one complete ORIENT → WORK → LEARN cycle.

    The Director is an LLM session with native Claude Code tools AND
    squad-specific MCP tools. It reads KB with Read, delegates to
    Engineer/Scribe via spawn_agent, validates with validate_strategy,
    and executes with execute_experiment.

    The _agent_manager and _director_response params are for testing.
    """
    start_time = time.time()

    # Set up infrastructure
    context_loader = ContextLoader(shared_dir=shared_dir)
    charter_base = Path(charter_dir) if charter_dir else (
        Path(__file__).resolve().parent.parent / "agents"
    )

    agent_manager = _agent_manager or AgentManager(
        context_loader=context_loader,
        charter_dir=charter_base,
        allowed_roles={"engineer", "scribe"},  # M1: only these two
    )

    # Read cycle context — default to full_squad if missing
    cadence = "full_squad"
    cadence_content = context_loader.load_file("loop/cadence.md").strip()
    if cadence_content and "cadence:" in cadence_content:
        parsed = cadence_content.split("cadence:")[1].strip().split("\n")[0].strip()
        if parsed:
            cadence = parsed

    nudges = context_loader.load_file("loop/nudges.md")

    # Build Director prompt
    director_charter = charter_base / "director" / "charter.md"
    director_prompt = build_director_prompt(
        charter_path=director_charter,
        iteration=iteration,
        cadence=cadence,
        nudges=nudges,
    )

    result = CycleResult(iteration=iteration)

    try:
        if _director_response is not None:
            # Test mode: use provided response
            result.total_cost_usd = _director_response.cost_usd
        else:
            # Production mode: run Director with squad MCP tools
            await _run_director_session(
                director_prompt, agent_manager, context_loader, result,
                charter_base=charter_base,
            )

    except Exception as e:
        logger.exception("Cycle %d failed", iteration)
        result.status = "FAILED"
        result.error = str(e)
    finally:
        # Always tear down agent sessions
        await agent_manager.teardown_all()
        # Add agent costs to Director cost
        result.total_cost_usd += agent_manager.total_cost_usd
        result.duration_seconds = time.time() - start_time

    logger.info(
        "Cycle %d %s (cost=$%.4f, duration=%.1fs, agents=%s)",
        iteration,
        result.status,
        result.total_cost_usd,
        result.duration_seconds,
        result.agents_spawned,
    )
    return result


async def _run_director_session(
    prompt: str,
    agent_manager: AgentManager,
    context_loader: ContextLoader,
    result: CycleResult,
    charter_base: Path | None = None,
) -> None:
    """Run the Director as a Claude Code session with squad MCP tools.

    The Director has:
    - Native Claude Code tools (Read, Write, Bash, Glob, Grep, Edit)
    - Squad MCP tools (spawn_agent, validate_strategy, execute_experiment, cycle_complete)

    It uses native tools to read KB during ORIENT and write cadence/frontiers.
    It uses squad tools to delegate to Engineer/Scribe and run experiments.

    The SDK handles tool dispatch natively — no JSON parsing needed.
    """
    from squad_engine.session import PersistentAgentSession

    # Create mutable cycle state that squad tools update
    cycle_state = CycleState()

    # Create MCP server with squad tools
    squad_mcp = create_squad_mcp_server(
        agent_manager=agent_manager,
        cycle_state=cycle_state,
    )

    charter_dir = charter_base or Path(__file__).resolve().parent.parent / "agents"
    director_charter = charter_dir / "director" / "charter.md"
    director = PersistentAgentSession(
        role="director",
        charter_path=director_charter,
        mcp_servers={"squad": squad_mcp},
    )

    try:
        await director.start()

        # Send the assembled prompt — the Director runs autonomously,
        # calling native tools and squad MCP tools as it sees fit.
        # The SDK dispatches tool calls; we just wait for completion.
        await director.query(prompt)

        # Transfer cycle state to result
        result.agents_spawned = cycle_state.agents_spawned
        result.experiment_result = cycle_state.experiment_result
        result.cadence_next = cycle_state.cadence_next

        if cycle_state.cycle_complete:
            result.status = "COMPLETE"
        else:
            logger.warning(
                "Director session ended without calling cycle_complete"
            )
            result.status = "FAILED"
            result.error = "Director did not signal cycle_complete"

    finally:
        await director.stop()
        result.total_cost_usd += director.total_cost_usd
