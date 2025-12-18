"""CLI for the Orchestrator.

Provides command-line interface for autonomous task execution.
"""

import asyncio

import click
from rich.console import Console

from orchestrator import telemetry
from orchestrator.config import OrchestratorConfig
from orchestrator.plan_parser import parse_plan
from orchestrator.sandbox import SandboxManager
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

        result = await run_task(target_task, sandbox, config, guidance)

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


def main() -> None:
    """Main entry point for the orchestrator CLI."""
    cli()


if __name__ == "__main__":
    main()
