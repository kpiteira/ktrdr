"""
Gap Analysis CLI Commands

Provides command-line interface for gap analysis and gap filler service management.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import typer
from tabulate import tabulate

from ktrdr.api.models.gap_analysis import (
    BatchGapAnalysisRequest,
    GapAnalysisMode,
    GapAnalysisRequest,
)
from ktrdr.api.services.gap_analysis_service import GapAnalysisService
from ktrdr.data.ib_gap_filler import get_gap_filler
from ktrdr.logging import get_logger

logger = get_logger(__name__)


# Create Typer app for gap analysis commands
gap_analysis_app = typer.Typer(
    name="gap-analysis", help="Gap analysis and management commands"
)


@gap_analysis_app.command("analyze")
def analyze_gaps(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, EURUSD)"),
    timeframe: str = typer.Argument(..., help="Timeframe (e.g., 1d, 1h)"),
    start_date: Optional[str] = typer.Option(
        None, "--start-date", "-s", help="Start date (YYYY-MM-DD or ISO format)"
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end-date", "-e", help="End date (YYYY-MM-DD or ISO format)"
    ),
    mode: str = typer.Option(
        "normal", "--mode", "-m", help="Analysis detail level (normal/extended/verbose)"
    ),
    include_expected: bool = typer.Option(
        False, "--include-expected", help="Include expected gaps in results"
    ),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format (table/json/summary)"
    ),
):
    """
    Analyze data gaps for a symbol/timeframe.

    Examples:
        ktrdr gap-analysis analyze AAPL 1d --start-date 2024-01-01 --end-date 2024-12-31
        ktrdr gap-analysis analyze EURUSD 1h --start-date 2024-01-01 --mode extended
        ktrdr gap-analysis analyze MSFT 1d --mode verbose --include-expected
    """
    try:
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if not start_date:
            # Default to 3 months ago
            start_date = (datetime.now(timezone.utc) - timedelta(days=90)).strftime(
                "%Y-%m-%d"
            )

        # Normalize date formats
        start_date = _normalize_date(start_date)
        end_date = _normalize_date(end_date)

        typer.echo(
            f"Analyzing gaps for {symbol}_{timeframe} from {start_date} to {end_date}"
        )

        # Create request
        request = GapAnalysisRequest(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            mode=GapAnalysisMode(mode),
        )

        # Run analysis
        result = asyncio.run(_run_gap_analysis(request))

        # Output results
        if output == "json":
            typer.echo(json.dumps(result.dict(), indent=2, default=str))
        elif output == "summary":
            _print_gap_summary(result)
        else:
            _print_gap_table(result, mode, include_expected)

    except Exception as e:
        logger.error(f"Gap analysis failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


@gap_analysis_app.command("batch")
def analyze_batch_gaps(
    timeframe: str = typer.Argument(..., help="Timeframe (e.g., 1d, 1h)"),
    symbols: list[str] = typer.Argument(
        ..., help="Trading symbols (e.g., AAPL MSFT GOOGL)"
    ),
    start_date: Optional[str] = typer.Option(
        None, "--start-date", "-s", help="Start date (YYYY-MM-DD or ISO format)"
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end-date", "-e", help="End date (YYYY-MM-DD or ISO format)"
    ),
    mode: str = typer.Option(
        "normal", "--mode", "-m", help="Analysis detail level (normal/extended/verbose)"
    ),
    include_expected: bool = typer.Option(
        False, "--include-expected", help="Include expected gaps in results"
    ),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format (table/json/summary)"
    ),
):
    """
    Analyze gaps for multiple symbols.

    Examples:
        ktrdr gap-analysis batch AAPL MSFT GOOGL 1d --start-date 2024-01-01
        ktrdr gap-analysis batch EURUSD GBPUSD 1h --mode extended
    """
    try:
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if not start_date:
            # Default to 3 months ago
            start_date = (datetime.now(timezone.utc) - timedelta(days=90)).strftime(
                "%Y-%m-%d"
            )

        # Normalize date formats
        start_date = _normalize_date(start_date)
        end_date = _normalize_date(end_date)

        typer.echo(
            f"Analyzing gaps for {len(symbols)} symbols ({timeframe}) from {start_date} to {end_date}"
        )

        # Create batch request
        request = BatchGapAnalysisRequest(
            symbols=list(symbols),
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            mode=GapAnalysisMode(mode),
        )

        # Run batch analysis
        result = asyncio.run(_run_batch_gap_analysis(request))

        # Output results
        if output == "json":
            typer.echo(json.dumps(result.dict(), indent=2, default=str))
        elif output == "summary":
            _print_batch_summary(result)
        else:
            _print_batch_table(result)

    except Exception as e:
        logger.error(f"Batch gap analysis failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


# Create Typer app for gap service commands
gap_service_app = typer.Typer(
    name="gap-service", help="Gap filler service management commands"
)


@gap_service_app.command("status")
def gap_service_status():
    """Show gap filler service status and statistics."""
    try:
        service = get_gap_filler()
        stats = service.get_stats()

        # Service status table
        status_data = [
            ["Running", "✅ Yes" if stats["running"] else "❌ No"],
            ["Check Interval", f"{stats['check_interval']} seconds"],
            ["Frequency", stats["configuration"]["frequency"]],
            [
                "Fill Unexpected Only",
                "✅ Yes" if stats["configuration"]["fill_unexpected_only"] else "❌ No",
            ],
            ["Max Gap Age", f"{stats['configuration']['max_gap_days']} days"],
            ["Batch Size", stats["configuration"]["batch_size"]],
            ["Last Scan", stats["last_scan_time"] or "Never"],
        ]

        typer.echo("Gap Filler Service Status")
        typer.echo("=" * 40)
        typer.echo(tabulate(status_data, headers=["Setting", "Value"], tablefmt="grid"))

        # Statistics table
        stats_data = [
            ["Gaps Detected", stats["gaps_detected"]],
            ["Gaps Filled", stats["gaps_filled"]],
            ["Gaps Failed", stats["gaps_failed"]],
            ["Expected Skipped", stats["gaps_expected_skipped"]],
            ["Symbols Processed", len(stats["symbols_processed"])],
            ["Errors", len(stats["errors"])],
        ]

        typer.echo("\nStatistics")
        typer.echo("=" * 20)
        typer.echo(tabulate(stats_data, headers=["Metric", "Count"], tablefmt="grid"))

        # Gap classifications
        if any(stats["gap_classifications"].values()):
            class_data = [
                [classification.replace("_", " ").title(), count]
                for classification, count in stats["gap_classifications"].items()
                if count > 0
            ]

            typer.echo("\nGap Classifications")
            typer.echo("=" * 30)
            typer.echo(tabulate(class_data, headers=["Type", "Count"], tablefmt="grid"))

        # Recent errors
        if stats["errors"]:
            typer.echo("\nRecent Errors")
            typer.echo("=" * 20)
            for error in stats["errors"][-3:]:  # Show last 3 errors
                typer.echo(f"• {error['time']}: {error['error']}")

    except Exception as e:
        logger.error(f"Failed to get gap service status: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


@gap_service_app.command("start")
def gap_service_start(
    frequency: Optional[str] = typer.Option(
        None,
        "--frequency",
        help="Override sync frequency (manual/hourly/daily/disabled)",
    )
):
    """Start the gap filler service."""
    try:
        service = get_gap_filler()

        if frequency:
            # Override frequency temporarily
            service.config["frequency"] = frequency
            service.check_interval = service._get_check_interval()
            typer.echo(f"Frequency overridden to: {frequency}")

        success = service.start()

        if success:
            typer.echo("✅ Gap filler service started successfully")
            typer.echo(f"Check interval: {service.check_interval} seconds")
            typer.echo("Use 'ktrdr gap-service status' to monitor progress")
        else:
            typer.echo("❌ Failed to start gap filler service", err=True)
            raise typer.Exit(1)

    except Exception as e:
        logger.error(f"Failed to start gap service: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


@gap_service_app.command("stop")
def gap_service_stop():
    """Stop the gap filler service."""
    try:
        service = get_gap_filler()
        service.stop()
        typer.echo("✅ Gap filler service stopped")

    except Exception as e:
        logger.error(f"Failed to stop gap service: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


@gap_service_app.command("scan-now")
def gap_service_scan_now(
    force: bool = typer.Option(
        False, "--force", help="Force scan even if frequency is disabled"
    )
):
    """Trigger immediate gap scan."""
    try:
        service = get_gap_filler()

        if force:
            # Temporarily override frequency
            original_frequency = service.config.get("frequency", "daily")
            service.config["frequency"] = "hourly"

        result = service.force_scan()

        if force:
            # Restore original frequency
            service.config["frequency"] = original_frequency

        if "error" in result:
            typer.echo(f"❌ Scan failed: {result['error']}", err=True)
            raise typer.Exit(1)
        else:
            typer.echo("✅ Gap scan completed")

            # Show scan results
            stats = result["stats"]
            scan_data = [
                ["Gaps Detected", stats["gaps_detected"]],
                ["Gaps Filled", stats["gaps_filled"]],
                ["Gaps Failed", stats["gaps_failed"]],
                ["Expected Skipped", stats["gaps_expected_skipped"]],
            ]

            typer.echo("\nScan Results")
            typer.echo("=" * 20)
            typer.echo(
                tabulate(scan_data, headers=["Metric", "Count"], tablefmt="grid")
            )

    except Exception as e:
        logger.error(f"Gap scan failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


# Helper functions
async def _run_gap_analysis(request: GapAnalysisRequest):
    """Run gap analysis asynchronously."""
    service = GapAnalysisService()
    return await service.analyze_gaps(request)


async def _run_batch_gap_analysis(request: BatchGapAnalysisRequest):
    """Run batch gap analysis asynchronously."""
    service = GapAnalysisService()
    return await service.analyze_gaps_batch(request)


def _normalize_date(date_str: str) -> str:
    """Normalize date string to ISO format."""
    try:
        # Try parsing as YYYY-MM-DD first
        if len(date_str) == 10 and date_str.count("-") == 2:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str + "T00:00:00Z"

        # Try parsing as ISO format
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    except ValueError:
        raise typer.BadParameter(
            f"Invalid date format: {date_str}. Use YYYY-MM-DD or ISO format."
        ) from None


def _print_gap_summary(result):
    """Print gap analysis summary."""
    typer.echo(f"\nGap Analysis Summary for {result.symbol}_{result.timeframe}")
    typer.echo("=" * 60)

    # Summary statistics
    summary_data = [
        ["Expected Bars", result.summary.expected_bars],
        ["Actual Bars", result.summary.actual_bars],
        ["Missing Bars", result.summary.total_missing],
        ["Completeness", f"{result.summary.data_completeness_pct:.1f}%"],
    ]

    typer.echo(tabulate(summary_data, headers=["Metric", "Value"], tablefmt="grid"))

    # Missing breakdown
    if result.summary.total_missing > 0:
        breakdown_data = [
            [classification.replace("_", " ").title(), count]
            for classification, count in result.summary.missing_breakdown.items()
            if count > 0
        ]

        if breakdown_data:
            typer.echo("\nMissing Bars Breakdown")
            typer.echo("=" * 30)
            typer.echo(
                tabulate(breakdown_data, headers=["Type", "Count"], tablefmt="grid")
            )

    # Recommendations
    if result.recommendations:
        typer.echo("\nRecommendations")
        typer.echo("=" * 20)
        for rec in result.recommendations:
            typer.echo(f"• {rec}")


def _print_gap_table(result, mode: str, include_expected: bool):
    """Print gap analysis with detailed gap information."""
    _print_gap_summary(result)

    # Individual gaps (if any)
    if result.gaps and mode in ["extended", "verbose"]:
        typer.echo(f"\nDetailed Gaps ({len(result.gaps)} found)")
        typer.echo("=" * 60)

        gap_data = []
        for gap in result.gaps:
            classification = str(gap.classification).replace("_", " ").title()
            start_date = gap.start_time.strftime("%Y-%m-%d %H:%M")
            gap.end_time.strftime("%Y-%m-%d %H:%M")

            gap_data.append(
                [
                    classification,
                    f"{gap.duration_hours:.1f}h",
                    gap.bars_missing,
                    gap.day_context,
                    start_date,
                    (
                        gap.note[:50] + "..."
                        if len(gap.note or "") > 50
                        else (gap.note or "")
                    ),
                ]
            )

        headers = ["Type", "Duration", "Bars", "Context", "Start Time", "Note"]
        typer.echo(tabulate(gap_data, headers=headers, tablefmt="grid"))


def _print_batch_summary(result):
    """Print batch analysis summary."""
    typer.echo("\nBatch Gap Analysis Summary")
    typer.echo("=" * 40)

    # Request summary
    req_data = [
        ["Symbols Requested", result.request_summary["symbols_requested"]],
        ["Successful", result.request_summary["symbols_successful"]],
        ["Failed", result.request_summary["symbols_failed"]],
        ["Timeframe", result.request_summary["timeframe"]],
    ]

    typer.echo(tabulate(req_data, headers=["Metric", "Value"], tablefmt="grid"))

    # Overall summary
    if result.overall_summary:
        overall_data = [
            ["Total Expected Bars", result.overall_summary["total_expected_bars"]],
            ["Total Actual Bars", result.overall_summary["total_actual_bars"]],
            ["Total Missing", result.overall_summary["total_missing_bars"]],
            [
                "Overall Completeness",
                f"{result.overall_summary['overall_completeness_pct']:.1f}%",
            ],
            [
                "Average Completeness",
                f"{result.overall_summary['average_completeness_pct']:.1f}%",
            ],
        ]

        typer.echo("\nOverall Statistics")
        typer.echo("=" * 25)
        typer.echo(tabulate(overall_data, headers=["Metric", "Value"], tablefmt="grid"))


def _print_batch_table(result):
    """Print batch analysis with individual symbol results."""
    _print_batch_summary(result)

    # Individual symbol results
    if result.results:
        typer.echo("\nIndividual Symbol Results")
        typer.echo("=" * 35)

        symbol_data = []
        for res in result.results:
            symbol_data.append(
                [
                    res.symbol,
                    res.summary.expected_bars,
                    res.summary.actual_bars,
                    res.summary.total_missing,
                    f"{res.summary.data_completeness_pct:.1f}%",
                ]
            )

        headers = ["Symbol", "Expected", "Actual", "Missing", "Complete %"]
        typer.echo(tabulate(symbol_data, headers=headers, tablefmt="grid"))

    # Errors
    if result.errors:
        typer.echo(f"\nErrors ({len(result.errors)})")
        typer.echo("=" * 15)
        for error in result.errors:
            typer.echo(f"• {error['symbol']}: {error['error']}")


# Register command groups with the main CLI
def register_gap_commands(cli_group):
    """Register gap analysis commands with the main CLI."""
    cli_group.add_typer(gap_analysis_app)
    cli_group.add_typer(gap_service_app)
