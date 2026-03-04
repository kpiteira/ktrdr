"""AssessmentAgentWorker — containerized assessment agent using Claude Code + MCP.

Receives strategy metrics and results, invokes Claude Code via AgentRuntime protocol,
and extracts the structured assessment from the SDK transcript. Follows the
same WorkerAPIBase contract as design and other workers.

Note: This worker's FastAPI app is only initialized when
KTRDR_WORKER_TYPE=agent_assessment is set in the environment.
It is typically started via the container entrypoint.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any

import yaml
from pydantic import Field

from ktrdr.agents import memory
from ktrdr.agents.memory import ExperimentRecord, Hypothesis
from ktrdr.agents.runtime.protocol import AgentRuntime
from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.logging import get_logger
from ktrdr.workers.base import WorkerAPIBase, WorkerOperationMixin

logger = get_logger(__name__)

# Default configuration
DEFAULT_ASSESSMENT_MAX_TURNS = 20
DEFAULT_ASSESSMENT_MAX_BUDGET = 1.5
DEFAULT_ASSESSMENT_MODEL = "claude-sonnet-4-6"

# MCP tool name for result extraction
SAVE_ASSESSMENT_TOOL = "mcp__ktrdr__save_assessment"

# Default allowed tools for assessment agent
DEFAULT_ALLOWED_TOOLS = [
    "mcp__ktrdr__*",  # All ktrdr MCP tools
    "Read",  # Filesystem read (strategies, memory, experiments)
    "Glob",  # Filesystem search
    "Grep",  # Content search
]


class AssessmentStartRequest(WorkerOperationMixin):
    """Request to start an assessment operation.

    Sent by backend's research orchestrator when dispatching assessment work.
    """

    strategy_name: str = Field(..., description="Name of the strategy to assess")
    strategy_config: dict[str, Any] | None = Field(
        default=None,
        description="Strategy YAML configuration (optional, agent can read from disk)",
    )
    training_metrics: dict[str, Any] = Field(
        ..., description="Training metrics (accuracy, loss, etc.)"
    )
    backtest_results: dict[str, Any] = Field(
        ..., description="Backtest results (sharpe, max_dd, total_trades, etc.)"
    )
    experiment_history: str | None = Field(
        default=None,
        description="Summary of past experiments for context",
    )


class AssessmentAgentWorker(WorkerAPIBase):
    """Assessment agent worker using Claude Code + MCP via AgentRuntime.

    Accepts strategy metrics and results, runs Claude Code to analyze them,
    and reports structured assessment via the operations service.
    """

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        worker_port: int = 5020,
        backend_url: str = "http://backend:8000",
        model: str = DEFAULT_ASSESSMENT_MODEL,
        max_turns: int = DEFAULT_ASSESSMENT_MAX_TURNS,
        max_budget_usd: float = DEFAULT_ASSESSMENT_MAX_BUDGET,
    ) -> None:
        super().__init__(
            worker_type=WorkerType.AGENT_ASSESSMENT,
            operation_type=OperationType.AGENT_ASSESSMENT,
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

        # Register the assessment-specific start endpoint
        @self.app.post("/assessments/start")
        async def start_assessment(request: AssessmentStartRequest):
            """Start an assessment operation.

            Accepts strategy metrics and results, creates an operation,
            and launches Claude Code in the background.
            """
            operation_id = (
                request.task_id or f"worker_assessment_{uuid.uuid4().hex[:12]}"
            )

            ops = self.get_operations_service()
            await ops.create_operation(
                operation_id=operation_id,
                operation_type=OperationType.AGENT_ASSESSMENT,
                metadata=OperationMetadata(
                    symbol="",
                    timeframe="",
                    mode="assessment",
                    parameters={
                        "strategy_name": request.strategy_name,
                    },
                ),
            )

            task = asyncio.create_task(
                self._execute_assessment_work(
                    operation_id=operation_id,
                    strategy_name=request.strategy_name,
                    strategy_config=request.strategy_config,
                    training_metrics=request.training_metrics,
                    backtest_results=request.backtest_results,
                    experiment_history=request.experiment_history,
                )
            )

            await ops.start_operation(operation_id, task)

            return {
                "success": True,
                "operation_id": operation_id,
                "status": "started",
            }

    def _build_user_prompt(
        self,
        strategy_name: str,
        strategy_config: dict[str, Any] | None,
        training_metrics: dict[str, Any],
        backtest_results: dict[str, Any],
        experiment_history: str | None,
    ) -> str:
        """Build the user prompt from strategy info and metrics.

        The system prompt is static (defines role/rubric). The user prompt
        carries the strategy data, metrics, and experiment context.
        """
        parts = [
            f"## Strategy: {strategy_name}",
        ]

        if strategy_config:
            config_yaml = yaml.dump(strategy_config, default_flow_style=False)
            parts.append(f"\n## Strategy Configuration\n\n```yaml\n{config_yaml}```")

        parts.append(
            f"\n## Training Metrics\n\n```json\n{json.dumps(training_metrics, indent=2)}\n```"
        )
        parts.append(
            f"\n## Backtest Results\n\n```json\n{json.dumps(backtest_results, indent=2)}\n```"
        )

        if experiment_history:
            parts.append(f"\n## Experiment History\n\n{experiment_history}")

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

    def extract_assessment_from_transcript(
        self, transcript: list[dict]
    ) -> dict[str, Any] | None:
        """Extract assessment info from the last save_assessment tool call.

        Scans the transcript for tool_use entries matching save_assessment.
        Uses the last occurrence (the agent may iterate and save multiple times,
        the final save is the definitive one).

        Returns:
            Dict with verdict, strengths, weaknesses, suggestions, assessment_path,
            or None if not found.
        """
        last_save: dict[str, Any] | None = None

        for i, entry in enumerate(transcript):
            if (
                entry.get("type") == "tool_use"
                and entry.get("tool") == SAVE_ASSESSMENT_TOOL
            ):
                tool_input = entry.get("input", {})
                verdict = tool_input.get("verdict")
                strategy_name = tool_input.get("strategy_name")
                strengths = tool_input.get("strengths", [])
                weaknesses = tool_input.get("weaknesses", [])
                suggestions = tool_input.get("suggestions", [])
                hypotheses = tool_input.get("hypotheses", [])

                # Check for corresponding tool_result to get assessment_path
                assessment_path = None
                for j in range(i + 1, len(transcript)):
                    result_entry = transcript[j]
                    if result_entry.get("type") == "tool_result" and result_entry.get(
                        "tool_use_id"
                    ) == entry.get("id"):
                        content = result_entry.get("content", "")
                        if isinstance(content, str):
                            try:
                                parsed = json.loads(content)
                                assessment_path = parsed.get("assessment_path")
                            except (json.JSONDecodeError, TypeError):
                                pass
                        break

                if verdict or strategy_name:
                    last_save = {
                        "verdict": verdict,
                        "strategy_name": strategy_name,
                        "strengths": strengths,
                        "weaknesses": weaknesses,
                        "suggestions": suggestions,
                        "hypotheses": hypotheses,
                        "assessment_path": assessment_path,
                    }

        return last_save

    def _save_memory(
        self,
        strategy_name: str,
        training_metrics: dict[str, Any],
        backtest_results: dict[str, Any],
        assessment_info: dict[str, Any],
    ) -> None:
        """Save experiment record and hypotheses to memory (best-effort).

        Called after a successful assessment. Failures are logged as warnings
        but do not affect operation completion.
        """
        try:
            experiment_id = memory.generate_experiment_id()

            record = ExperimentRecord(
                id=experiment_id,
                timestamp=datetime.now().isoformat(),
                strategy_name=strategy_name,
                context={},
                results=backtest_results,
                assessment={
                    "verdict": assessment_info.get("verdict"),
                    "observations": assessment_info.get("strengths", []),
                    "hypotheses": [
                        h.get("text", "") for h in assessment_info.get("hypotheses", [])
                    ],
                    "limitations": assessment_info.get("weaknesses", []),
                },
                source="agent",
            )
            memory.save_experiment(record)

            # Save new hypotheses from the assessment
            for h in assessment_info.get("hypotheses", []):
                if not h.get("text"):
                    continue
                hypothesis = Hypothesis(
                    id=memory.generate_hypothesis_id(),
                    text=h["text"],
                    source_experiment=experiment_id,
                    rationale=h.get("rationale", ""),
                )
                memory.save_hypothesis(hypothesis)

            logger.info(
                "Saved experiment %s with %d hypotheses",
                experiment_id,
                len(assessment_info.get("hypotheses", [])),
            )

        except Exception:
            logger.warning(
                "Failed to save memory for strategy %s (non-blocking)",
                strategy_name,
                exc_info=True,
            )

    async def _execute_assessment_work(
        self,
        operation_id: str,
        strategy_name: str,
        strategy_config: dict[str, Any] | None,
        training_metrics: dict[str, Any],
        backtest_results: dict[str, Any],
        experiment_history: str | None,
    ) -> None:
        """Execute assessment work in the background.

        Invokes AgentRuntime with the assessment prompt and MCP config,
        extracts assessment info from the transcript, and reports completion.
        """
        ops = self.get_operations_service()

        try:
            from ktrdr.agents.assessment_sdk_prompt import ASSESSMENT_SYSTEM_PROMPT

            user_prompt = self._build_user_prompt(
                strategy_name=strategy_name,
                strategy_config=strategy_config,
                training_metrics=training_metrics,
                backtest_results=backtest_results,
                experiment_history=experiment_history,
            )

            logger.info(
                "Starting assessment agent for operation %s (strategy=%s)",
                operation_id,
                strategy_name,
            )

            result = await self._runtime.invoke(
                user_prompt,
                model=self._model,
                max_turns=self._max_turns,
                max_budget_usd=self._max_budget_usd,
                allowed_tools=DEFAULT_ALLOWED_TOOLS,
                cwd="/app",
                system_prompt=ASSESSMENT_SYSTEM_PROMPT,
                mcp_servers=self._get_mcp_servers(),
            )

            assessment_info = self.extract_assessment_from_transcript(result.transcript)

            if assessment_info is None:
                await ops.fail_operation(
                    operation_id=operation_id,
                    error_message=(
                        "Assessment agent did not call save_assessment MCP tool. "
                        "No assessment was produced."
                    ),
                )
                logger.warning(
                    "Assessment agent %s produced no assessment (turns=%d, cost=$%.2f)",
                    operation_id,
                    result.turns,
                    result.cost_usd,
                )
                return

            # Save memory (best-effort, non-blocking)
            self._save_memory(
                strategy_name=strategy_name,
                training_metrics=training_metrics,
                backtest_results=backtest_results,
                assessment_info=assessment_info,
            )

            await ops.complete_operation(
                operation_id=operation_id,
                result_summary={
                    "verdict": assessment_info["verdict"],
                    "strategy_name": assessment_info["strategy_name"],
                    "strengths": assessment_info["strengths"],
                    "weaknesses": assessment_info["weaknesses"],
                    "suggestions": assessment_info["suggestions"],
                    "hypotheses": assessment_info.get("hypotheses", []),
                    "assessment_path": assessment_info.get("assessment_path"),
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": result.cost_usd,
                    "turns": result.turns,
                    "session_id": result.session_id,
                },
            )
            logger.info(
                "Assessment agent %s completed: verdict=%s (turns=%d, cost=$%.2f)",
                operation_id,
                assessment_info["verdict"],
                result.turns,
                result.cost_usd,
            )

        except Exception as e:
            logger.exception("Assessment agent %s failed", operation_id)
            await ops.fail_operation(
                operation_id=operation_id,
                error_message=str(e),
            )


# ==============================================================================
# Module-level app for uvicorn (same pattern as design_agent_worker.py)
# ==============================================================================


def _create_default_worker() -> AssessmentAgentWorker:
    """Create the default worker instance for container deployment."""
    from ktrdr.agents.runtime.claude import ClaudeAgentRuntime
    from ktrdr.agents.runtime.protocol import AgentRuntimeConfig
    from ktrdr.config.settings import get_api_service_settings, get_worker_settings

    worker_settings = get_worker_settings()

    api_settings = get_api_service_settings()
    backend_url = api_settings.base_url
    if backend_url.endswith("/api/v1"):
        backend_url = backend_url[:-7]

    runtime_config = AgentRuntimeConfig(
        model=os.environ.get("KTRDR_AGENT_MODEL", DEFAULT_ASSESSMENT_MODEL),
        max_budget_usd=float(
            os.environ.get("KTRDR_AGENT_MAX_BUDGET", str(DEFAULT_ASSESSMENT_MAX_BUDGET))
        ),
        max_turns=int(
            os.environ.get("KTRDR_AGENT_MAX_TURNS", str(DEFAULT_ASSESSMENT_MAX_TURNS))
        ),
    )
    runtime = ClaudeAgentRuntime(config=runtime_config)

    return AssessmentAgentWorker(
        runtime=runtime,
        worker_port=worker_settings.port,
        backend_url=backend_url,
        model=runtime_config.model,
        max_turns=runtime_config.max_turns,
        max_budget_usd=runtime_config.max_budget_usd,
    )


# Only create worker instance when running as a module (uvicorn)
if os.environ.get("KTRDR_WORKER_TYPE") == "agent_assessment":
    _worker = _create_default_worker()
    app = _worker.app
else:
    app = None  # type: ignore[assignment]
