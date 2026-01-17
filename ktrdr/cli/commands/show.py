"""Show command implementation.

Implements the `ktrdr show` command for displaying market data and strategy features.

Subcommands:
- `ktrdr show <symbol> [timeframe]` - Show market data
- `ktrdr show features <strategy>` - Show strategy features
"""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.client import AsyncCLIClient
from ktrdr.cli.output import print_error
from ktrdr.cli.state import CLIState
from ktrdr.cli.telemetry import trace_cli_command

console = Console()

# Create show command group with callback for data display
show_app = typer.Typer(name="show", help="Show data and details")


@show_app.callback(invoke_without_command=True)
def show_callback(ctx: typer.Context) -> None:
    """Show data and details.

    For market data:
        ktrdr show data AAPL
        ktrdr show data AAPL 1d

    For strategy features:
        ktrdr show features ./strategies/momentum.yaml
    """
    # If a subcommand was invoked, let it run
    if ctx.invoked_subcommand is not None:
        return

    # No subcommand - show help
    console.print("Usage: ktrdr show [COMMAND]")
    console.print()
    console.print("Commands:")
    console.print("  data      Show market data for a symbol")
    console.print("  features  Show resolved features for a strategy")
    console.print()
    console.print("Examples:")
    console.print("  ktrdr show data AAPL")
    console.print("  ktrdr show data AAPL 1d")
    console.print("  ktrdr show features ./strategies/momentum.yaml")


@show_app.command("data")
@trace_cli_command("show_data")
def show_data(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="Symbol (e.g., AAPL)"),
    timeframe: str = typer.Argument("1h", help="Timeframe (e.g., 1h, 1d)"),
) -> None:
    """Show market data for a symbol.

    Examples:
        ktrdr show data AAPL
        ktrdr show data AAPL 1d
    """
    state: CLIState = ctx.obj

    try:
        asyncio.run(_show_data(state, symbol, timeframe))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None


async def _show_data(state: CLIState, symbol: str, timeframe: str) -> None:
    """Fetch and display market data."""
    async with AsyncCLIClient() as client:
        result = await client.get(f"/data/{symbol}/{timeframe}")

    # API returns {"success": true, "data": {"dates": [...], "ohlcv": [...]}}
    data = result.get("data", {})
    dates = data.get("dates", [])
    ohlcv = data.get("ohlcv", [])

    if state.json_mode:
        print(json.dumps(data))
        return

    if not dates or not ohlcv:
        console.print(f"No data available for {symbol} {timeframe}")
        return

    table = Table(title=f"{symbol} {timeframe}")
    table.add_column("Date", style="cyan")
    table.add_column("Open", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Low", justify="right")
    table.add_column("Close", justify="right")
    table.add_column("Volume", justify="right")

    # Show last 10 bars for display
    display_count = min(10, len(dates))
    for i in range(-display_count, 0):
        date = dates[i]
        bar = ohlcv[i]

        # Format date - take first 16 chars (YYYY-MM-DDTHH:MM)
        if len(date) >= 16:
            date = date[:16]

        table.add_row(
            date,
            f"{bar[0]:.2f}",
            f"{bar[1]:.2f}",
            f"{bar[2]:.2f}",
            f"{bar[3]:.2f}",
            f"{bar[4]:,.0f}",
        )

    console.print(table)


@show_app.command("features")
@trace_cli_command("show_features")
def show_features(
    ctx: typer.Context,
    strategy: str = typer.Argument(..., help="Strategy path or name"),
) -> None:
    """Show resolved features for a strategy.

    Displays the NN input features that will be generated from the strategy's
    fuzzy sets and indicators.

    Examples:
        ktrdr show features ./strategies/momentum.yaml
        ktrdr show features strategies/my_strategy.yaml
    """
    state: CLIState = ctx.obj

    try:
        _show_features_local(state, strategy)
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None


def _show_features_local(state: CLIState, strategy_path: str) -> None:
    """Load and display strategy features from local file."""
    from ktrdr.config.feature_resolver import FeatureResolver
    from ktrdr.config.strategy_loader import StrategyConfigurationLoader

    path = Path(strategy_path)
    if not path.exists():
        raise FileNotFoundError(f"Strategy file not found: {strategy_path}")

    # Load strategy - must be v3 format
    loader = StrategyConfigurationLoader()
    config = loader.load_v3_strategy(path)

    # Resolve features
    resolver = FeatureResolver()
    features = resolver.resolve(config)

    if state.json_mode:
        # Output JSON format
        features_data = [
            {
                "feature_id": f.feature_id,
                "timeframe": f.timeframe,
                "fuzzy_set": f.fuzzy_set_id,
                "membership": f.membership_name,
            }
            for f in features
        ]
        print(
            json.dumps(
                {
                    "strategy": config.name,
                    "features": features_data,
                    "count": len(features),
                }
            )
        )
        return

    # Display header
    console.print(f"Strategy: [cyan]{config.name}[/cyan]")
    console.print(f"Features ({len(features)} total):")
    console.print()

    # Display features in a table
    table = Table(title=f"Features: {config.name}")
    table.add_column("Feature ID", style="cyan")
    table.add_column("Timeframe")
    table.add_column("Fuzzy Set")
    table.add_column("Membership")

    for f in features:
        table.add_row(
            f.feature_id,
            f.timeframe,
            f.fuzzy_set_id,
            f.membership_name,
        )

    console.print(table)
