"""Task runner for executing tasks via Claude Code.

Handles task execution by constructing prompts, invoking Claude Code
in the sandbox, and parsing structured output.
"""

import re
import time
from typing import Callable, Literal

from orchestrator.config import OrchestratorConfig
from orchestrator.models import Task, TaskResult
from orchestrator.sandbox import SandboxManager


async def run_task(
    task: Task,
    sandbox: SandboxManager,
    config: OrchestratorConfig,
    plan_path: str,
    human_guidance: str | None = None,
    on_tool_use: Callable[[str, dict], None] | None = None,
) -> TaskResult:
    """Execute a task via Claude Code in the sandbox.

    Args:
        task: The task to execute
        sandbox: Sandbox manager for Claude invocation
        config: Orchestrator configuration
        plan_path: Path to the milestone plan file (for /ktask invocation)
        human_guidance: Optional guidance from human (for retry after escalation)
        on_tool_use: Optional callback for streaming tool use events.
            If provided, uses streaming mode for real-time progress visibility.

    Returns:
        TaskResult with execution outcome
    """
    # Construct prompt with /ktask command
    prompt = _build_prompt(task, plan_path, human_guidance)

    # Invoke Claude Code (streaming if callback provided)
    start_time = time.time()

    if on_tool_use is not None:
        # Use streaming mode for real-time progress
        claude_result = await sandbox.invoke_claude_streaming(
            prompt=prompt,
            on_tool_use=on_tool_use,
            max_turns=config.max_turns,
            timeout=config.task_timeout_seconds,
        )
    else:
        # Use standard mode (no streaming)
        claude_result = await sandbox.invoke_claude(
            prompt=prompt,
            max_turns=config.max_turns,
            timeout=config.task_timeout_seconds,
        )

    duration = time.time() - start_time

    # Parse status and metadata from output
    status, question, options, recommendation, error = parse_task_output(
        claude_result.result
    )

    # Estimate tokens from cost (rough estimate: ~$0.01 per 1000 tokens)
    tokens_used = _estimate_tokens(claude_result.total_cost_usd)

    return TaskResult(
        task_id=task.id,
        status=status,
        duration_seconds=duration,
        tokens_used=tokens_used,
        cost_usd=claude_result.total_cost_usd,
        output=claude_result.result,
        session_id=claude_result.session_id,
        question=question,
        options=options,
        recommendation=recommendation,
        error=error,
    )


def _build_prompt(
    task: Task, plan_path: str, human_guidance: str | None = None
) -> str:
    """Build the prompt for Claude Code execution using /ktask skill.

    Invokes the /ktask skill which handles:
    - TDD workflow (RED → GREEN → REFACTOR)
    - Git workflow (branch, commits)
    - Memory reflection
    - Handoff documents
    """
    prompt = f"/ktask impl: {plan_path} task: {task.id}"

    if human_guidance:
        prompt += f"\n\nAdditional guidance: {human_guidance}"

    return prompt


def _estimate_tokens(cost_usd: float) -> int:
    """Estimate token count from cost.

    Rough estimate based on Claude pricing (~$0.01 per 1000 tokens average).
    """
    if cost_usd <= 0:
        return 0
    return int(cost_usd * 100000)  # $0.01 = 1000 tokens


def parse_task_output(
    output: str,
) -> tuple[
    Literal["completed", "failed", "needs_human"],
    str | None,  # question
    list[str] | None,  # options
    str | None,  # recommendation
    str | None,  # error
]:
    """Parse structured output from Claude Code.

    Extracts STATUS and related fields from Claude's output.

    Args:
        output: Raw output text from Claude Code

    Returns:
        Tuple of (status, question, options, recommendation, error)
    """
    # Default values
    status: Literal["completed", "failed", "needs_human"] = "completed"
    question: str | None = None
    options: list[str] | None = None
    recommendation: str | None = None
    error: str | None = None

    # Parse STATUS
    status_match = re.search(r"STATUS:\s*(completed|failed|needs_human)", output)
    if status_match:
        status = status_match.group(1)  # type: ignore[assignment]

    # Parse ERROR for failed status
    error_match = re.search(r"ERROR:\s*(.+?)(?:\n|$)", output)
    if error_match:
        error = error_match.group(1).strip()

    # Parse QUESTION for needs_human status
    question_match = re.search(r"QUESTION:\s*(.+?)(?:\n|$)", output)
    if question_match:
        question = question_match.group(1).strip()

    # Parse OPTIONS for needs_human status
    options_match = re.search(r"OPTIONS:\s*(.+?)(?:\n|$)", output)
    if options_match:
        options_str = options_match.group(1).strip()
        options = [opt.strip() for opt in options_str.split(",")]

    # Parse RECOMMENDATION for needs_human status
    rec_match = re.search(r"RECOMMENDATION:\s*(.+?)(?:\n|$)", output)
    if rec_match:
        recommendation = rec_match.group(1).strip()

    return status, question, options, recommendation, error
