"""CLI for the Orchestrator.

Provides command-line interface for autonomous task execution.
"""

import asyncio
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from orchestrator import telemetry
from orchestrator.config import OrchestratorConfig
from orchestrator.haiku_brain import HaikuBrain
from orchestrator.health import CHECK_ORDER, get_health
from orchestrator.lock import MilestoneLock
from orchestrator.milestone_runner import (
    MilestoneResult,
    create_milestone_pr,
    run_milestone,
)
from orchestrator.models import Task, TaskResult
from orchestrator.runner import run_task
from orchestrator.sandbox import SandboxManager, format_tool_call
from orchestrator.state import OrchestratorState
from orchestrator.telemetry import create_metrics, setup_telemetry

console = Console()


@click.group()
@click.version_option(package_name="orchestrator")
def cli() -> None:
    """Orchestrator - Autonomous task execution for KTRDR."""
    pass


@cli.command()
@click.option("--check", type=click.Choice(CHECK_ORDER), help="Run single check")
def health(check: str | None) -> None:
    """Check orchestrator health status."""
    checks = [check] if check else None
    report = get_health(checks=checks)
    click.echo(json.dumps(report.to_dict(), indent=2))
    sys.exit(0 if report.status == "healthy" else 1)


@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.argument("task_id")
@click.option("--guidance", "-g", help="Additional guidance for Claude")
@click.option(
    "-m",
    "--model",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    default=None,
    help="Claude model for task execution (default: Claude's default)",
)
def task(plan_file: str, task_id: str, guidance: str | None, model: str | None) -> None:
    """Execute a single task from a plan file."""
    model_id = MODEL_ALIASES[model] if model else None
    asyncio.run(_run_task(plan_file, task_id, guidance, model_id))


async def _run_task(
    plan_file: str, task_id: str, guidance: str | None, model: str | None = None
) -> None:
    """Internal async implementation of task execution."""
    config = OrchestratorConfig.from_env()
    tracer, meter = setup_telemetry(config)
    create_metrics(meter)

    # Parse plan and find task using HaikuBrain
    milestone_id = Path(plan_file).stem
    brain = HaikuBrain()
    plan_content = Path(plan_file).read_text()
    extracted = brain.extract_tasks(plan_content)

    # Convert ExtractedTask to Task and find target
    tasks = [
        Task(
            id=t.id,
            title=t.title,
            description=t.description,
            file_path=None,
            acceptance_criteria=[],
            plan_file=plan_file,
            milestone_id=milestone_id,
        )
        for t in extracted
    ]
    target_task = next((t for t in tasks if t.id == task_id), None)

    if not target_task:
        console.print(f"[red]Task {task_id} not found in {plan_file}[/red]")
        return

    sandbox = SandboxManager()

    with tracer.start_as_current_span("orchestrator.task") as span:
        span.set_attribute("task.id", task_id)
        span.set_attribute("task.title", target_task.title)

        console.print(f"[bold]Task {task_id}:[/bold] {target_task.title}")
        console.print("Invoking Claude Code...")

        result = await run_task(
            target_task,
            sandbox,
            config,
            plan_file,
            human_guidance=guidance,
            model=model,
        )

        # Record telemetry on span
        span.set_attribute("task.status", result.status)
        span.set_attribute("claude.tokens", result.tokens_used)
        span.set_attribute("claude.cost_usd", result.cost_usd)
        span.set_attribute("claude.session_id", result.session_id)

        # Update metrics
        telemetry.tasks_counter.add(1, {"status": result.status})
        telemetry.tokens_counter.add(result.tokens_used)
        telemetry.cost_counter.add(result.cost_usd)

        # Output result
        status_color = {
            "completed": "green",
            "failed": "red",
            "needs_human": "yellow",
        }
        color = status_color[result.status]
        console.print(
            f"Task {task_id}: "
            f"[bold {color}]{result.status.upper()}[/bold {color}] "
            f"({result.duration_seconds:.0f}s, "
            f"{result.tokens_used / 1000:.1f}k tokens, "
            f"${result.cost_usd:.2f})"
        )

        # Show additional info for non-completed status
        if result.status == "needs_human" and result.question:
            console.print(f"\n[yellow]Question:[/yellow] {result.question}")
            if result.options:
                console.print(f"[yellow]Options:[/yellow] {', '.join(result.options)}")
            if result.recommendation:
                console.print(
                    f"[yellow]Recommendation:[/yellow] {result.recommendation}"
                )
        elif result.status == "failed" and result.error:
            console.print(f"\n[red]Error:[/red] {result.error}")


# Model aliases for the --model flag
MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-5-20251101",
}


