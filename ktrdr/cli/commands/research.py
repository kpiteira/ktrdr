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
    goal: Optional[str] = typer.Argument(
        None, help="Research goal or brief (required unless --strategy is provided)"
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use: opus, sonnet, haiku, or full model ID",
    ),
    strategy: Optional[str] = typer.Option(
        None,
        "--strategy",
        "-s",
        help="Existing v3 strategy name to train directly (skips design phase)",
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

    Use --strategy to skip the design phase and train an existing strategy directly.

    Examples:
        ktrdr research "build a momentum strategy for AAPL"

        ktrdr research "analyze volatility patterns" --follow

        ktrdr research "test strategy" --model haiku -f

        ktrdr research --strategy v3_minimal --follow
    """
    # Normalize empty/whitespace strings to None for consistent validation
    if goal is not None and not goal.strip():
        goal = None
    if strategy is not None and not strategy.strip():
        strategy = None

    # Validate: either goal or strategy must be provided (but not both)
    if goal is None and strategy is None:
        raise typer.BadParameter(
            "Either a goal argument or --strategy option is required."
        )
    if goal is not None and strategy is not None:
        raise typer.BadParameter(
            "Cannot specify both goal and --strategy. "
            "Use goal to design a new strategy, or --strategy to train an existing one."
        )
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
        json_data: dict = {}
        if strategy:
            json_data["strategy"] = strategy
        elif goal:
            json_data["brief"] = goal
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
