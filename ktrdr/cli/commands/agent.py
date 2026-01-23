"""Agent command implementation.

Implements the `ktrdr agent` subcommand group for agent-related operations
including status display for multi-research observability.

PERFORMANCE NOTE: Heavy imports (AsyncCLIClient, Console) are deferred inside
the function body to keep CLI startup fast.
"""

import typer

from ktrdr.cli.telemetry import trace_cli_command

agent_app = typer.Typer(
    name="agent",
    help="Agent research operations and status.",
)


def format_duration(seconds: int) -> str:
    """Format seconds as Xm Ys."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}m {secs:02d}s"


@agent_app.command("status")
@trace_cli_command("agent.status")
def status(ctx: typer.Context) -> None:
    """Show status of all active agent researches.

    Displays active research operations with their phases, worker
    utilization, budget remaining, and capacity information.

    Examples:
        ktrdr agent status
    """
    # Lazy imports for fast CLI startup
    import asyncio
    import json

    from rich.console import Console

    from ktrdr.cli.client import AsyncCLIClient
    from ktrdr.cli.output import print_error
    from ktrdr.cli.state import CLIState

    state: CLIState = ctx.obj
    console = Console()

    async def _show_agent_status() -> None:
        """Show agent status with all active researches."""
        async with AsyncCLIClient() as client:
            data = await client.get("/agent/status")

        if state.json_mode:
            print(json.dumps(data))
            return

        if data["status"] == "idle":
            console.print("Status: [dim]idle[/dim]")
            if data.get("last_cycle"):
                last = data["last_cycle"]
                console.print(f"Last cycle: {last['operation_id']} ({last['outcome']})")
        else:
            active = data["active_researches"]
            console.print(f"Active researches: {len(active)}\n")

            for r in active:
                strategy = r.get("strategy_name") or "-"
                duration = format_duration(r["duration_seconds"])
                console.print(
                    f"  {r['operation_id']}  {r['phase']:<12} "
                    f"strategy: {strategy:<20} ({duration})"
                )

            console.print()

        # Workers
        workers = data.get("workers", {})
        training = workers.get("training", {})
        backtest = workers.get("backtesting", {})
        console.print(
            f"Workers: training {training.get('busy', 0)}/{training.get('total', 0)}, "
            f"backtest {backtest.get('busy', 0)}/{backtest.get('total', 0)}"
        )

        # Budget
        budget = data.get("budget", {})
        remaining = budget.get("remaining", 0)
        console.print(f"Budget: ${remaining:.2f} remaining today")

        # Capacity
        capacity = data.get("capacity", {})
        console.print(
            f"Capacity: {capacity.get('active', 0)}/{capacity.get('limit', 0)} researches"
        )

    try:
        asyncio.run(_show_agent_status())
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
