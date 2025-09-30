"""Async model commands using AsyncCLIClient pattern for improved performance.

This module provides the migrated model commands that use the AsyncCLIClient
base class for connection reuse and performance optimization.
"""

import asyncio
import signal
import sys
import time
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

from ktrdr.cli.async_cli_client import AsyncCLIClient, AsyncCLIClientError
from ktrdr.config.strategy_loader import strategy_loader
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError, ValidationError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for async model commands
async_models_app = typer.Typer(
    name="models",
    help="Async neural network model management commands with improved performance",
    no_args_is_help=True,
)


async def _wait_for_cancellation_completion_async(
    cli: AsyncCLIClient, operation_id: str, console: Console, timeout: int = 30
) -> bool:
    """Wait for training cancellation to complete with timeout using AsyncCLIClient."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            status_result = await cli._make_request(
                "GET", f"/operations/{operation_id}"
            )
            operation_data = status_result.get("data", {})
            status = operation_data.get("status", "unknown")

            if status == "cancelled":
                console.print(
                    "✅ [green]Training cancellation completed successfully[/green]"
                )
                return True
            elif status in ["completed", "failed"]:
                console.print(
                    f"⚠️ [yellow]Training finished as '{status}' before cancellation could complete[/yellow]"
                )
                return True

            # Show progress while waiting
            elapsed = int(time.time() - start_time)
            console.print(
                f"⏳ Waiting for cancellation completion... ({elapsed}s/{timeout}s)"
            )
            await asyncio.sleep(2)

        except Exception as e:
            console.print(f"[red]Error checking cancellation status: {e}[/red]")
            break

    console.print(
        f"⚠️ [yellow]Cancellation timeout after {timeout}s - training may still be running[/yellow]"
    )
    return False


@async_models_app.command("train")
def train_model_async(
    strategy_file: str = typer.Argument(..., help="Path to strategy YAML file"),
    symbol: Optional[str] = typer.Argument(
        None, help="Trading symbol (optional, overrides strategy config)"
    ),
    timeframe: Optional[str] = typer.Argument(
        None, help="Data timeframe (optional, overrides strategy config)"
    ),
    start_date: str = typer.Option(
        ..., "--start-date", help="Training start date (YYYY-MM-DD)"
    ),
    end_date: str = typer.Option(
        ..., "--end-date", help="Training end date (YYYY-MM-DD)"
    ),
    models_dir: str = typer.Option(
        "models", "--models-dir", help="Directory to save trained models"
    ),
    validation_split: float = typer.Option(
        0.2, "--validation-split", help="Validation data split ratio"
    ),
    data_mode: str = typer.Option(
        "local", "--data-mode", help="Data loading mode (local, ib)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show training plan without executing"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    detailed_analytics: bool = typer.Option(
        False,
        "--detailed-analytics",
        help="Enable detailed training analytics with CSV/JSON export",
    ),
) -> None:
    """
    Train neural network models using strategy configurations with async architecture.

    This command trains new models using the specified strategy configuration with
    improved performance through connection reuse and async optimization.
    Symbols and timeframes are extracted from the strategy file unless explicitly
    overridden with command arguments.

    Examples:
        # Strategy-driven training (recommended)
        ktrdr models train strategies/neuro_mean_reversion.yaml --start-date 2024-01-01 --end-date 2024-06-01

        # Override strategy config (legacy)
        ktrdr models train strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-01-01 --end-date 2024-06-01

        # Dry run to see what would be trained
        ktrdr models train strategies/trend_momentum.yaml --start-date 2023-01-01 --end-date 2024-01-01 --dry-run
    """
    try:
        # Validate strategy file exists
        strategy_path = Path(strategy_file)
        if not strategy_path.exists():
            console.print(
                f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]"
            )
            raise typer.Exit(1)

        # Load strategy configuration to extract symbols/timeframes if not provided
        try:
            config, is_v2 = strategy_loader.load_strategy_config(str(strategy_path))
            config_symbols, config_timeframes = (
                strategy_loader.extract_training_symbols_and_timeframes(config)
            )
        except Exception as e:
            console.print(f"[red]❌ Error loading strategy config: {e}[/red]")
            raise typer.Exit(1) from e

        # Use strategy config or CLI overrides
        final_symbols = [symbol] if symbol else config_symbols
        final_timeframes = [timeframe] if timeframe else config_timeframes

        # Validate we have symbols and timeframes
        if not final_symbols:
            console.print(
                "[red]❌ Error: No symbols specified in strategy config or CLI arguments[/red]"
            )
            raise typer.Exit(1)
        if not final_timeframes:
            console.print(
                "[red]❌ Error: No timeframes specified in strategy config or CLI arguments[/red]"
            )
            raise typer.Exit(1)

        # Support both multi-symbol and multi-timeframe training
        training_symbols = final_symbols
        training_timeframes = final_timeframes

        # Show what will be trained
        if len(final_symbols) > 1:
            console.print("[green]✅ Multi-symbol training enabled:[/green]")
            console.print(f"   Symbols: {', '.join(final_symbols)}")
        else:
            console.print("[blue]📊 Single-symbol training:[/blue]")
            console.print(f"   Symbol: {final_symbols[0]}")

        if len(final_timeframes) > 1:
            console.print("[green]✅ Multi-timeframe training enabled:[/green]")
            console.print(f"   Timeframes: {', '.join(final_timeframes)}")
        else:
            console.print("[blue]📊 Single-timeframe training:[/blue]")
            console.print(f"   Timeframe: {final_timeframes[0]}")

        # Validate all symbols
        validated_symbols = []
        for sym in training_symbols:
            validated_sym = InputValidator.validate_string(
                sym, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
            )
            validated_symbols.append(validated_sym)
        training_symbols = validated_symbols

        # Validate all timeframes
        validated_timeframes = []
        for tf in training_timeframes:
            validated_tf = InputValidator.validate_string(
                tf, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
            )
            validated_timeframes.append(validated_tf)
        training_timeframes = validated_timeframes
        validation_split = InputValidator.validate_numeric(
            validation_split, min_value=0.0, max_value=0.5
        )

        # Run async operation with extracted/validated symbols and timeframes
        asyncio.run(
            _train_model_async_impl(
                strategy_file,
                training_symbols,
                training_timeframes,
                start_date,
                end_date,
                models_dir,
                validation_split,
                data_mode,
                dry_run,
                verbose,
                detailed_analytics,
            )
        )

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _train_model_async_impl(
    strategy_file: str,
    symbols: list[str],
    timeframes: list[str],
    start_date: str,
    end_date: str,
    models_dir: str,
    validation_split: float,
    data_mode: str,
    dry_run: bool,
    verbose: bool,
    detailed_analytics: bool,
) -> None:
    """Async implementation of train model command using AsyncCLIClient."""
    try:
        # Use AsyncCLIClient for connection reuse and performance
        async with AsyncCLIClient() as cli:
            # Check API connection using AsyncCLIClient
            try:
                await cli._make_request("GET", "/health")
            except AsyncCLIClientError as e:
                if e.error_code == "CLI-ConnectionError":
                    error_console.print(
                        "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
                    )
                    error_console.print(
                        "Make sure the API server is running at the configured URL"
                    )
                    sys.exit(1)
                else:
                    raise

            if verbose:
                symbols_str = ", ".join(symbols)
                timeframes_str = ", ".join(timeframes)
                console.print(f"🧠 Training model for {symbols_str} ({timeframes_str})")
                console.print(f"📋 Strategy: {strategy_file}")
                console.print(f"📅 Training period: {start_date} to {end_date}")

            if dry_run:
                console.print("🔍 [yellow]DRY RUN - No model will be trained[/yellow]")
                symbols_str = ", ".join(symbols)
                timeframes_str = ", ".join(timeframes)
                console.print(f"📋 Would train: {symbols_str} on {timeframes_str}")
                console.print(f"📊 Validation split: {validation_split}")
                console.print(f"💾 Models directory: {models_dir}")
                return

            # Call the training API endpoint using AsyncCLIClient
            console.print("🚀 [cyan]Starting model training via async API...[/cyan]")
            console.print("📋 Training parameters:")
            console.print(f"   Strategy: {strategy_file}")
            symbols_str = ", ".join(symbols)
            console.print(f"   Symbols: {symbols_str}")
            timeframes_str = ", ".join(timeframes)
            console.print(f"   Timeframes: {timeframes_str}")
            console.print(f"   Period: {start_date} to {end_date}")
            console.print(f"   Validation split: {validation_split}")
            if detailed_analytics:
                console.print(
                    "   Analytics: [green]✅ Detailed analytics enabled[/green]"
                )

            # Start the training via async API
            try:
                # Extract strategy name from file path (remove .yaml extension)
                strategy_name = Path(strategy_file).stem

                # Use async training API with improved performance
                result = await cli._make_request(
                    "POST",
                    "/trainings/start",
                    json_data={
                        "symbols": symbols,
                        "timeframes": timeframes,
                        "strategy_name": strategy_name,
                        "start_date": start_date,
                        "end_date": end_date,
                        "detailed_analytics": detailed_analytics,
                    },
                )

                if "task_id" not in result:
                    console.print(
                        f"❌ [red]API response missing task_id: {result}[/red]"
                    )
                    return

                task_id = result["task_id"]
                console.print(f"✅ Training started with ID: [bold]{task_id}[/bold]")

            except AsyncCLIClientError as e:
                console.print(f"❌ [red]Failed to start training: {str(e)}[/red]")
                console.print(
                    "[yellow]🔍 AsyncCLIClientError caught - this is causing premature return![/yellow]"
                )
                console.print(f"[yellow]Error code: {e.error_code}[/yellow]")
                console.print(f"[yellow]Error details: {e.details}[/yellow]")
                return

            # Poll for progress with proper signal handling and comprehensive error handling
            # Temporarily suppress httpx logging to keep progress display clean
            import logging

            httpx_logger = logging.getLogger("httpx")
            original_level = httpx_logger.level
            httpx_logger.setLevel(logging.WARNING)

            # Set up cancellation handling with error protection
            cancelled = False
            loop = asyncio.get_running_loop()

            def signal_handler() -> None:
                """Handle Ctrl+C for graceful training cancellation."""
                nonlocal cancelled
                cancelled = True
                console.print(
                    "\n[yellow]🛑 Training cancellation requested... stopping training[/yellow]"
                )

            # Register signal handler with the event loop - catch any exceptions
            try:
                loop.add_signal_handler(signal.SIGINT, signal_handler)
                console.print("[dim]🔧 Signal handler registered successfully[/dim]")
            except Exception as e:
                console.print(
                    f"[yellow]⚠️ Could not register signal handler: {e}[/yellow]"
                )
                console.print(
                    "[yellow]Training will continue without Ctrl+C handling[/yellow]"
                )

            # Wrap the entire polling section to catch any exceptions that might cause premature exit
            try:
                console.print("[dim]🔧 Starting progress monitoring...[/dim]")
                console.print("[dim]🔧 Creating Progress bar...[/dim]")
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task("Training model...", total=100)

                    while True:
                        try:
                            # Check for cancellation first
                            if cancelled:
                                console.print(
                                    "[yellow]🛑 Sending cancellation to training service...[/yellow]"
                                )
                                try:
                                    cancel_response = await cli._make_request(
                                        "POST",
                                        f"/operations/{task_id}/cancel",
                                        json_data={
                                            "reason": "User requested cancellation via CLI"
                                        },
                                    )
                                    if cancel_response.get("success"):
                                        console.print(
                                            "✅ [yellow]Training cancellation sent successfully[/yellow]"
                                        )
                                        # Wait for cancellation to complete with timeout
                                        await _wait_for_cancellation_completion_async(
                                            cli, task_id, console
                                        )
                                    else:
                                        console.print(
                                            f"[red]Training cancellation failed: {cancel_response}[/red]"
                                        )
                                except Exception as e:
                                    console.print(
                                        f"[red]Training cancel request failed: {str(e)}[/red]"
                                    )
                                break

                            # Get status from operations framework via AsyncCLIClient
                            # Use the outer cli client to avoid nested context issues
                            status_result = await cli._make_request(
                                "GET", f"/operations/{task_id}"
                            )
                            operation_data = status_result.get("data", {})

                            status = operation_data.get("status", "unknown")
                            progress_info = operation_data.get("progress", {})
                            progress_pct = progress_info.get("percentage", 0)
                            progress_context = progress_info.get("context", {})

                            # Extract epoch info from metadata and results
                            metadata = operation_data.get("metadata", {})
                            total_epochs = metadata.get("parameters", {}).get(
                                "epochs", 100
                            )

                            # For completed operations, get actual epochs from results
                            if status == "completed" and operation_data.get(
                                "result_summary"
                            ):
                                training_metrics = operation_data.get(
                                    "result_summary", {}
                                ).get("training_metrics", {})
                                current_epoch = training_metrics.get(
                                    "epochs_trained", 0
                                )
                                bars_info = ""
                                gpu_info = ""
                            else:
                                # Prefer using new progress context fields (Task 5.4)
                                current_epoch = progress_context.get("current_epoch", 0)
                                current_batch = progress_context.get("current_batch", 0)
                                total_batches = progress_context.get(
                                    "total_batches_per_epoch", 0
                                )

                                # Build bars info from context
                                bars_info = ""
                                if current_batch > 0 and total_batches > 0:
                                    bars_info = (
                                        f", Batch: {current_batch}/{total_batches}"
                                    )

                                # Extract GPU/resource usage info (Task 5.4)
                                gpu_info = ""
                                resource_usage = progress_context.get(
                                    "resource_usage", {}
                                )
                                gpu_used = resource_usage.get("gpu_used", False)
                                if gpu_used:
                                    gpu_name = resource_usage.get("gpu_name", "GPU")
                                    gpu_util = resource_usage.get(
                                        "gpu_utilization_percent"
                                    )
                                    if gpu_util is not None:
                                        gpu_info = f" 🖥️ {gpu_name}: {gpu_util:.0f}%"
                                    elif gpu_name:
                                        gpu_info = f" 🖥️ {gpu_name}"

                                # Fallback: parse from current_step string (backward compatibility)
                                if current_epoch == 0:
                                    current_step = progress_info.get("current_step", "")
                                    if (
                                        current_step
                                        and "Epoch:" in current_step
                                        and "Bars:" in current_step
                                    ):
                                        try:
                                            # Extract epoch number
                                            epoch_part = (
                                                current_step.split("Epoch:")[1]
                                                .split(",")[0]
                                                .strip()
                                            )
                                            current_epoch = int(epoch_part)

                                            # Extract bars part "X/Y"
                                            bars_part = current_step.split("Bars:")[
                                                1
                                            ].strip()
                                            # Remove any trailing text like "(Val Acc: 0.123)"
                                            if bars_part and "(" in bars_part:
                                                bars_part = bars_part.split("(")[
                                                    0
                                                ].strip()

                                            # Parse current bars and total bars for this epoch
                                            if bars_part and "/" in bars_part:
                                                current_bars_str, total_bars_str = (
                                                    bars_part.split("/")
                                                )
                                                current_bars = int(
                                                    current_bars_str.replace(",", "")
                                                )
                                                total_bars_all_epochs = int(
                                                    total_bars_str.replace(",", "")
                                                )

                                                # Calculate bars per epoch and current bars in this epoch
                                                bars_per_epoch = (
                                                    total_bars_all_epochs
                                                    // total_epochs
                                                    if total_epochs > 0
                                                    else 0
                                                )
                                                bars_this_epoch = (
                                                    current_bars % bars_per_epoch
                                                    if bars_per_epoch > 0
                                                    else 0
                                                )

                                                bars_info = f", Bars: {bars_this_epoch:,}/{bars_per_epoch:,}"

                                        except (
                                            IndexError,
                                            ValueError,
                                            ZeroDivisionError,
                                        ):
                                            current_epoch = 0
                                            bars_info = ""

                            # Update progress bar with epoch, bars, and GPU info
                            if current_epoch > 0:
                                epoch_info = f" (Epoch: {current_epoch}/{total_epochs}{bars_info}{gpu_info})"
                            else:
                                epoch_info = gpu_info if gpu_info else ""
                            progress.update(
                                task,
                                completed=progress_pct,
                                description=f"Status: {status}{epoch_info}",
                            )

                            if status == "completed":
                                console.print(
                                    "✅ [green]Model training completed successfully![/green]"
                                )
                                break
                            elif status == "failed":
                                error_msg = operation_data.get("error", "Unknown error")
                                console.print(
                                    f"❌ [red]Training failed: {error_msg}[/red]"
                                )
                                return
                            elif status == "cancelled":
                                console.print(
                                    "✅ [yellow]Training cancelled successfully[/yellow]"
                                )
                                return

                            # Wait before next poll
                            await asyncio.sleep(3)

                        except asyncio.CancelledError:
                            console.print(
                                "\n⚠️  [yellow]Training monitoring cancelled[/yellow]"
                            )
                            break
                        except Exception as e:
                            console.print(
                                f"❌ [red]Error polling training status: {str(e)}[/red]"
                            )
                            console.print(
                                f"[yellow]Exception type: {type(e).__name__}[/yellow]"
                            )
                            if hasattr(e, "details"):
                                console.print(
                                    f"[yellow]Error details: {e.details}[/yellow]"
                                )
                            break

                # If we reach here without breaking due to completion/failure, mark as success
                console.print("[dim]✅ Polling completed successfully[/dim]")

            except Exception as polling_error:
                # Catch any exception that might cause the entire function to exit prematurely
                console.print(
                    f"❌ [red]Critical error in polling setup: {type(polling_error).__name__}: {polling_error}[/red]"
                )
                console.print(
                    "[yellow]This error caused the AsyncCLIClient context to close prematurely[/yellow]"
                )
                import traceback

                console.print(f"[dim]Traceback: {traceback.format_exc()}[/dim]")
            finally:
                # Remove signal handler and restore logging
                try:
                    loop.remove_signal_handler(signal.SIGINT)
                except (ValueError, OSError):
                    pass
                httpx_logger.setLevel(original_level)

            # Get real results from API using outer cli client (after finally block)
            try:
                performance_result = await cli._make_request(
                    "GET", f"/trainings/{task_id}/performance"
                )

                # Handle None or malformed response
                if not performance_result:
                    console.print(
                        "⚠️  [yellow]Training completed, but unable to fetch detailed results[/yellow]"
                    )
                    return

                training_metrics = performance_result.get("training_metrics", {})
                test_metrics = performance_result.get("test_metrics", {})
                model_info = performance_result.get("model_info", {})

                # Display real results
                console.print("📊 [bold green]Training Results:[/bold green]")
                console.print(
                    f"🎯 Test accuracy: {test_metrics.get('test_accuracy', 0) * 100:.1f}%"
                )
                console.print(
                    f"📊 Precision: {test_metrics.get('precision', 0) * 100:.1f}%"
                )
                console.print(f"📊 Recall: {test_metrics.get('recall', 0) * 100:.1f}%")
                console.print(
                    f"📊 F1 Score: {test_metrics.get('f1_score', 0) * 100:.1f}%"
                )
                console.print(
                    f"📈 Validation accuracy: {training_metrics.get('final_val_accuracy', 0) * 100:.1f}%"
                )
                console.print(
                    f"📉 Final loss: {training_metrics.get('final_train_loss', 0):.4f}"
                )
                console.print(
                    f"⏱️  Training time: {training_metrics.get('training_time_minutes', 0):.1f} minutes"
                )

                # Format model size from bytes
                model_size_bytes = model_info.get("model_size_bytes", 0)
                if model_size_bytes == 0:
                    console.print("💾 Model size: 0 bytes")
                elif model_size_bytes < 1024:
                    console.print(f"💾 Model size: {model_size_bytes} bytes")
                elif model_size_bytes < 1024 * 1024:
                    console.print(f"💾 Model size: {model_size_bytes / 1024:.1f} KB")
                else:
                    console.print(
                        f"💾 Model size: {model_size_bytes / (1024 * 1024):.1f} MB"
                    )

            except Exception as e:
                console.print(
                    f"❌ [red]Error retrieving training results: {str(e)}[/red]"
                )
                console.print(
                    "✅ [green]Training completed, but unable to fetch detailed results[/green]"
                )

            console.print("💾 Model training completed via AsyncCLIClient")

            # Debug: Check if we're still within the context
            if cli._http_client is not None and not cli._http_client.is_closed:
                console.print(
                    "✅ [green]Main AsyncCLIClient context is still active[/green]"
                )
            else:
                console.print(
                    "❌ [red]Main AsyncCLIClient context was closed unexpectedly[/red]"
                )

    except AsyncCLIClientError:
        # Re-raise CLI errors without wrapping
        raise
    except Exception as e:
        # Note: Fixed variable reference (was using undefined 'symbol' and 'timeframe')
        symbols_str = ", ".join(symbols) if symbols else "unknown"
        timeframes_str = ", ".join(timeframes) if timeframes else "unknown"
        raise DataError(
            message=f"Failed to train model for {symbols_str}",
            error_code="CLI-TrainModelError",
            details={
                "symbols": symbols,
                "timeframes": timeframes,
                "strategy": strategy_file,
                "error": str(e),
            },
        ) from e
