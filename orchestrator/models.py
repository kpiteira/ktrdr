"""Data models for the Orchestrator.

Defines dataclasses for tasks, Claude Code results, and task execution results.
All models are JSON serializable via dataclasses.asdict() for state persistence.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Task:
    """A task extracted from a milestone plan.

    Represents a single unit of work to be executed by Claude Code.
    """

    id: str
    title: str
    description: str
    file_path: str | None
    acceptance_criteria: list[str]
    plan_file: str
    milestone_id: str


@dataclass
class ClaudeResult:
    """Result from a Claude Code invocation.

    Captures the structured output from claude CLI with --output-format json.
    """

    is_error: bool
    result: str
    total_cost_usd: float
    duration_ms: int
    num_turns: int
    session_id: str


@dataclass
class TaskResult:
    """Result of executing a task.

    Captures task execution outcome including status, metrics, and any
    escalation information for needs_human status.

    Status values:
        completed: Task finished successfully
        failed: Task encountered an error
        needs_human: Task requires human input to proceed
    """

    task_id: str
    status: Literal["completed", "failed", "needs_human"]
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    output: str
    session_id: str
    # If needs_human - escalation information
    question: str | None = None
    options: list[str] | None = None
    recommendation: str | None = None
    # If failed - error details
    error: str | None = None
