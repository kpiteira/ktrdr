"""Research command implementation.

Implements the `ktrdr research <goal>` command that triggers an AI research
cycle using the agent trigger API. Supports fire-and-forget (default) or
follow mode with --follow flag.

PERFORMANCE NOTE: Heavy imports (AsyncCLIClient, Console, agent_commands) are
deferred inside the function body to keep CLI startup fast.
"""

from typing import Optional

import typer

from ktrdr.cli.telemetry import trace_cli_command


@trace_cli_command("research")
def research(
    ctx: typer.Context,
    goal: str = typer.Argument(..., help="Research goal or brief"),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use: opus, sonnet, haiku, or full model ID",
    ),
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="Follow progress until completion",
    ),
) -> None:
    """Start an AI research cycle.

    Triggers an agent to begin autonomous research based on the goal.
    By default, returns immediately with the operation ID. Use --follow
    to watch progress until completion.

    Examples:
        ktrdr research "build a momentum strategy for AAPL"

        ktrdr research "analyze volatility patterns" --follow

        ktrdr research "test strategy" --model haiku -f
    """
    # Lazy imports for fast CLI startup
    import asyncio

    from rich.console import Console

    from ktrdr.cli.client import AsyncCLIClient
    from ktrdr.cli.helpers.agent_monitor import monitor_agent_cycle
    from ktrdr.cli.output import print_error, print_operation_started
    from ktrdr.cli.state import CLIState

    state: CLIState = ctx.obj
    console = Console()

    async def _research_async() -> None:
        """Async implementation of research command."""
        # Build request body
        json_data: dict = {"brief": goal}
        if model:
            json_data["model"] = model

        async with AsyncCLIClient() as client:
            result = await client.post("/agent/trigger", json=json_data)

        if not result.get("triggered"):
            reason = result.get("reason", "unknown")
            raise RuntimeError(f"Could not start research: {reason}")

        operation_id = result["operation_id"]

        if follow:
            # Show startup info then enter monitoring mode
            console.print("\n[green]Research cycle started![/green]")
            console.print(f"  Operation ID: {operation_id}")
            if result.get("model"):
                console.print(f"  Model: {result['model']}")
            console.print()

            # Reuse existing nested progress UX from agent_commands.py
            await monitor_agent_cycle(operation_id)
        else:
            # Fire-and-forget mode: print operation ID and return
            print_operation_started("research", operation_id, state)

    try:
        asyncio.run(_research_async())
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