@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.option("--notify/--no-notify", default=False, help="Send macOS notifications")
@click.option(
    "--llm-only",
    is_flag=True,
    help="Use LLM interpreter only for escalation detection, skip regex fast-path",
)
@click.option(
    "-m",
    "--model",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    default=None,
    help="Claude model for task execution (default: Claude's default)",
)
def run(plan_file: str, notify: bool, llm_only: bool, model: str | None) -> None:
    """Run all tasks in a milestone."""
    from orchestrator.runner import configure_interpreter

    configure_interpreter(llm_only=llm_only)
    model_id = MODEL_ALIASES[model] if model else None
    asyncio.run(_run_milestone(plan_file, resume=False, notify=notify, model=model_id))


@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.option("--notify/--no-notify", default=False, help="Send macOS notifications")
@click.option(
    "--llm-only",
    is_flag=True,
    help="Use LLM interpreter only for escalation detection, skip regex fast-path",
)
@click.option(
    "-m",
    "--model",
    type=click.Choice(["haiku", "sonnet", "opus"]),
    default=None,
    help="Claude model for task execution (default: Claude's default)",
)
def resume(plan_file: str, notify: bool, llm_only: bool, model: str | None) -> None:
    """Resume a previously interrupted milestone."""
    from orchestrator.runner import configure_interpreter

    configure_interpreter(llm_only=llm_only)

    config = OrchestratorConfig.from_env()
    milestone_id = Path(plan_file).stem

    # Check that state exists
    state = OrchestratorState.load(config.state_dir, milestone_id)
    if state is None:
        console.print(f"[red]No saved state for {milestone_id}[/red]")
        console.print("Use 'orchestrator run' to start a new run.")
        return

    if len(state.completed_tasks) == 0:
        console.print(
            "[yellow]No tasks completed yet. Use 'orchestrator run' instead.[/yellow]"
        )
        return

    console.print(f"Found state: {len(state.completed_tasks)} task(s) completed")

    model_id = MODEL_ALIASES[model] if model else None
    asyncio.run(_run_milestone(plan_file, resume=True, notify=notify, model=model_id))


async def _run_milestone(
    plan_file: str,
    resume: bool = False,
    notify: bool = False,
    model: str | None = None,
) -> None:
    """Internal async implementation of milestone execution."""
    config = OrchestratorConfig.from_env()
    tracer, meter = setup_telemetry(config)
    create_metrics(meter)

    milestone_id = Path(plan_file).stem

    # Acquire lock to prevent concurrent runs
    lock = MilestoneLock(config.state_dir, milestone_id)

    # Define callback for real-time streaming progress
    def on_tool_use(tool_name: str, tool_input: dict) -> None:
        """Display tool calls in real-time during task execution."""
        msg = format_tool_call(tool_name, tool_input)
        console.print(f"           {msg}")

    # Define callback for task completion display
    def on_task_complete(task: Task, task_result: TaskResult) -> None:
        """Display task summary after completion."""
        status_color = {
            "completed": "green",
            "failed": "red",
            "needs_human": "yellow",
        }
        color = status_color.get(task_result.status, "white")

        console.print(
            f"Task {task.id}: "
            f"[bold {color}]{task_result.status.upper()}[/bold {color}] "
            f"({task_result.duration_seconds:.0f}s, "
            f"{task_result.tokens_used / 1000:.1f}k tokens, "
            f"${task_result.cost_usd:.2f})"
        )

        # Display Claude's task summary (output field contains the summary)
        if task_result.output:
            console.print(f"\n{task_result.output}\n")

    try:
        with lock:
            if not resume:
                console.print(f"[bold]Starting milestone:[/bold] {milestone_id}")
            else:
                console.print(f"[bold]Resuming milestone:[/bold] {milestone_id}")

            result = await run_milestone(
                plan_path=plan_file,
                state_dir=config.state_dir,
                resume=resume,
                config=config,
                tracer=tracer,
                on_task_complete=on_task_complete,
                on_tool_use=on_tool_use,
                model=model,
            )

            # Output summary
            _print_milestone_summary(result)

            # Prompt for PR creation if milestone completed successfully
            if result.status == "completed":
                await _prompt_for_pr(result, config)

            # Send notification if requested
            if notify:
                _send_notification(result)

    except RuntimeError as e:
        # Lock held by another process
        console.print(f"[red]Error:[/red] {e}")


def _print_milestone_summary(result: MilestoneResult) -> None:
    """Print milestone completion summary."""
    status_color = {
        "completed": "green",
        "failed": "red",
        "needs_human": "yellow",
    }
    color = status_color[result.status]

    console.print(f"\n[bold {color}]Milestone {result.status.upper()}[/bold {color}]")
    console.print(f"  Tasks: {result.completed_tasks}/{result.total_tasks} completed")
    console.print(f"  Duration: {_format_duration(result.total_duration_seconds)}")
    console.print(f"  Tokens: {result.total_tokens / 1000:.1f}k")
    console.print(f"  Cost: ${result.total_cost_usd:.2f}")

    if result.failed_tasks > 0:
        console.print(f"  [red]Failed: {result.failed_tasks}[/red]")


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def _send_notification(result: MilestoneResult) -> None:
    """Send macOS notification for milestone completion."""
    try:
        from orchestrator.notifications import send_notification

        send_notification(
            title=f"Milestone {result.status}",
            message=f"{result.completed_tasks}/{result.total_tasks} tasks completed",
        )
    except ImportError:
        # notifications module not implemented yet (Task 3.7)
        pass


