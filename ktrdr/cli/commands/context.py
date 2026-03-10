"""Context analysis command implementation.

Implements `ktrdr context analyze` for generating and analyzing daily trend
direction labels. Used by Thread 2 (Multi-TF Context) to validate whether
daily context provides complementary information to hourly regime detection.

PERFORMANCE NOTE: Heavy imports are deferred inside function bodies.
"""

from typing import Optional

import typer

from ktrdr.cli.telemetry import trace_cli_command

context_app = typer.Typer(
    name="context",
    help="Multi-timeframe context analysis.",
)

# Label name mapping
_LABEL_NAMES = {0: "Bullish", 1: "Bearish", 2: "Neutral"}


@context_app.command("analyze")
@trace_cli_command("context.analyze")
def analyze(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="Symbol (e.g., EURUSD)"),
    timeframe: str = typer.Argument(
        "1d", help="Timeframe for context labels (should be 1d)"
    ),
    start_date: Optional[str] = typer.Option(
        None, "--start-date", help="Start date (YYYY-MM-DD)"
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end-date", help="End date (YYYY-MM-DD)"
    ),
    horizon: int = typer.Option(5, "--horizon", help="Forward-looking horizon in bars"),
    bullish_threshold: float = typer.Option(
        0.005, "--bullish-threshold", help="Bullish return threshold"
    ),
    bearish_threshold: float = typer.Option(
        -0.005, "--bearish-threshold", help="Bearish return threshold"
    ),
    hourly_timeframe: Optional[str] = typer.Option(
        None,
        "--hourly-timeframe",
        help="Load hourly data for return-by-context analysis (e.g., 1h)",
    ),
) -> None:
    """Analyze daily trend direction context labels.

    Generates forward-looking context labels (BULLISH/NEUTRAL/BEARISH) from
    daily OHLCV data and computes statistics: distribution, persistence,
    and optionally hourly return-by-context.

    Examples:
        ktrdr context analyze EURUSD 1d --start-date 2020-01-01 --end-date 2025-01-01
        ktrdr context analyze EURUSD 1d --hourly-timeframe 1h
    """
    # Lazy imports for fast CLI startup
    from rich.console import Console
    from rich.table import Table

    from ktrdr.data.repository import DataRepository
    from ktrdr.errors.exceptions import DataNotFoundError
    from ktrdr.training.context_labeler import ContextLabeler

    console = Console()

    # Load daily data from cache
    console.print(f"Loading {symbol} {timeframe} data from cache...")
    repo = DataRepository()
    try:
        daily_data = repo.load_from_cache(symbol, timeframe, start_date, end_date)
    except DataNotFoundError:
        console.print(f"[red]Error: No cached data for {symbol} {timeframe}[/red]")
        console.print(
            f"[yellow]Run: ktrdr data load {symbol} --timeframe {timeframe}[/yellow]"
        )
        raise typer.Exit(1) from None

    if daily_data is None or len(daily_data) == 0:
        console.print("[red]Error: No data available for the specified range[/red]")
        raise typer.Exit(1)

    console.print(
        f"Loaded {len(daily_data)} bars ({daily_data.index[0]} to {daily_data.index[-1]})"
    )

    # Generate context labels
    labeler = ContextLabeler(
        horizon=horizon,
        bullish_threshold=bullish_threshold,
        bearish_threshold=bearish_threshold,
    )
    labels = labeler.label(daily_data)
    valid_count = labels.notna().sum()
    console.print(
        f"Generated {valid_count} context labels (last {horizon} bars are NaN)"
    )

    # Optionally load hourly data
    hourly_data = None
    if hourly_timeframe:
        console.print(f"Loading {symbol} {hourly_timeframe} hourly data...")
        try:
            hourly_data = repo.load_from_cache(
                symbol, hourly_timeframe, start_date, end_date
            )
            console.print(f"Loaded {len(hourly_data)} hourly bars")
        except DataNotFoundError:
            console.print(
                f"[yellow]Warning: No cached hourly data for {symbol} {hourly_timeframe}, "
                "skipping return-by-context analysis[/yellow]"
            )

    # Compute statistics
    stats = labeler.analyze_labels(labels, hourly_data=hourly_data)

    # Print report
    console.print()
    console.print(
        f"[bold]Context Labeler Report — {symbol} {timeframe} "
        f"({daily_data.index[0].strftime('%Y-%m-%d')} to {daily_data.index[-1].strftime('%Y-%m-%d')})[/bold]"
    )
    console.print("─" * 60)

    # Distribution table
    console.print()
    console.print("[bold]Distribution[/bold]")
    dist_table = Table(show_header=True)
    dist_table.add_column("Context")
    dist_table.add_column("Fraction", justify="right")
    dist_table.add_column("Days", justify="right")
    for cls in [0, 1, 2]:
        frac = stats.distribution.get(cls, 0.0)
        days = int(frac * valid_count)
        dist_table.add_row(
            _LABEL_NAMES[cls],
            f"{frac:.1%}",
            str(days),
        )
    console.print(dist_table)

    # Persistence table
    console.print()
    console.print("[bold]Persistence[/bold]")
    dur_table = Table(show_header=True)
    dur_table.add_column("Context")
    dur_table.add_column("Mean Duration (days)", justify="right")
    for cls in [0, 1, 2]:
        dur = stats.mean_duration_days.get(cls, 0.0)
        dur_table.add_row(_LABEL_NAMES[cls], f"{dur:.1f}")
    console.print(dur_table)

    # Return by context (if hourly data provided)
    if stats.mean_hourly_return_by_context is not None:
        console.print()
        console.print("[bold]Return by Context (hourly bars)[/bold]")
        ret_table = Table(show_header=True)
        ret_table.add_column("Context")
        ret_table.add_column("Mean Hourly Return", justify="right")
        for cls in [0, 1, 2]:
            ret = stats.mean_hourly_return_by_context.get(cls, 0.0)
            sign = "+" if ret >= 0 else ""
            ret_table.add_row(_LABEL_NAMES[cls], f"{sign}{ret:.4%}")
        console.print(ret_table)

    # Regime correlation (if available)
    if stats.regime_correlation is not None:
        console.print()
        console.print(
            f"[bold]Regime Correlation:[/bold] {stats.regime_correlation:.3f}"
        )
        if stats.regime_correlation < 0.3:
            console.print(
                "[green]Low correlation — context is complementary to regime[/green]"
            )
        elif stats.regime_correlation > 0.7:
            console.print(
                "[yellow]High correlation — context may be redundant with regime[/yellow]"
            )

    # Quality gate summary
    console.print()
    console.print("[bold]Quality Gate Summary[/bold]")
    all_pass = True

    # Check distribution balance
    max_frac = max(stats.distribution.values())
    if max_frac > 0.6:
        console.print(
            f"  Distribution: [red]FAIL[/red] (max class = {max_frac:.0%} > 60%)"
        )
        all_pass = False
    else:
        console.print(
            f"  Distribution: [green]PASS[/green] (max class = {max_frac:.0%})"
        )

    # Check persistence
    dur_values = [
        stats.mean_duration_days.get(cls, 0.0)
        for cls in [0, 1, 2]
        if stats.distribution.get(cls, 0) > 0
    ]
    min_dur = min(dur_values) if dur_values else 0.0
    if min_dur < 3.0:
        console.print(
            f"  Persistence: [red]FAIL[/red] (min duration = {min_dur:.1f} days < 3)"
        )
        all_pass = False
    else:
        console.print(
            f"  Persistence: [green]PASS[/green] (min duration = {min_dur:.1f} days)"
        )

    # Check return differentiation
    if stats.mean_hourly_return_by_context is not None:
        bull_ret = stats.mean_hourly_return_by_context.get(0, 0.0)
        bear_ret = stats.mean_hourly_return_by_context.get(1, 0.0)
        if bull_ret > 0 and bear_ret < 0:
            console.print(
                "  Return diff: [green]PASS[/green] (bullish > 0, bearish < 0)"
            )
        else:
            console.print(
                f"  Return diff: [red]FAIL[/red] (bullish={bull_ret:+.4%}, bearish={bear_ret:+.4%})"
            )
            all_pass = False
    else:
        console.print("  Return diff: [dim]SKIP[/dim] (no hourly data)")

    console.print()
    if all_pass:
        console.print(
            "[bold green]Gate: PASS — context hypothesis supported[/bold green]"
        )
    else:
        console.print("[bold red]Gate: FAIL — see failed criteria above[/bold red]")
