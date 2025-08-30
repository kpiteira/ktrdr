"""Backtesting commands for the main CLI."""

import asyncio
import json
import signal
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ktrdr.cli.api_client import get_api_client

# Rich console for formatted output
console = Console()

# Global variable to track cancellation
cancelled = False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global cancelled
    cancelled = True
    console.print("\n[yellow]⏹️  Cancellation requested. Stopping backtest...[/yellow]")


def run_backtest(
    strategy: str = typer.Argument(..., help="Strategy name (without .yaml extension)"),
    symbol: str = typer.Argument(
        ..., help="Trading symbol to backtest (e.g., AAPL, MSFT)"
    ),
    timeframe: str = typer.Argument(
        ..., help="Timeframe for backtest data (e.g., 1h, 4h, 1d)"
    ),
    start_date: str = typer.Option(
        ..., "--start-date", help="Start date for backtest (YYYY-MM-DD)"
    ),
    end_date: str = typer.Option(
        ..., "--end-date", help="End date for backtest (YYYY-MM-DD)"
    ),
    capital: float = typer.Option(
        100000, "--capital", "-c", help="Initial capital for backtest"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output with progress"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file for results (JSON format)"
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress all output except errors"
    ),
):
    """
    Run a backtest on a trained trading strategy.

    This command uses the async API to simulate trading and provides real-time
    progress updates. The backtest can be cancelled with Ctrl+C.

    Examples:
        ktrdr backtest neuro_mean_reversion AAPL 1h --start-date 2024-07-01 --end-date 2024-12-31
        ktrdr backtest momentum MSFT 4h --start-date 2023-01-01 --end-date 2024-01-01 --capital 50000
    """
    # Use asyncio to run the async function
    return asyncio.run(
        _run_backtest_async(
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            capital=capital,
            verbose=verbose,
            output=output,
            quiet=quiet,
        )
    )