async def _prompt_for_pr(result: MilestoneResult, config: OrchestratorConfig) -> None:
    """Prompt user to create PR and invoke Claude if confirmed."""
    if click.confirm("\nCreate PR for this milestone?", default=True):
        console.print("[bold]Invoking Claude to create PR...[/bold]")

        # Create sandbox for PR creation
        sandbox = SandboxManager(
            container_name=config.sandbox_container,
            workspace_path=config.workspace_path,
        )

        pr_result = await create_milestone_pr(
            sandbox=sandbox,
            milestone_id=result.state.milestone_id,
            completed_tasks=result.state.completed_tasks,
            total_cost_usd=result.total_cost_usd,
            base_branch=result.state.starting_branch,
        )

        if pr_result.is_error:
            console.print(f"[red]PR creation failed:[/red] {pr_result.result}")
        else:
            console.print(pr_result.result)


@cli.command()
@click.option("--milestone", "-m", default=None, help="Filter by milestone name")
@click.option("--limit", "-n", default=10, help="Number of runs to show")
def history(milestone: str | None, limit: int) -> None:
    """Show history of milestone runs."""
    config = OrchestratorConfig.from_env()

    # Find all state files
    if not config.state_dir.exists():
        console.print("[yellow]No state directory found[/yellow]")
        return

    state_files = list(config.state_dir.glob("*_state.json"))

    if not state_files:
        console.print("[yellow]No milestone runs found[/yellow]")
        return

    # Load and filter states
    runs: list[OrchestratorState] = []
    for path in state_files:
        milestone_id = path.stem.replace("_state", "")
        state = OrchestratorState.load(config.state_dir, milestone_id)
        if state:
            if milestone is None or milestone in state.milestone_id:
                runs.append(state)

    # Sort by date descending (most recent first)
    runs.sort(key=lambda s: s.started_at, reverse=True)
    runs = runs[:limit]

    if not runs:
        console.print("[yellow]No matching milestone runs found[/yellow]")
        return

    # Display table
    table = Table(title="Milestone History")
    table.add_column("Milestone")
    table.add_column("Started")
    table.add_column("Tasks")
    table.add_column("E2E")
    table.add_column("Cost")

    for run in runs:
        total_cost = sum(r.get("cost_usd", 0) for r in run.task_results.values())
        total_tasks = len(run.completed_tasks) + len(run.failed_tasks)
        table.add_row(
            run.milestone_id,
            run.started_at.strftime("%Y-%m-%d %H:%M"),
            f"{len(run.completed_tasks)}/{total_tasks}",
            run.e2e_status or "-",
            f"${total_cost:.2f}",
        )

    console.print(table)


@cli.command()
@click.option("--since", default=None, help="Show costs since date (YYYY-MM-DD)")
@click.option("--by-milestone/--total", default=True, help="Break down by milestone")
def costs(since: str | None, by_milestone: bool) -> None:
    """Show cost summary."""
    from collections import defaultdict
    from datetime import datetime

    config = OrchestratorConfig.from_env()

    # Parse since date
    since_date = datetime.fromisoformat(since) if since else datetime.min

    # Check for state directory
    if not config.state_dir.exists():
        console.print("[yellow]No state directory found[/yellow]")
        return

    state_files = list(config.state_dir.glob("*_state.json"))

    if not state_files:
        console.print("[yellow]No milestone runs found[/yellow]")
        return

    # Aggregate costs from state files
    costs_by_milestone: dict[str, float] = defaultdict(float)
    total_cost = 0.0

    for path in state_files:
        milestone_id = path.stem.replace("_state", "")
        state = OrchestratorState.load(config.state_dir, milestone_id)
        if state and state.started_at >= since_date:
            cost = sum(r.get("cost_usd", 0) for r in state.task_results.values())
            costs_by_milestone[state.milestone_id] += cost
            total_cost += cost

    if not costs_by_milestone:
        console.print("[yellow]No matching milestone runs found[/yellow]")
        return

    if by_milestone:
        table = Table(title="Costs by Milestone")
        table.add_column("Milestone")
        table.add_column("Cost", justify="right")

        for milestone, cost in sorted(costs_by_milestone.items()):
            table.add_row(milestone, f"${cost:.2f}")

        table.add_row("[bold]Total[/bold]", f"[bold]${total_cost:.2f}[/bold]")
        console.print(table)
    else:
        console.print(f"Total cost: ${total_cost:.2f}")


def main() -> None:
    """Main entry point for the orchestrator CLI."""
    cli()


if __name__ == "__main__":
    main()
