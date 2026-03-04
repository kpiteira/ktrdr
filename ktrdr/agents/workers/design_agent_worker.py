"""DesignAgentWorker — containerized design agent using Claude Code + MCP.

Receives a research brief, invokes Claude Code via AgentRuntime protocol,
and extracts the designed strategy from the SDK transcript. Follows the
same WorkerAPIBase contract as training and backtest workers.

Run via uvicorn:
    uvicorn ktrdr.agents.workers.design_agent_worker:app --host 0.0.0.0 --port 5010
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any

from pydantic import Field

from ktrdr.agents.runtime.protocol import AgentRuntime
from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.logging import get_logger
from ktrdr.workers.base import WorkerAPIBase, WorkerOperationMixin

logger = get_logger(__name__)

# Default configuration
DEFAULT_DESIGN_MAX_TURNS = 25
DEFAULT_DESIGN_MAX_BUDGET = 2.0
DEFAULT_DESIGN_MODEL = "claude-sonnet-4-6"

# MCP tool name for result extraction
SAVE_STRATEGY_TOOL = "mcp__ktrdr__save_strategy_config"

# Default allowed tools for design agent
DEFAULT_ALLOWED_TOOLS = [
    "mcp__ktrdr__*",  # All ktrdr MCP tools
    "Read",  # Filesystem read (strategies, memory)
    "Glob",  # Filesystem search
    "Grep",  # Content search
]


class DesignStartRequest(WorkerOperationMixin):
    """Request to start a design operation.

    Sent by backend's research orchestrator when dispatching design work.
    """

    brief: str = Field(..., description="Research brief describing what to design")
    symbol: str = Field(..., description="Target symbol (e.g., EURUSD)")
    timeframe: str = Field(..., description="Primary timeframe (e.g., 1h)")
    experiment_context: str | None = Field(
        default=None,
        description="Summary of past experiments for context",
    )


class DesignAgentWorker(WorkerAPIBase):
    """Design agent worker using Claude Code + MCP via AgentRuntime.

    Accepts research briefs, runs Claude Code to design strategies,
    and reports results via the operations service.
    """

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        worker_port: int = 5010,
        backend_url: str = "http://backend:8000",
        model: str = DEFAULT_DESIGN_MODEL,
        max_turns: int = DEFAULT_DESIGN_MAX_TURNS,
        max_budget_usd: float = DEFAULT_DESIGN_MAX_BUDGET,
    ) -> None:
        super().__init__(
            worker_type=WorkerType.AGENT_DESIGN,
            operation_type=OperationType.AGENT_DESIGN,
            worker_port=worker_port,
            backend_url=backend_url,
        )
        self._runtime = runtime
        self._model = model
        self._max_turns = max_turns
        self._max_budget_usd = max_budget_usd
        self._mcp_backend_url = os.environ.get(
            "KTRDR_MCP_BACKEND_URL", "http://backend:8000/api/v1"
        )

        # Register the design-specific start endpoint
        @self.app.post("/designs/start")
        async def start_design(request: DesignStartRequest):
            """Start a design operation.

            Accepts a research brief, creates an operation, and launches
            Claude Code in the background.
            """
            operation_id = request.task_id or f"worker_design_{uuid.uuid4().hex[:12]}"

            asyncio.create_task(
                self._execute_design_work(
                    operation_id=operation_id,
                    brief=request.brief,
                    symbol=request.symbol,
                    timeframe=request.timeframe,
                    experiment_context=request.experiment_context,
                )
            )

            return {
                "success": True,
                "operation_id": operation_id,
                "status": "started",
            }

    def _build_user_prompt(
        self,
        brief: str,
        symbol: str,
        timeframe: str,
        experiment_context: str | None,
    ) -> str:
        """Build the user prompt from brief and context.

        The system prompt is static (defines role/workflow). The user prompt
        carries the research brief and experiment context.
        """
        parts = [
            f"## Research Brief\n\n{brief}",
            f"\n## Target\n\nSymbol: {symbol}\nTimeframe: {timeframe}",
        ]
        if experiment_context:
            parts.append(f"\n## Experiment Context\n\n{experiment_context}")
        return "\n".join(parts)

    def _get_mcp_servers(self) -> dict[str, Any]:
        """Build MCP server config for Claude Code invocation."""
        return {
            "ktrdr": {
                "command": "bash",
                "args": ["-c", "cd /mcp && python -m src.main"],
                "env": {
                    "KTRDR_API_URL": self._mcp_backend_url,
                    "LOG_LEVEL": "WARNING",
                },
            }
        }

    def extract_strategy_from_transcript(
        self, transcript: list[dict]
    ) -> dict[str, Any] | None:
        """Extract strategy info from the last save_strategy_config tool call.

        Scans the transcript for tool_use entries matching save_strategy_config.
        Uses the last occurrence (the agent may iterate and save multiple times,
        the final save is the definitive one).

        Returns:
            Dict with strategy_name and strategy_path, or None if not found.
        """
        last_save: dict[str, Any] | None = None

        for i, entry in enumerate(transcript):
            if (
                entry.get("type") == "tool_use"
                and entry.get("tool") == SAVE_STRATEGY_TOOL
            ):
                # Look for the corresponding tool_result to get the output
                tool_input = entry.get("input", {})
                strategy_name = tool_input.get("strategy_name")

                # Check if there's a tool_result following this entry
                strategy_path = None
                for j in range(i + 1, len(transcript)):
                    result_entry = transcript[j]
                    if result_entry.get("type") == "tool_result" and result_entry.get(
                        "tool_use_id"
                    ) == entry.get("id"):
                        # Parse the result content for path info
                        content = result_entry.get("content", "")
                        if isinstance(content, str):
                            try:
                                parsed = json.loads(content)
                                strategy_name = parsed.get(
                                    "strategy_name", strategy_name
                                )
                                strategy_path = parsed.get("strategy_path")
                            except (json.JSONDecodeError, TypeError):
                                pass
                        break

                if strategy_name:
                    last_save = {
                        "strategy_name": strategy_name,
                        "strategy_path": strategy_path,
                    }

        return last_save

    async def _execute_design_work(
        self,
        operation_id: str,
        brief: str,
        symbol: str,
        timeframe: str,
        experiment_context: str | None,
    ) -> None:
        """Execute design work in the background.

        Invokes AgentRuntime with the design prompt and MCP config,
        extracts strategy info from the transcript, and reports completion.
        """
        ops = self.get_operations_service()

        try:
            # Import system prompt (deferred to avoid circular imports during testing)
            from ktrdr.agents.design_sdk_prompt import DESIGN_SYSTEM_PROMPT

            user_prompt = self._build_user_prompt(
                brief=brief,
                symbol=symbol,
                timeframe=timeframe,
                experiment_context=experiment_context,
            )

            logger.info(
                "Starting design agent for operation %s (symbol=%s, tf=%s)",
                operation_id,
                symbol,
                timeframe,
            )

            result = await self._runtime.invoke(
                user_prompt,
                model=self._model,
                max_turns=self._max_turns,
                max_budget_usd=self._max_budget_usd,
                allowed_tools=DEFAULT_ALLOWED_TOOLS,
                cwd="/app",
                system_prompt=DESIGN_SYSTEM_PROMPT,
                mcp_servers=self._get_mcp_servers(),
            )

            # Extract strategy from transcript
            strategy_info = self.extract_strategy_from_transcript(result.transcript)

            if strategy_info is None:
                await ops.fail_operation(
                    operation_id=operation_id,
                    error_message=(
                        "Design agent did not call save_strategy_config MCP tool. "
                        "No strategy was produced."
                    ),
                )
                logger.warning(
                    "Design agent %s produced no strategy (turns=%d, cost=$%.2f)",
                    operation_id,
                    result.turns,
                    result.cost_usd,
                )
                return

            await ops.complete_operation(
                operation_id=operation_id,
                result_summary={
                    "strategy_name": strategy_info["strategy_name"],
                    "strategy_path": strategy_info.get("strategy_path"),
                    "input_tokens": 0,  # SDK doesn't expose per-message tokens
                    "output_tokens": 0,
                    "cost_usd": result.cost_usd,
                    "turns": result.turns,
                    "session_id": result.session_id,
                },
            )
            logger.info(
                "Design agent %s completed: strategy=%s (turns=%d, cost=$%.2f)",
                operation_id,
                strategy_info["strategy_name"],
                result.turns,
                result.cost_usd,
            )

        except Exception as e:
            logger.exception("Design agent %s failed", operation_id)
            await ops.fail_operation(
                operation_id=operation_id,
                error_message=str(e),
            )


# ==============================================================================
# Module-level app for uvicorn (same pattern as backtest_worker.py)
# ==============================================================================


def _create_default_worker() -> DesignAgentWorker:
    """Create the default worker instance for container deployment.

    Reads configuration from environment variables and creates a
    ClaudeAgentRuntime as the runtime provider.
    """
    from ktrdr.agents.runtime.claude import ClaudeAgentRuntime
    from ktrdr.agents.runtime.protocol import AgentRuntimeConfig
    from ktrdr.config.settings import get_api_service_settings, get_worker_settings

    worker_settings = get_worker_settings()

    # Backend URL (strip /api/v1 suffix if present)
    api_settings = get_api_service_settings()
    backend_url = api_settings.base_url
    if backend_url.endswith("/api/v1"):
        backend_url = backend_url[:-7]

    # Create runtime
    runtime_config = AgentRuntimeConfig(
        model=os.environ.get("KTRDR_AGENT_MODEL", DEFAULT_DESIGN_MODEL),
        max_budget_usd=float(
            os.environ.get("KTRDR_AGENT_MAX_BUDGET", str(DEFAULT_DESIGN_MAX_BUDGET))
        ),
        max_turns=int(
            os.environ.get("KTRDR_AGENT_MAX_TURNS", str(DEFAULT_DESIGN_MAX_TURNS))
        ),
    )
    runtime = ClaudeAgentRuntime(config=runtime_config)

    return DesignAgentWorker(
        runtime=runtime,
        worker_port=worker_settings.port,
        backend_url=backend_url,
        model=runtime_config.model,
        max_turns=runtime_config.max_turns,
        max_budget_usd=runtime_config.max_budget_usd,
    )


# Only create worker instance when running as a module (uvicorn),
# not when imported for testing
if os.environ.get("KTRDR_WORKER_TYPE") == "agent_design":
    _worker = _create_default_worker()
    app = _worker.app
else:
    # When imported for testing, app is not created at module level.
    # Tests create DesignAgentWorker directly with mock runtime.
    app = None  # type: ignore[assignment]
