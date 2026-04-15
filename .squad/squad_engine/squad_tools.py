"""Squad MCP tools — registered as native tools the Director can call.

These are the squad-specific tools that the Director uses alongside
its standard Claude Code tools (Read, Write, Bash, etc.). Registered
via create_sdk_mcp_server and passed to the Director's session options.

The Director uses native tools to read KB files directly, and these
squad tools to orchestrate agents and execute experiments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ktrdr import get_logger

logger = get_logger(__name__)


@dataclass
class ConversationEntry:
    """One exchange in the Director's conversation with an agent."""

    role: str
    message_to_agent: str
    agent_response: str
    cost_usd: float = 0.0
    turns: int = 0


MAX_DEBATE_TURNS = 5


@dataclass
class CycleState:
    """Mutable state shared across tool calls within a single cycle.

    Passed to each tool handler via closure. Tracks what happened
    during the cycle for CycleResult construction.
    """

    agents_spawned: list[str] = field(default_factory=list)
    experiment_result: dict | None = None
    cadence_next: str = "full_squad"
    cycle_complete: bool = False
    conversation_log: list[ConversationEntry] = field(default_factory=list)
    debate_pairs: dict[tuple[str, str], int] = field(default_factory=dict)
    debates: list[dict] = field(default_factory=list)
    last_spawned_role: str | None = None

    def _pair_key(self, role_a: str, role_b: str) -> tuple[str, str]:
        """Sorted pair key so (A,B) == (B,A)."""
        return tuple(sorted([role_a, role_b]))

    def record_debate_turn(self, role_a: str, role_b: str) -> None:
        """Record one turn in a debate between two roles."""
        key = self._pair_key(role_a, role_b)
        self.debate_pairs[key] = self.debate_pairs.get(key, 0) + 1

    def is_debate_limit_reached(self, role_a: str, role_b: str) -> bool:
        """Check if this debate pair has hit the 5-turn maximum."""
        key = self._pair_key(role_a, role_b)
        return self.debate_pairs.get(key, 0) >= MAX_DEBATE_TURNS

    def record_debate(
        self,
        roles: list[str],
        turns: int,
        revised: bool,
        resolution: str,
    ) -> None:
        """Record structured metadata for a completed debate."""
        self.debates.append({
            "roles": roles,
            "turns": turns,
            "revised": revised,
            "resolution": resolution,
        })


