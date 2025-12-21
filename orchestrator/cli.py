"""CLI for the Orchestrator.

Provides command-line interface for autonomous task execution.
"""

import asyncio
from pathlib import Path

import click
from rich.console import Console

from orchestrator import telemetry
from orchestrator.config import OrchestratorConfig
from orchestrator.lock import MilestoneLock
from orchestrator.milestone_runner import (
    MilestoneResult,
    create_milestone_pr,
    run_milestone,
)
from orchestrator.models import Task, TaskResult
from orchestrator.plan_parser import parse_plan
from orchestrator.sandbox import SandboxManager, format_tool_call
from orchestrator.state import OrchestratorState
from orchestrator.task_runner import run_task
from orchestrator.telemetry import create_metrics, setup_telemetry

console = Console()


@click.group()
@click.version_option(package_name="orchestrator")
def cli() -> None:
    """Orchestrator - Autonomous task execution for KTRDR."""
    pass


@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.argument("task_id")
@click.option("--guidance", "-g", help="Additional guidance for Claude")
def task(plan_file: str, task_id: str, guidance: str | None) -> None:
    """Execute a single task from a plan file."""
    asyncio.run(_run_task(plan_file, task_id, guidance))


async def _run_task(plan_file: str, task_id: str, guidance: str | None) -> None:
    """Internal async implementation of task execution."""
    config = OrchestratorConfig.from_env()
    tracer, meter = setup_telemetry(config)
    create_metrics(meter)

    # Parse plan and find task
    tasks = parse_plan(plan_file)
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
            target_task, sandbox, config, plan_file, human_guidance=guidance
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


@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.option("--notify/--no-notify", default=False, help="Send macOS notifications")
def run(plan_file: str, notify: bool) -> None:
    """Run all tasks in a milestone."""
    asyncio.run(_run_milestone(plan_file, resume=False, notify=notify))


@cli.command()
@click.argument("plan_file", type=click.Path(exists=True))
@click.option("--notify/--no-notify", default=False, help="Send macOS notifications")
def resume(plan_file: str, notify: bool) -> None:
    """Resume a previously interrupted milestone."""
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

    asyncio.run(_run_milestone(plan_file, resume=True, notify=notify))


async def _run_milestone(
    plan_file: str, resume: bool = False, notify: bool = False
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
        )

        if pr_result.is_error:
            console.print(f"[red]PR creation failed:[/red] {pr_result.result}")
        else:
            console.print(pr_result.result)


def main() -> None:
    """Main entry point for the orchestrator CLI."""
    cli()


if __name__ == "__main__":
    main()
