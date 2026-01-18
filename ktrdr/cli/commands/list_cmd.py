"""List command implementation.

Implements the `ktrdr list <resource>` command that lists strategies, models,
and checkpoints in a table format.

Replaces the old `ktrdr strategies list` command with a more consistent pattern.

PERFORMANCE NOTE: Heavy imports (AsyncCLIClient, Console, Table) are deferred
inside command functions to keep CLI startup fast.
"""

import typer

from ktrdr.cli.telemetry import trace_cli_command

# Create a subcommand group
list_app = typer.Typer(name="list", help="List resources")


@list_app.command("strategies")
@trace_cli_command("list_strategies")
def list_strategies(ctx: typer.Context) -> None:
    """List available strategies.

    Shows all strategies in the system with their name, status, symbols, and timeframes.

    Examples:
        ktrdr list strategies

        ktrdr --json list strategies
    """
    # Lazy imports for fast CLI startup
    import asyncio
    import json

    from rich.console import Console
    from rich.table import Table

    from ktrdr.cli.client import AsyncCLIClient
    from ktrdr.cli.output import print_error
    from ktrdr.cli.state import CLIState

    state: CLIState = ctx.obj
    console = Console()

    async def _fetch() -> None:
        """Fetch and display strategies list."""
        async with AsyncCLIClient() as client:
            result = await client.get("/strategies")

        # API returns {"strategies": [...]}
        strategies = result.get("strategies", [])

        if state.json_mode:
            print(json.dumps(strategies))
            return

        if not strategies:
            console.print("No strategies found")
            return

        table = Table(title="Strategies")
        table.add_column("Name", style="cyan")
        table.add_column("Status")
        table.add_column("Symbol")
        table.add_column("Timeframe")

        for s in strategies:
            # Handle both v2 (symbol, timeframe) and v3 (training_data.symbols) formats
            td = s.get("training_data", s.get("data", {}))
            if td:
                symbols = td.get("symbols", [])
                timeframes = td.get("timeframes", [])
                symbol = ", ".join(symbols) if symbols else s.get("symbol", "")
                timeframe = (
                    ", ".join(timeframes) if timeframes else s.get("timeframe", "")
                )
            else:
                symbol = s.get("symbol", "")
                timeframe = s.get("timeframe", "")

            status = s.get("training_status", "")
            # Color-code status
            if status == "trained":
                status_display = f"[green]{status}[/green]"
            elif status == "training":
                status_display = f"[yellow]{status}[/yellow]"
            elif status == "failed":
                status_display = f"[red]{status}[/red]"
            else:
                status_display = status

            table.add_row(
                s.get("name", ""),
                status_display,
                symbol,
                timeframe,
            )

        console.print(table)

    try:
        asyncio.run(_fetch())
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None


@list_app.command("models")
@trace_cli_command("list_models")
def list_models(ctx: typer.Context) -> None:
    """List trained models.

    Shows all trained models with their name, strategy, creation date, and performance.

    Examples:
        ktrdr list models

        ktrdr --json list models
    """
    # Lazy imports for fast CLI startup
    import asyncio
    import json

    from rich.console import Console
    from rich.table import Table

    from ktrdr.cli.client import AsyncCLIClient
    from ktrdr.cli.output import print_error
    from ktrdr.cli.state import CLIState

    state: CLIState = ctx.obj
    console = Console()

    async def _fetch() -> None:
        """Fetch and display models list."""
        async with AsyncCLIClient() as client:
            result = await client.get("/models")

        # API returns {"models": [...]}
        models = result.get("models", [])

        if state.json_mode:
            print(json.dumps(models))
            return

        if not models:
            console.print("No models found")
            return

        table = Table(title="Models")
        table.add_column("Name", style="cyan")
        table.add_column("Symbol")
        table.add_column("Timeframe")
        table.add_column("Created")
        table.add_column("Accuracy")

        for m in models:
            # Format created date - take first 10 chars (YYYY-MM-DD)
            created = m.get("created_at", "")
            if created and len(created) >= 10:
                created = created[:10]

            # Format accuracy
            accuracy = m.get("training_accuracy")
            if accuracy is not None:
                accuracy_display = f"{accuracy:.1%}"
            else:
                accuracy_display = "-"

            table.add_row(
                m.get("model_name", ""),
                m.get("symbol") or "-",
                m.get("timeframe") or "-",
                created,
                accuracy_display,
            )

        console.print(table)

    try:
        asyncio.run(_fetch())
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None


@list_app.command("checkpoints")
@trace_cli_command("list_checkpoints")
def list_checkpoints(ctx: typer.Context) -> None:
    """List available checkpoints.

    Shows all checkpoints with their operation ID, type, creation date, and size.

    Examples:
        ktrdr list checkpoints

        ktrdr --json list checkpoints
    """
    # Lazy imports for fast CLI startup
    import asyncio
    import json

    from rich.console import Console
    from rich.table import Table

    from ktrdr.cli.client import AsyncCLIClient
    from ktrdr.cli.output import print_error
    from ktrdr.cli.state import CLIState

    state: CLIState = ctx.obj
    console = Console()

    async def _fetch() -> None:
        """Fetch and display checkpoints list."""
        async with AsyncCLIClient() as client:
            result = await client.get("/checkpoints")

        # API returns {"data": [...], "total_count": N}
        checkpoints = result.get("data", [])

        if state.json_mode:
            print(json.dumps(checkpoints))
            return

        if not checkpoints:
            console.print("No checkpoints found")
            return

        table = Table(title="Checkpoints")
        table.add_column("Operation ID", style="cyan")
        table.add_column("Type")
        table.add_column("Created")
        table.add_column("Summary")
        table.add_column("Size")

        for c in checkpoints:
            # Truncate operation ID for display
            op_id = c.get("operation_id", "")
            if len(op_id) > 16:
                op_id = op_id[:16] + "..."

            # Format created date
            created = c.get("created_at", "")
            if created and len(created) >= 16:
                created = created[:16]

            # Format state summary
            state_summary = c.get("state_summary", {})
            if "epoch" in state_summary:
                summary = f"epoch {state_summary['epoch']}"
            elif "bar_index" in state_summary:
                summary = f"bar {state_summary['bar_index']}"
            elif "step" in state_summary:
                summary = f"step {state_summary['step']}"
            else:
                summary = "-"

            # Format size
            size_bytes = c.get("artifacts_size_bytes")
            if size_bytes:
                if size_bytes >= 1_000_000:
                    size = f"{size_bytes / 1_000_000:.1f} MB"
                elif size_bytes >= 1_000:
                    size = f"{size_bytes / 1_000:.1f} KB"
                else:
                    size = f"{size_bytes} B"
            else:
                size = "-"

            table.add_row(
                op_id,
                c.get("checkpoint_type", ""),
                created,
                summary,
                size,
            )

        console.print(table)

    try:
        asyncio.run(_fetch())
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
