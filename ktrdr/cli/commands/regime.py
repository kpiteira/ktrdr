"""Regime analysis CLI commands.

Implements `ktrdr regime analyze` for analyzing market regime labels
on cached OHLCV data.

PERFORMANCE NOTE: Heavy imports are deferred inside the function body.
"""

from typing import Optional

import typer

regime_app = typer.Typer(
    name="regime",
    help="Market regime analysis commands.",
)


@regime_app.command("analyze")
def analyze(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., EURUSD)"),
    timeframe: str = typer.Argument(..., help="Timeframe (e.g., 1h, 1d)"),
    start_date: Optional[str] = typer.Option(
        None, "--start-date", help="Start date (YYYY-MM-DD)"
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end-date", help="End date (YYYY-MM-DD)"
    ),
    macro_atr_mult: float = typer.Option(
        3.0, "--macro-atr-mult", help="ATR multiplier for macro zigzag threshold"
    ),
    micro_atr_mult: float = typer.Option(
        1.0, "--micro-atr-mult", help="ATR multiplier for micro zigzag threshold"
    ),
    atr_period: int = typer.Option(14, "--atr-period", help="ATR calculation period"),
    vol_crisis_threshold: float = typer.Option(
        2.0, "--vol-crisis-threshold", help="RV ratio threshold for volatile regime"
    ),
    vol_lookback: int = typer.Option(
        120, "--vol-lookback", help="Bars for historical volatility baseline"
    ),
    progression_tolerance: float = typer.Option(
        0.5,
        "--progression-tolerance",
        help="Fraction of pivot pairs that must progress",
    ),
) -> None:
    """Analyze market regime labels for a symbol/timeframe.

    Uses multi-scale zigzag (macro + micro) to identify market regimes.
    Auto-adapts to any timeframe/instrument via ATR-scaled thresholds.

    Example:
        ktrdr regime analyze EURUSD 1h --start-date 2019-01-01 --end-date 2024-01-01
    """
    from rich.console import Console
    from rich.table import Table

    from ktrdr.data.repository import DataRepository

    # Import directly from submodule — neither regime_labeler nor
    # multi_scale_regime_labeler imports torch, so this is safe without
    # going through ktrdr.training.__init__ (which pulls ModelTrainer/torch).
    from ktrdr.training.multi_scale_regime_labeler import MultiScaleRegimeLabeler

    console = Console()

    try:
        repo = DataRepository()
        data = repo.load_from_cache(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        console.print(f"[red]Error loading data: {e}[/red]")
        raise typer.Exit(1) from None

    console.print(
        f"\nAnalyzing regime labels for [bold]{symbol} {timeframe}[/bold] "
        f"({len(data)} bars)"
    )

    labeler = MultiScaleRegimeLabeler(
        macro_atr_mult=macro_atr_mult,
        micro_atr_mult=micro_atr_mult,
        atr_period=atr_period,
        vol_lookback=vol_lookback,
        vol_crisis_threshold=vol_crisis_threshold,
        progression_tolerance=progression_tolerance,
    )

    try:
        labels = labeler.generate_labels(data)
    except Exception as e:
        console.print(f"[red]Error generating labels: {e}[/red]")
        raise typer.Exit(1) from None

    stats = labeler.analyze_labels(labels, data)

    # Parameters table
    console.print("\n[bold]Parameters[/bold]")
    params_table = Table(show_header=False, padding=(0, 2))
    params_table.add_column("Param", style="dim")
    params_table.add_column("Value")
    params_table.add_row("Macro ATR mult", f"{macro_atr_mult}")
    params_table.add_row("Micro ATR mult", f"{micro_atr_mult}")
    params_table.add_row("ATR period", f"{atr_period}")
    params_table.add_row("Vol crisis threshold", f"{vol_crisis_threshold}")
    params_table.add_row("Vol lookback", f"{vol_lookback} bars")
    params_table.add_row("Progression tolerance", f"{progression_tolerance}")
    console.print(params_table)

    # Distribution table
    console.print("\n[bold]Distribution[/bold]")
    dist_table = Table()
    dist_table.add_column("Regime")
    dist_table.add_column("Fraction", justify="right")
    dist_table.add_column("Bars", justify="right")
    for regime, frac in sorted(stats.distribution.items()):
        bars = int(frac * stats.total_bars)
        dist_table.add_row(regime, f"{frac:.1%}", str(bars))
    console.print(dist_table)

    # Duration / persistence table
    console.print("\n[bold]Mean Duration (Persistence)[/bold]")
    dur_table = Table()
    dur_table.add_column("Regime")
    dur_table.add_column("Mean Duration (bars)", justify="right")
    for regime, dur in sorted(stats.mean_duration_bars.items()):
        dur_table.add_row(regime, f"{dur:.1f}")
    console.print(dur_table)

    # Return by regime table
    console.print("\n[bold]Mean Forward Return by Regime[/bold]")
    ret_table = Table()
    ret_table.add_column("Regime")
    ret_table.add_column("Mean Return", justify="right")
    for regime, ret in sorted(stats.mean_return_by_regime.items()):
        style = "green" if ret > 0 else "red" if ret < 0 else ""
        ret_table.add_row(regime, f"{ret:+.4%}", style=style)
    console.print(ret_table)

    # Transition matrix
    if stats.transition_matrix:
        console.print("\n[bold]Transition Matrix[/bold]")
        all_regimes = sorted(
            set().union(*[set(row.keys()) for row in stats.transition_matrix.values()])
            | set(stats.transition_matrix.keys())
        )
        trans_table = Table()
        trans_table.add_column("From \\ To", style="bold")
        for regime in all_regimes:
            trans_table.add_column(regime, justify="right")

        for from_regime in all_regimes:
            row = stats.transition_matrix.get(from_regime, {})
            cells = [f"{row.get(to, 0.0):.2f}" for to in all_regimes]
            trans_table.add_row(from_regime, *cells)

        console.print(trans_table)

    # Summary
    console.print(
        f"\n[bold]Summary:[/bold] {stats.total_bars} labeled bars, "
        f"{stats.total_transitions} transitions"
    )
