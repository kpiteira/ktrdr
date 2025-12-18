"""Task runner for executing tasks via Claude Code.

Handles task execution by constructing prompts, invoking Claude Code
in the sandbox, and parsing structured output.
"""

import re
import time
from typing import Literal

from orchestrator.config import OrchestratorConfig
from orchestrator.models import Task, TaskResult
from orchestrator.sandbox import SandboxManager


async def run_task(
    task: Task,
    sandbox: SandboxManager,
    config: OrchestratorConfig,
    human_guidance: str | None = None,
) -> TaskResult:
    """Execute a task via Claude Code in the sandbox.

    Args:
        task: The task to execute
        sandbox: Sandbox manager for Claude invocation
        config: Orchestrator configuration
        human_guidance: Optional guidance from human (for retry after escalation)

    Returns:
        TaskResult with execution outcome
    """
    # Construct prompt with /ktask command
    prompt = _build_prompt(task, human_guidance)

    # Invoke Claude Code
    start_time = time.time()
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


def _build_prompt(task: Task, human_guidance: str | None = None) -> str:
    """Build the prompt for Claude Code execution."""
    criteria = "\n".join(f"- {c}" for c in task.acceptance_criteria)

    prompt = f"""# Task {task.id}: {task.title}

**File:** {task.file_path or "N/A"}

**Description:**
{task.description}

**Acceptance Criteria:**
{criteria}

{f"**Additional Guidance:** {human_guidance}" if human_guidance else ""}

Please implement this task. When complete, include in your final message:
- STATUS: completed | needs_human | failed
- If needs_human: QUESTION: <question> OPTIONS: <options> RECOMMENDATION: <rec>
- If failed: ERROR: <what went wrong>
"""
    return prompt.strip()


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
