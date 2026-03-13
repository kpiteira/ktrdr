"""Ensemble backtest CLI commands.

Implements `ktrdr ensemble backtest` for running regime-routed
ensemble backtests from YAML configuration files.

PERFORMANCE NOTE: Heavy imports are deferred inside the function body.
"""

from pathlib import Path
from typing import Optional

import typer

ensemble_app = typer.Typer(
    name="ensemble",
    help="Ensemble backtest commands.",
)


@ensemble_app.command("backtest")
def backtest(
    config_path: str = typer.Argument(
        ..., help="Path to ensemble configuration YAML file"
    ),
    start_date: str = typer.Option(..., "--start-date", help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end-date", help="End date (YYYY-MM-DD)"),
    symbol: Optional[str] = typer.Option(
        None, "--symbol", help="Trading symbol (default: EURUSD)"
    ),
    timeframe: Optional[str] = typer.Option(
        None, "--timeframe", help="Timeframe (default: 1h)"
    ),
    initial_capital: float = typer.Option(
        100000.0, "--capital", help="Initial capital"
    ),
) -> None:
    """Run a regime-routed ensemble backtest.

    Loads an ensemble configuration YAML, loads all referenced model bundles,
    and runs a backtest where a regime classifier gates routing to per-regime
    signal models.

    Example:
        ktrdr ensemble backtest ensemble_config.yaml --start-date 2024-01-01 --end-date 2024-06-01
    """
    import asyncio

    from rich.console import Console
    from rich.table import Table

    from ktrdr.backtesting.engine import BacktestConfig
    from ktrdr.backtesting.ensemble_runner import EnsembleBacktestRunner
    from ktrdr.config.ensemble_config import EnsembleConfiguration

    console = Console()

    # 1. Load ensemble config
    config_file = Path(config_path)
    if not config_file.exists():
        console.print(f"[red]Error: Config file not found: {config_path}[/red]")
        raise typer.Exit(code=1)

    try:
        ensemble_config = EnsembleConfiguration.from_yaml(config_file)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(code=1) from None

    console.print(
        f"[bold]Ensemble:[/bold] {ensemble_config.name} "
        f"({len(ensemble_config.models)} models)"
    )

    # 2. Create backtest config
    backtest_config = BacktestConfig(
        strategy_config_path="",
        model_path=None,
        symbol=symbol or "EURUSD",
        timeframe=timeframe or "1h",
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )

    # 3. Run ensemble backtest
    runner = EnsembleBacktestRunner(
        ensemble_config=ensemble_config,
        backtest_config=backtest_config,
    )

    try:
        results = asyncio.run(runner.run())
    except FileNotFoundError as e:
        console.print(f"[red]Error: Model not found: {e}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"[red]Error running ensemble backtest: {e}[/red]")
        raise typer.Exit(code=1) from None

    # 4. Display results
    console.print()
    console.print("[bold green]Ensemble Backtest Complete[/bold green]")
    console.print(f"  Symbol: {results.symbol}")
    console.print(f"  Timeframe: {results.timeframe}")
    console.print(f"  Bars: {results.total_bars}")
    console.print(f"  Trades: {len(results.trades)}")
    console.print(f"  Transitions: {results.transition_count}")
    console.print(f"  Time: {results.execution_time_seconds:.1f}s")

    # Per-regime breakdown table
    console.print()
    table = Table(title="Per-Regime Breakdown")
    table.add_column("Regime", style="cyan")
    table.add_column("Bars", justify="right")
    table.add_column("Trades", justify="right")

    for regime, metrics in results.per_regime_metrics.items():
        table.add_row(
            regime,
            str(metrics.get("bars", 0)),
            str(metrics.get("trades", 0)),
        )

    console.print(table)

    # Transition sequence (if any)
    if results.regime_sequence:
        console.print()
        trans_table = Table(title="Regime Transitions")
        trans_table.add_column("Timestamp")
        trans_table.add_column("From", style="yellow")
        trans_table.add_column("To", style="green")

        for t in results.regime_sequence[:20]:  # Show first 20
            trans_table.add_row(
                str(t.get("timestamp", "")),
                str(t.get("from", "")),
                str(t.get("to", "")),
            )

        if len(results.regime_sequence) > 20:
            trans_table.add_row(
                f"... and {len(results.regime_sequence) - 20} more", "", ""
            )
        console.print(trans_table)