async def _run_backtest_async(
    strategy: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    capital: float,
    verbose: bool,
    output: Optional[str],
    quiet: bool,
):
    """Run backtest using async API with progress tracking."""
    global cancelled
    cancelled = False

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Get API client
    api_client = get_api_client()
    operation_id = None

    try:
        if not quiet:
            console.print("[cyan]🔬 KTRDR Backtesting Engine[/cyan]")
            console.print("=" * 50)

        # Validate arguments
        if capital <= 0:
            console.print(
                f"[red]❌ Error: Capital must be positive, got {capital}[/red]"
            )
            raise typer.Exit(1)

        if verbose and not quiet:
            console.print("📋 Configuration:")
            console.print(f"  Strategy: [blue]{strategy}[/blue]")
            console.print(f"  Symbol: [blue]{symbol}[/blue]")
            console.print(f"  Timeframe: [blue]{timeframe}[/blue]")
            console.print(
                f"  Period: [blue]{start_date}[/blue] to [blue]{end_date}[/blue]"
            )
            console.print(f"  Capital: [green]${capital:,.2f}[/green]")
            console.print()

        # Start backtest via API
        if not quiet:
            console.print("🚀 Starting backtest...")

        response = await api_client.start_backtest(
            strategy_name=strategy,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=capital,
        )

        if not response.get("success"):
            console.print(
                f"[red]❌ Failed to start backtest: {response.get('error', 'Unknown error')}[/red]"
            )
            raise typer.Exit(1)

        # Get operation ID
        operation_id = response["data"]["backtest_id"]

        if not quiet:
            console.print(f"⚡ Started backtest operation: {operation_id}")

        # Poll for progress with Rich progress bar
        if not quiet and verbose:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("Running backtest...", total=100)

                # Poll operation status
                while not cancelled:
                    try:
                        status_response = await api_client.get_operation_status(
                            operation_id
                        )
                        operation_data = status_response.get("data", {})

                        status = operation_data.get("status")
                        progress_info = operation_data.get("progress", {})
                        progress_percentage = progress_info.get("percentage", 0)
                        current_step = progress_info.get("current_step", "Running...")

                        # Display warnings if any
                        warnings = operation_data.get("warnings", [])
                        if warnings:
                            for warning in warnings[-2:]:  # Show last 2 warnings
                                console.print(f"[yellow]⚠️  {warning}[/yellow]")

                        # Display errors if any
                        errors = operation_data.get("errors", [])
                        if errors:
                            for error in errors[-2:]:  # Show last 2 errors
                                console.print(f"[red]❌ {error}[/red]")

                        # Build enhanced description with items info
                        description = (
                            current_step[:70] + "..."
                            if len(current_step) > 70
                            else current_step
                        )

                        # Add items processed info if available
                        items_processed = progress_info.get("items_processed", 0)
                        items_total = progress_info.get("items_total")
                        if items_processed > 0:
                            if items_total:
                                description += (
                                    f" ({items_processed:,}/{items_total:,} bars)"
                                )
                            else:
                                description += f" ({items_processed:,} bars)"

                        # Update progress display
                        progress.update(
                            task,
                            completed=progress_percentage,
                            description=description,
                        )

                        # Check if operation completed
                        if status in ["completed", "failed", "cancelled"]:
                            progress.update(
                                task, completed=100, description="Completed"
                            )
                            break

                        # Sleep before next poll
                        await asyncio.sleep(1.0)

                    except Exception as e:
                        if not quiet:
                            console.print(
                                f"[yellow]Warning: Failed to get operation status: {str(e)}[/yellow]"
                            )
                        break
        else:
            # Simple polling without progress display
            while not cancelled:
                try:
                    status_response = await api_client.get_operation_status(
                        operation_id
                    )
                    operation_data = status_response.get("data", {})
                    status = operation_data.get("status")

                    if status in ["completed", "failed", "cancelled"]:
                        break

                    await asyncio.sleep(2.0)

                except Exception as e:
                    if not quiet:
                        console.print(
                            f"[yellow]Warning: Failed to get operation status: {str(e)}[/yellow]"
                        )
                    break

        # Handle cancellation
        if cancelled and operation_id:
            try:
                await api_client.cancel_operation(
                    operation_id=operation_id,
                    reason="User requested cancellation via CLI",
                )
                if not quiet:
                    console.print("⏹️  Backtest cancelled successfully")
                return None
            except Exception as e:
                if not quiet:
                    console.print(
                        f"[yellow]Warning: Failed to cancel operation: {str(e)}[/yellow]"
                    )

        # Get final status
        try:
            final_status_response = await api_client.get_operation_status(operation_id)
            final_operation_data = final_status_response.get("data", {})
            final_status = final_operation_data.get("status")

            if final_status == "failed":
                error_message = final_operation_data.get("error", "Unknown error")
                console.print(f"[red]❌ Backtest failed: {error_message}[/red]")
                raise typer.Exit(1)
            elif final_status == "cancelled":
                console.print("[yellow]⏹️  Backtest was cancelled[/yellow]")
                return None
        except Exception as e:
            console.print(f"[red]❌ Failed to get final status: {str(e)}[/red]")
            raise typer.Exit(1) from e

        # Get results
        try:
            results_response = await api_client.get_backtest_results(operation_id)
            if not results_response.get("success"):
                console.print(
                    f"[red]❌ Failed to get results: {results_response.get('error', 'Unknown error')}[/red]"
                )
                raise typer.Exit(1)

            results_data = results_response["data"]

            # Get trades if verbose
            trades_data = []
            if verbose:
                try:
                    trades_response = await api_client.get_backtest_trades(operation_id)
                    if trades_response.get("success"):
                        trades_data = trades_response["data"]["trades"]
                except Exception as e:
                    console.print(
                        f"[yellow]Warning: Failed to get trades: {str(e)}[/yellow]"
                    )

            # Save results if output file specified
            if output:
                output_data = results_data.copy()
                if trades_data:
                    output_data["trades"] = trades_data

                # Get equity curve
                try:
                    equity_response = await api_client.get_equity_curve(operation_id)
                    if equity_response.get("success"):
                        output_data["equity_curve"] = equity_response["data"]
                except Exception as e:
                    console.print(
                        f"[yellow]Warning: Failed to get equity curve: {str(e)}[/yellow]"
                    )

                output_path = Path(output)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "w") as f:
                    json.dump(output_data, f, indent=2, default=str)

            if not quiet:
                # Display summary
                console.print("\n[green]✅ Backtest completed successfully![/green]")
                if output:
                    console.print(f"[cyan]📄 Results saved to: {output}[/cyan]")

                # Print performance summary
                console.print("\n[cyan]📊 Performance Summary:[/cyan]")
                console.print("=" * 50)

                metrics = results_data.get("metrics", {})
                results_data.get("summary", {})

                total_return = metrics.get("total_return", 0)
                total_return_pct = (total_return / capital) * 100 if capital > 0 else 0

                console.print(
                    f"💰 Total Return: [green]${total_return:,.2f} ({total_return_pct:.2f}%)[/green]"
                )
                console.print(
                    f"📈 Sharpe Ratio: [yellow]{metrics.get('sharpe_ratio', 0):.3f}[/yellow]"
                )
                console.print(
                    f"📉 Max Drawdown: [red]${metrics.get('max_drawdown', 0):,.2f}[/red]"
                )
                console.print(
                    f"🎯 Win Rate: [blue]{metrics.get('win_rate', 0)*100:.1f}%[/blue]"
                )
                console.print(
                    f"🏷️ Total Trades: [blue]{metrics.get('total_trades', 0)}[/blue]"
                )

            return results_data

        except Exception as e:
            console.print(f"[red]❌ Failed to get backtest results: {str(e)}[/red]")
            raise typer.Exit(1) from e

    except Exception as e:
        if "Ctrl+C" not in str(e):  # Don't show error for user cancellation
            console.print(f"[red]❌ Backtest failed: {str(e)}[/red]")
            if verbose and not quiet:
                import traceback

                console.print(traceback.format_exc())
        raise typer.Exit(1) from e