def create_squad_mcp_server(
    agent_manager: Any,
    cycle_state: CycleState,
    transcript_logger: Any | None = None,
):
    """Create an MCP server with squad tools for the Director.

    Returns an McpSdkServerConfig that can be passed to
    ClaudeAgentOptions.mcp_servers.
    """
    from squad_engine.session import _get_sdk
    from squad_engine.tools import execute_experiment, validate_strategy

    sdk = _get_sdk()

    # --- spawn_agent tool ---

    @sdk.tool(
        name="spawn_agent",
        description=(
            "Start a conversation with a squad agent or send a follow-up message. "
            "First call for a role creates a new session with the agent's charter and history. "
            "Subsequent calls continue the conversation (multi-turn). "
            "Available roles: engineer (designs strategies, writes YAML, evaluates results), "
            "quant (cost/profitability analysis), inventor (divergent thinking, structural novelty), "
            "scout (external research, literature), critic (statistical rigor, adversarial challenge), "
            "architect (feasibility, capability gaps), scribe (records results to knowledge base). "
            "Returns the agent's response text."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["engineer", "quant", "inventor", "scout", "critic", "architect", "scribe"],
                    "description": "Which agent to spawn or message",
                },
                "message": {
                    "type": "string",
                    "description": "What to tell the agent",
                },
                "context": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "KB file paths to load as context (e.g. 'knowledge/synthesis.md'). "
                        "Only used on first spawn for a role."
                    ),
                },
            },
            "required": ["role", "message"],
        },
    )
    async def spawn_agent_tool(input: dict) -> dict[str, Any]:
        role = input["role"]
        message = input["message"]
        context = input.get("context")

        logger.info("Director spawning %s: %s", role, message[:100])

        # Track debate turns between consecutive different roles
        prev = cycle_state.last_spawned_role
        if prev and prev != role:
            # Check limit before spawning
            if cycle_state.is_debate_limit_reached(prev, role):
                logger.info(
                    "Debate limit reached for %s ↔ %s (5 turns). Returning limit message.",
                    prev, role,
                )
                cycle_state.last_spawned_role = role
                return {
                    "output": (
                        f"Debate between {prev} and {role} reached the 5-turn limit. "
                        "Please resolve the discussion and proceed."
                    ),
                    "cost_usd": 0.0,
                    "turns": 0,
                }
            cycle_state.record_debate_turn(prev, role)

        cycle_state.last_spawned_role = role

        result = await agent_manager.spawn_agent(role, message, context)

        if role not in cycle_state.agents_spawned:
            cycle_state.agents_spawned.append(role)

        # Record the full exchange for conversation review
        cycle_state.conversation_log.append(ConversationEntry(
            role=role,
            message_to_agent=message,
            agent_response=result.output,
            cost_usd=result.cost_usd,
            turns=result.turns,
        ))

        output = {
            "output": result.output,
            "cost_usd": result.cost_usd,
            "turns": result.turns,
        }
        if transcript_logger:
            transcript_logger.log_tool_call(
                "spawn_agent", {"role": role, "message": message[:200]}, output
            )
        return output

    # --- validate_strategy tool ---

    @sdk.tool(
        name="validate_strategy",
        description=(
            "Validate a strategy YAML file. Runs 'ktrdr validate' on the strategy. "
            "Returns whether the strategy is valid and any error message. "
            "Call this after the Engineer writes a strategy YAML. "
            "If invalid, send the error to the Engineer to fix."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Strategy name (without .yaml extension)",
                },
            },
            "required": ["name"],
        },
    )
    async def validate_strategy_tool(input: dict) -> dict[str, Any]:
        name = input["name"]
        logger.info("Director validating strategy: %s", name)

        result = await validate_strategy(name)
        output = {"valid": result.valid, "error": result.error}
        if transcript_logger:
            transcript_logger.log_tool_call("validate_strategy", {"name": name}, output)
        return output

    # --- execute_experiment tool ---

    @sdk.tool(
        name="execute_experiment",
        description=(
            "Run training + backtest for a strategy via executor.sh. "
            "This is long-running (minutes to hours). Returns training metrics "
            "and backtest results. Call this after the strategy validates."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "description": "Strategy name",
                },
                "train_start": {
                    "type": "string",
                    "description": "Training start date (YYYY-MM-DD)",
                    "default": "2015-01-01",
                },
                "train_end": {
                    "type": "string",
                    "description": "Training end date (YYYY-MM-DD)",
                    "default": "2020-12-31",
                },
                "bt_start": {
                    "type": "string",
                    "description": "Backtest start date (YYYY-MM-DD)",
                    "default": "2021-01-01",
                },
                "bt_end": {
                    "type": "string",
                    "description": "Backtest end date (YYYY-MM-DD)",
                    "default": "2025-01-01",
                },
            },
            "required": ["strategy"],
        },
    )
    async def execute_experiment_tool(input: dict) -> dict[str, Any]:
        strategy = input["strategy"]
        logger.info("Director executing experiment: %s", strategy)

        result = await execute_experiment(
            strategy=strategy,
            train_start=input.get("train_start", "2015-01-01"),
            train_end=input.get("train_end", "2020-12-31"),
            bt_start=input.get("bt_start", "2021-01-01"),
            bt_end=input.get("bt_end", "2025-01-01"),
        )

        cycle_state.experiment_result = {
            "status": result.status,
            "training": result.training,
            "backtest": result.backtest,
            "error": result.error,
        }
        if transcript_logger:
            transcript_logger.log_tool_call(
                "execute_experiment", {"strategy": strategy}, cycle_state.experiment_result
            )
        return cycle_state.experiment_result

    # --- cycle_complete tool ---

    @sdk.tool(
        name="cycle_complete",
        description=(
            "Signal that the cycle is done. Call this after the Scribe has "
            "recorded results. Set the cadence for the next cycle."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "cadence": {
                    "type": "string",
                    "enum": ["full_squad", "quick_iteration", "synthesis", "pause"],
                    "description": "Cadence mode for the next cycle",
                },
                "reason": {
                    "type": "string",
                    "description": "One-line reason for the cadence choice",
                },
            },
            "required": ["cadence", "reason"],
        },
    )
    async def cycle_complete_tool(input: dict) -> dict[str, Any]:
        cycle_state.cadence_next = input["cadence"]
        cycle_state.cycle_complete = True
        logger.info(
            "Cycle complete — next cadence: %s (%s)",
            input["cadence"],
            input.get("reason", ""),
        )
        output = {"status": "complete", "next_cadence": input["cadence"]}
        if transcript_logger:
            transcript_logger.log_tool_call("cycle_complete", input, output)
        return output

    # Bundle into MCP server
    return sdk.create_sdk_mcp_server(
        name="squad",
        version="2.0.0",
        tools=[
            spawn_agent_tool,
            validate_strategy_tool,
            execute_experiment_tool,
            cycle_complete_tool,
        ],
    )
