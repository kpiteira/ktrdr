"""Milestone runner for sequential task execution.

Coordinates running all tasks in a milestone, persisting state after
each task for resumability, and reporting progress.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

from opentelemetry import trace

from orchestrator import telemetry
from orchestrator.config import OrchestratorConfig
from orchestrator.models import ClaudeResult, Task, TaskResult
from orchestrator.plan_parser import parse_plan
from orchestrator.sandbox import SandboxManager
from orchestrator.state import OrchestratorState
from orchestrator.task_runner import run_task


@dataclass
class MilestoneResult:
    """Result of milestone execution.

    Contains final status, aggregated metrics, and state reference.
    """

    status: Literal["completed", "failed", "needs_human"]
    state: OrchestratorState
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_cost_usd: float
    total_tokens: int
    total_duration_seconds: float


async def run_milestone(
    plan_path: str,
    state_dir: Path,
    resume: bool = False,
    config: OrchestratorConfig | None = None,
    tracer: trace.Tracer | None = None,
    on_task_complete: Callable[[Task, TaskResult], None] | None = None,
) -> MilestoneResult:
    """Run all tasks in a milestone sequentially.

    Parses the plan file, executes tasks in order, persists state after
    each task, and handles needs_human/failed statuses by stopping.

    Args:
        plan_path: Path to the milestone plan markdown file
        state_dir: Directory for state persistence
        resume: If True, continue from last completed task
        config: Orchestrator configuration (uses defaults if None)
        tracer: OpenTelemetry tracer (uses no-op if None)
        on_task_complete: Optional callback invoked after each completed task,
            receives the Task and TaskResult for displaying summaries

    Returns:
        MilestoneResult with final status and aggregated metrics
    """
    config = config or OrchestratorConfig.from_env()
    tracer = tracer or trace.get_tracer("orchestrator")

    # Extract milestone ID from plan filename
    milestone_id = Path(plan_path).stem

    # Parse plan to get tasks
    tasks = parse_plan(plan_path)

    # Load or create state
    state = None
    if resume:
        state = OrchestratorState.load(state_dir, milestone_id)

    if state is None:
        state = OrchestratorState(
            milestone_id=milestone_id,
            plan_path=plan_path,
            started_at=datetime.now(),
        )

    # Initialize sandbox
    sandbox = SandboxManager(
        container_name=config.sandbox_container,
        workspace_path=config.workspace_path,
    )

    # Determine starting point
    start_index = state.get_next_task_index() if resume else 0

    # Tracking variables
    total_cost = 0.0
    total_tokens = 0
    total_duration = 0.0
    final_status: Literal["completed", "failed", "needs_human"] = "completed"

    # Create milestone span
    with tracer.start_as_current_span("orchestrator.milestone") as milestone_span:
        milestone_span.set_attribute("milestone.id", milestone_id)
        milestone_span.set_attribute("milestone.total_tasks", len(tasks))
        milestone_span.set_attribute("milestone.resume", resume)
        milestone_span.set_attribute("milestone.start_index", start_index)

        # Execute tasks sequentially
        for _i, task in enumerate(tasks[start_index:], start=start_index):
            with tracer.start_as_current_span("orchestrator.task") as task_span:
                task_span.set_attribute("task.id", task.id)
                task_span.set_attribute("task.title", task.title)

                # Run the task
                result = await run_task(task, sandbox, config)

                # Record telemetry
                task_span.set_attribute("task.status", result.status)
                task_span.set_attribute("claude.tokens", result.tokens_used)
                task_span.set_attribute("claude.cost_usd", result.cost_usd)
                task_span.set_attribute("task.duration_seconds", result.duration_seconds)

                # Update metrics (if initialized)
                _record_metrics(milestone_id, result.status, result.tokens_used, result.cost_usd)

                # Accumulate totals
                total_cost += result.cost_usd
                total_tokens += result.tokens_used
                total_duration += result.duration_seconds

                # Handle result based on status
                if result.status == "completed":
                    state.mark_task_completed(task.id, asdict(result))
                    state.save(state_dir)

                    # Invoke callback for task summary display
                    if on_task_complete is not None:
                        on_task_complete(task, result)

                elif result.status == "needs_human":
                    state.save(state_dir)
                    final_status = "needs_human"
                    break

                elif result.status == "failed":
                    state.failed_tasks.append(task.id)
                    state.save(state_dir)
                    final_status = "failed"
                    break

        # Record final milestone attributes
        milestone_span.set_attribute("milestone.status", final_status)
        milestone_span.set_attribute("milestone.total_cost_usd", total_cost)
        milestone_span.set_attribute("milestone.total_tokens", total_tokens)
        milestone_span.set_attribute("milestone.completed_tasks", len(state.completed_tasks))
        milestone_span.set_attribute("milestone.failed_tasks", len(state.failed_tasks))

    return MilestoneResult(
        status=final_status,
        state=state,
        total_tasks=len(tasks),
        completed_tasks=len(state.completed_tasks),
        failed_tasks=len(state.failed_tasks),
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
        total_duration_seconds=total_duration,
    )


def _record_metrics(
    milestone_id: str,
    status: str,
    tokens: int,
    cost_usd: float,
) -> None:
    """Record metrics if counters are initialized.

    Safely handles the case where create_metrics() hasn't been called.
    """
    try:
        telemetry.tasks_counter.add(1, {"milestone": milestone_id, "status": status})
        telemetry.tokens_counter.add(tokens, {"milestone": milestone_id})
        telemetry.cost_counter.add(cost_usd, {"milestone": milestone_id})
    except (AttributeError, NameError):
        # Counters not initialized - telemetry disabled
        pass


async def create_milestone_pr(
    sandbox: SandboxManager,
    milestone_id: str,
    completed_tasks: list[str],
    total_cost_usd: float,
) -> ClaudeResult:
    """Create a PR for the milestone via Claude.

    Invokes Claude Code to create a pull request summarizing all changes
    made across the completed tasks.

    Args:
        sandbox: SandboxManager for invoking Claude
        milestone_id: The milestone identifier
        completed_tasks: List of completed task IDs
        total_cost_usd: Total cost of the milestone

    Returns:
        ClaudeResult from the PR creation invocation
    """
    prompt = f"""Create a PR for milestone {milestone_id}.

Completed tasks: {', '.join(completed_tasks)}
Total cost: ${total_cost_usd:.2f}

Use `gh pr create` with a summary of all changes made across the tasks.
Include:
- A descriptive title for the milestone
- A summary of what was implemented
- Any key decisions or changes made

The PR should summarize the entire milestone's work, not individual tasks."""

    return await sandbox.invoke_claude(prompt=prompt, max_turns=10)
