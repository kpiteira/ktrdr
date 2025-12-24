"""Milestone runner for sequential task execution.

Coordinates running all tasks in a milestone, persisting state after
each task for resumability, and reporting progress.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

from opentelemetry import trace
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from orchestrator import telemetry
from orchestrator.config import OrchestratorConfig
from orchestrator.e2e_runner import apply_e2e_fix, run_e2e_tests
from orchestrator.escalation import EscalationInfo, escalate_and_wait
from orchestrator.haiku_brain import HaikuBrain
from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
from orchestrator.models import ClaudeResult, Task, TaskResult
from orchestrator.sandbox import SandboxManager
from orchestrator.state import OrchestratorState
from orchestrator.task_runner import run_task_with_escalation

# Console for E2E output
console = Console()


@dataclass
class MilestoneResult:
    """Result of milestone execution.

    Contains final status, aggregated metrics, and state reference.

    Status values:
        completed: All tasks and E2E tests passed
        failed: Task execution failed
        needs_human: Task requires human input
        e2e_failed: E2E tests failed after tasks completed
    """

    status: Literal["completed", "failed", "needs_human", "e2e_failed"]
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
    on_tool_use: Callable[[str, dict], None] | None = None,
    notify: bool = True,
    model: str | None = None,
) -> MilestoneResult:
    """Run all tasks in a milestone sequentially.

    Parses the plan file, executes tasks in order, persists state after
    each task, and handles needs_human/failed statuses by stopping.

    Uses run_task_with_escalation for automatic loop detection and
    escalation handling. Loop detection state is persisted for resumability.

    Args:
        plan_path: Path to the milestone plan markdown file
        state_dir: Directory for state persistence
        resume: If True, continue from last completed task
        config: Orchestrator configuration (uses defaults if None)
        tracer: OpenTelemetry tracer (uses no-op if None)
        on_task_complete: Optional callback invoked after each completed task,
            receives the Task and TaskResult for displaying summaries
        on_tool_use: Optional callback for real-time streaming of tool calls.
            Receives (tool_name, tool_input) for each Claude tool invocation.
            Use with format_tool_call() for human-readable progress display.
        notify: Whether to send notifications on escalation (default True)
        model: Claude model to use for task execution (e.g., 'sonnet', 'opus').
            If None, uses Claude's default model.

    Returns:
        MilestoneResult with final status and aggregated metrics
    """
    config = config or OrchestratorConfig.from_env()
    tracer = tracer or trace.get_tracer("orchestrator")

    # Extract milestone ID from plan filename
    milestone_id = Path(plan_path).stem

    # Parse plan to get tasks using HaikuBrain
    brain = HaikuBrain()
    plan_content = Path(plan_path).read_text()
    extracted = brain.extract_tasks(plan_content)

    # Convert ExtractedTask to Task model for compatibility
    tasks = [
        Task(
            id=t.id,
            title=t.title,
            description=t.description,
            file_path=None,  # /ktask reads this from plan
            acceptance_criteria=[],
            plan_file=str(plan_path),
            milestone_id=milestone_id,
        )
        for t in extracted
    ]

    # Initialize sandbox
    sandbox = SandboxManager(
        container_name=config.sandbox_container,
        workspace_path=config.workspace_path,
    )

    # Load or create state
    state = None
    if resume:
        state = OrchestratorState.load(state_dir, milestone_id)

    if state is None:
        # Get current branch for PR base (before /ktask creates a new branch)
        starting_branch = _get_current_branch(sandbox)

        state = OrchestratorState(
            milestone_id=milestone_id,
            plan_path=plan_path,
            started_at=datetime.now(),
            starting_branch=starting_branch,
        )

    # Create loop detector with state (persists failure tracking across resumes)
    loop_detector_config = LoopDetectorConfig()
    loop_detector = LoopDetector(loop_detector_config, state)

    # Determine starting point
    start_index = state.get_next_task_index() if resume else 0

    # Tracking variables
    total_cost = 0.0
    total_tokens = 0
    total_duration = 0.0
    final_status: Literal["completed", "failed", "needs_human", "e2e_failed"] = "completed"

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

                # Run the task with escalation handling and loop detection
                result = await run_task_with_escalation(
                    task,
                    sandbox,
                    config,
                    plan_path,
                    loop_detector,
                    tracer,
                    notify=notify,
                    on_tool_use=on_tool_use,
                    model=model,
                )

                # Record telemetry
                task_span.set_attribute("task.status", result.status)
                task_span.set_attribute("claude.tokens", result.tokens_used)
                task_span.set_attribute("claude.cost_usd", result.cost_usd)
                task_span.set_attribute(
                    "task.duration_seconds", result.duration_seconds
                )

                # Update metrics (if initialized)
                _record_metrics(
                    milestone_id, result.status, result.tokens_used, result.cost_usd
                )

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

        # Run E2E tests if all tasks completed successfully
        if final_status == "completed":
            # Read plan content and parse E2E scenario
            plan_content = Path(plan_path).read_text()
            e2e_scenario = parse_e2e_scenario(plan_content)

            if e2e_scenario:
                console.print("\n[bold]Running E2E tests...[/bold]")

                while True:
                    e2e_result = await run_e2e_tests(
                        milestone_id, e2e_scenario, sandbox, config, tracer
                    )

                    # Accumulate E2E costs
                    total_cost += e2e_result.cost_usd
                    total_tokens += e2e_result.tokens_used
                    total_duration += e2e_result.duration_seconds

                    if e2e_result.status == "passed":
                        console.print(
                            f"E2E: [bold green]PASSED[/bold green] "
                            f"({e2e_result.duration_seconds:.0f}s)"
                        )
                        state.e2e_status = "passed"
                        state.save(state_dir)
                        break

                    elif e2e_result.status == "failed":
                        console.print("E2E: [bold red]FAILED[/bold red]")

                        # Record failure for loop detection
                        loop_detector.record_e2e_failure(
                            e2e_result.diagnosis or "Unknown"
                        )
                        should_stop, reason = loop_detector.should_stop_e2e()

                        if should_stop:
                            console.print(f"[bold red]LOOP DETECTED:[/bold red] {reason}")
                            state.e2e_status = "failed"
                            state.save(state_dir)
                            final_status = "e2e_failed"
                            break

                        # Show diagnosis
                        if e2e_result.diagnosis:
                            console.print(
                                Panel(
                                    e2e_result.diagnosis,
                                    title="Claude's Diagnosis",
                                    border_style="red",
                                )
                            )

                        if e2e_result.is_fixable and e2e_result.fix_suggestion:
                            # Prompt for fix
                            apply = prompt_for_fix(e2e_result.fix_suggestion)

                            if apply:
                                console.print("Applying fix...")
                                success = await apply_e2e_fix(
                                    e2e_result.fix_suggestion, sandbox, config, tracer
                                )

                                if success:
                                    console.print("Fix applied. Re-running E2E...")
                                    continue  # Re-run E2E
                                else:
                                    console.print("[red]Fix could not be applied[/red]")

                        # Not fixable or fix declined - escalate
                        info = EscalationInfo(
                            task_id="e2e",
                            question=e2e_result.diagnosis or "E2E test failed",
                            options=_extract_options(e2e_result.raw_output),
                            recommendation=_extract_recommendation(
                                e2e_result.raw_output
                            ),
                            raw_output=e2e_result.raw_output,
                        )
                        await escalate_and_wait(info, tracer, notify)
                        state.e2e_status = "failed"
                        state.save(state_dir)
                        final_status = "e2e_failed"
                        break

                    else:  # unclear
                        console.print("E2E: [bold yellow]UNCLEAR[/bold yellow]")
                        # Escalate for human interpretation
                        info = EscalationInfo(
                            task_id="e2e",
                            question="E2E test result unclear. Please review the output.",
                            options=None,
                            recommendation=None,
                            raw_output=e2e_result.raw_output,
                        )
                        await escalate_and_wait(info, tracer, notify)
                        state.e2e_status = "failed"
                        state.save(state_dir)
                        final_status = "e2e_failed"
                        break

        # Record final milestone attributes
        milestone_span.set_attribute("milestone.status", final_status)
        milestone_span.set_attribute("milestone.total_cost_usd", total_cost)
        milestone_span.set_attribute("milestone.total_tokens", total_tokens)
        milestone_span.set_attribute(
            "milestone.completed_tasks", len(state.completed_tasks)
        )
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


def prompt_for_fix(fix_suggestion: str) -> bool:
    """Prompt user to apply a suggested fix.

    Displays the fix suggestion and asks for confirmation.

    Args:
        fix_suggestion: The suggested fix from Claude's diagnosis

    Returns:
        True if user wants to apply the fix, False otherwise
    """
    console.print(
        Panel(
            fix_suggestion,
            title="Suggested Fix",
            border_style="yellow",
        )
    )
    response = Prompt.ask("Apply fix?", choices=["y", "n"], default="y")
    return response.lower() == "y"


def _extract_options(raw_output: str) -> list[str] | None:
    """Extract options from E2E failure output.

    Looks for OPTIONS: marker in the output.

    Args:
        raw_output: Raw output from Claude E2E test

    Returns:
        List of options if found, None otherwise
    """
    import re

    match = re.search(
        r"OPTIONS:\s*(.+?)(?=RECOMMENDATION:|$)", raw_output, re.DOTALL | re.IGNORECASE
    )
    if match:
        options_text = match.group(1).strip()
        # Parse options from various formats
        lettered = re.findall(r"[A-Z]\)\s*(.+?)(?=[A-Z]\)|$)", options_text, re.DOTALL)
        if lettered:
            return [opt.strip() for opt in lettered]
        # Try bullet points
        bullets = re.findall(r"-\s*(.+?)(?=-|$)", options_text, re.DOTALL)
        if bullets:
            return [opt.strip() for opt in bullets]
        return [options_text]
    return None


def _extract_recommendation(raw_output: str) -> str | None:
    """Extract recommendation from E2E failure output.

    Looks for RECOMMENDATION: marker in the output.

    Args:
        raw_output: Raw output from Claude E2E test

    Returns:
        Recommendation if found, None otherwise
    """
    import re

    match = re.search(r"RECOMMENDATION:\s*(.+?)$", raw_output, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _get_current_branch(sandbox: SandboxManager) -> str:
    """Get the current git branch from the sandbox.

    Returns:
        Branch name, or "main" if detection fails.
    """
    import subprocess

    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                sandbox.container_name,
                "git",
                "-C",
                sandbox.workspace_path,
                "branch",
                "--show-current",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch if branch else "main"
    except Exception:
        pass
    return "main"


def parse_e2e_scenario(plan_content: str) -> str | None:
    """Extract E2E test scenario from plan content.

    Looks for a section starting with "## E2E Test" (with optional "Scenario" suffix)
    and extracts the content, preferring code blocks if present.

    This function uses regex for E2E extraction (Decision 10: keep regex for E2E,
    only use Haiku for task extraction and result interpretation).

    Args:
        plan_content: The full markdown content of the plan file

    Returns:
        The E2E scenario text, or None if no E2E section exists
    """
    import re

    # Find the E2E Test section header
    # Matches: ## E2E Test, ## E2E Test Scenario, etc.
    header_match = re.search(
        r"^##\s+E2E\s+Test.*?$", plan_content, re.MULTILINE | re.IGNORECASE
    )

    if not header_match:
        return None

    # Get content from after the header to the next ## section or end of file
    start = header_match.end()
    next_section_match = re.search(r"^##\s+", plan_content[start:], re.MULTILINE)

    if next_section_match:
        section_content = plan_content[start : start + next_section_match.start()]
    else:
        section_content = plan_content[start:]

    # Extract all code blocks within this section
    code_blocks = re.findall(r"```\w*\n(.*?)```", section_content, re.DOTALL)

    if code_blocks:
        # Return all code blocks joined together
        return "\n\n".join(block.strip() for block in code_blocks)

    # Fall back to plain text (strip leading/trailing whitespace)
    plain_text = section_content.strip()
    return plain_text if plain_text else None


async def create_milestone_pr(
    sandbox: SandboxManager,
    milestone_id: str,
    completed_tasks: list[str],
    total_cost_usd: float,
    base_branch: str = "main",
) -> ClaudeResult:
    """Create a PR for the milestone via Claude.

    Invokes Claude Code to create a pull request summarizing all changes
    made across the completed tasks.

    Args:
        sandbox: SandboxManager for invoking Claude
        milestone_id: The milestone identifier
        completed_tasks: List of completed task IDs
        total_cost_usd: Total cost of the milestone
        base_branch: Target branch for the PR (default: main)

    Returns:
        ClaudeResult from the PR creation invocation
    """
    prompt = f"""Create a PR for milestone {milestone_id}.

Completed tasks: {", ".join(completed_tasks)}
Total cost: ${total_cost_usd:.2f}

Use `gh pr create --base {base_branch}` with a summary of all changes made across the tasks.
Include:
- A descriptive title for the milestone
- A summary of what was implemented
- Any key decisions or changes made

The PR should summarize the entire milestone's work, not individual tasks."""

    return await sandbox.invoke_claude(prompt=prompt, max_turns=10)
