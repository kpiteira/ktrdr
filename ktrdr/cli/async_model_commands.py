"""Model commands using unified AsyncOperationExecutor pattern.

This module provides model training commands using the unified async operations
pattern with AsyncOperationExecutor and TrainingOperationAdapter.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ktrdr.cli.operation_adapters import TrainingOperationAdapter
from ktrdr.cli.operation_executor import AsyncOperationExecutor
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.cli.v3_utils import display_v3_dry_run, is_v3_strategy
from ktrdr.config.strategy_loader import StrategyConfigurationLoader, strategy_loader
from ktrdr.config.validation import InputValidator
from ktrdr.errors import ValidationError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for model commands
async_models_app = typer.Typer(
    name="models",
    help="Neural network model management commands",
    no_args_is_help=True,
)


@async_models_app.command("train")
@trace_cli_command("models_train")
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
    Train neural network models using strategy configurations.

    This command trains new models using the specified strategy configuration.
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

        # Handle v3 strategy dry-run BEFORE loading v2/legacy config
        # This displays detailed v3 info (indicators, fuzzy sets, features)
        if dry_run and is_v3_strategy(strategy_path):
            display_v3_dry_run(strategy_path)
            return

        # Load strategy configuration to extract symbols/timeframes if not provided
        try:
            if is_v3_strategy(strategy_path):
                # V3 strategy - use v3 loader
                loader = StrategyConfigurationLoader()
                v3_config = loader.load_v3_strategy(strategy_path)
                # Extract symbols (field is 'symbols', YAML uses 'list' alias)
                symbol_config = v3_config.training_data.symbols
                config_symbols = symbol_config.symbols or (
                    [symbol_config.symbol] if symbol_config.symbol else []
                )
                # Extract timeframes
                tf_config = v3_config.training_data.timeframes
                if tf_config.timeframes:
                    config_timeframes = tf_config.timeframes
                elif tf_config.timeframe:
                    config_timeframes = [tf_config.timeframe]
                else:
                    config_timeframes = []
            else:
                # V2 strategy - use legacy loader
                v2_config, _ = strategy_loader.load_strategy_config(str(strategy_path))
                config_symbols, config_timeframes = (
                    strategy_loader.extract_training_symbols_and_timeframes(v2_config)
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
    """Async implementation of train model command using unified executor pattern."""
    # Reduce HTTP logging noise unless verbose mode
    if not verbose:
        import logging

        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.WARNING)

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

    # Display training parameters
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
        console.print("   Analytics: [green]✅ Detailed analytics enabled[/green]")

    # Extract strategy name from file path
    strategy_name = Path(strategy_file).stem

    # Create adapter with training-specific parameters
    adapter = TrainingOperationAdapter(
        strategy_name=strategy_name,
        symbols=symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        validation_split=validation_split,
        detailed_analytics=detailed_analytics,
    )

    # Create executor for unified async operation handling
    executor = AsyncOperationExecutor()

    # Define training-specific progress message formatter
    def format_training_progress(operation_data: dict) -> str:
        """Format progress message with training-specific details.

        The TrainingProgressRenderer on the backend already formats rich progress
        messages and puts them in progress.current_step. We should use that first,
        and only fall back to manual construction if it's not available.
        """
        status = operation_data.get("status", "unknown")
        progress_info = operation_data.get("progress") or {}

        # First, try to use the pre-formatted message from TrainingProgressRenderer
        # This is in progress.current_step and should already contain epoch/batch/GPU info
        rendered_message = progress_info.get("current_step")
        if rendered_message and rendered_message != "Status: running":
            # Use the backend-rendered message directly
            return f"Status: {status} - {rendered_message}"

        # Fallback: extract context and build message manually
        progress_context = (
            progress_info.get("context") if progress_info else None
        ) or {}

        # Debug: log what we're receiving
        if verbose:
            logger.debug(
                f"Progress info: current_step={rendered_message}, context={progress_context}"
            )

        # Extract epoch information
        metadata = operation_data.get("metadata") or {}
        parameters = metadata.get("parameters") or {}
        total_epochs = parameters.get("epochs", 100)

        # Get current epoch from progress context (match TrainingProgressBridge field names)
        current_epoch = progress_context.get("epoch_index", 0)
        current_batch = progress_context.get("batch_number", 0)
        total_batches = progress_context.get("batch_total_per_epoch", 0)
        total_epochs_from_context = progress_context.get("total_epochs", total_epochs)

        # Build status message with epoch/batch info
        status_msg = f"Status: {status}"
        if current_epoch > 0:
            status_msg += f" (Epoch: {current_epoch}/{total_epochs_from_context}"
            if current_batch > 0 and total_batches > 0:
                status_msg += f", Batch: {current_batch}/{total_batches}"
            status_msg += ")"

        # Extract GPU info
        resource_usage = progress_context.get("resource_usage") or {}
        if resource_usage.get("gpu_used"):
            gpu_name = resource_usage.get("gpu_name", "GPU")
            gpu_util = resource_usage.get("gpu_utilization_percent")
            if gpu_util is not None:
                status_msg += f" 🖥️ {gpu_name}: {gpu_util:.0f}%"

        return status_msg

    # Execute operation - executor handles progress bar
    success = await executor.execute_operation(
        adapter=adapter,
        console=console,
        progress_callback=format_training_progress,
        show_progress=True,
    )

    # Exit with appropriate code
    sys.exit(0 if success else 1)
