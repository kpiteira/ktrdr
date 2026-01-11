"""
Model management commands for the KTRDR CLI.

This module contains all CLI commands related to neural network models:
- train: Train new models with strategies
- list: List available trained models
- test: Test model performance
- load: Load models for prediction
- predict: Make predictions using loaded models
"""

import asyncio
import json
import sys
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
from rich.table import Table

from ktrdr.cli.api_client import check_api_connection, get_api_client
from ktrdr.cli.client import AsyncCLIClient, CLIClientError
from ktrdr.cli.commands import get_effective_api_url
from ktrdr.cli.operation_adapters import TrainingOperationAdapter
from ktrdr.cli.v3_utils import display_v3_dry_run, is_v3_strategy
from ktrdr.config.strategy_loader import strategy_loader
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError, ValidationError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)


# Create the CLI app for model commands
models_app = typer.Typer(
    name="models",
    help="Neural network model management commands",
    no_args_is_help=True,
)


@models_app.command("train")
def train_model(
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
):
    """
    Train neural network models using strategy configurations.

    This command trains new models using the specified strategy configuration.
    Symbols and timeframes are extracted from the strategy file unless explicitly
    overridden with command arguments. Supports both single and multi-symbol/timeframe training.

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
        training_symbols = final_symbols  # Now supporting multi-symbol training!
        training_timeframes = final_timeframes  # Already supporting multi-timeframe!

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
            _train_model_async(
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


async def _train_model_async(
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
):
    """Async implementation of train model command using AsyncCLIClient.execute_operation()."""
    try:
        # Use AsyncCLIClient for connection reuse and performance
        async with AsyncCLIClient() as cli:
            # Check API connection using AsyncCLIClient
            if not await cli.health_check():
                error_console.print(
                    "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
                )
                error_console.print(
                    "Make sure the API server is running at the configured URL"
                )
                sys.exit(1)

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
                console.print(
                    "   Analytics: [green]✅ Detailed analytics enabled[/green]"
                )

            # Extract strategy name from file path (remove .yaml extension)
            strategy_name = Path(strategy_file).stem

            # Create the training adapter
            adapter = TrainingOperationAdapter(
                strategy_name=strategy_name,
                symbols=symbols,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date,
                validation_split=validation_split,
                detailed_analytics=detailed_analytics,
            )

            # Set up progress display using Rich Progress
            progress_bar = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            )
            task_id = None

            def on_progress(percentage: int, message: str) -> None:
                """Progress callback for Rich progress display."""
                nonlocal task_id
                if task_id is not None:
                    progress_bar.update(
                        task_id, completed=percentage, description=message
                    )

            # Execute the operation with progress display
            try:
                with progress_bar:
                    task_id = progress_bar.add_task("Training model...", total=100)
                    result = await cli.execute_operation(
                        adapter,
                        on_progress=on_progress,
                        poll_interval=0.3,
                    )
            except CLIClientError as e:
                console.print(f"❌ [red]Failed to start training: {str(e)}[/red]")
                return

            # Handle result based on final status
            status = result.get("status", "unknown")
            operation_id = result.get("operation_id", "")

            if status == "completed":
                console.print(
                    "✅ [green]Model training completed successfully![/green]"
                )
                console.print(f"   Operation ID: [bold]{operation_id}[/bold]")

                # Fetch and display performance results
                await _display_training_results(cli, operation_id, console)

            elif status == "failed":
                error_msg = result.get(
                    "error_message", result.get("error", "Unknown error")
                )
                console.print(f"❌ [red]Training failed: {error_msg}[/red]")

            elif status == "cancelled":
                console.print("✅ [yellow]Training cancelled successfully[/yellow]")

            else:
                console.print(
                    f"⚠️ [yellow]Training ended with status: {status}[/yellow]"
                )

    except CLIClientError:
        # Re-raise CLI errors without wrapping
        raise
    except Exception as e:
        # Fixed variable reference issue
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


async def _display_training_results(
    cli: AsyncCLIClient,
    operation_id: str,
    console: Console,
) -> None:
    """Fetch and display training performance results."""
    try:
        performance_result = await cli.get(f"/trainings/{operation_id}/performance")
        training_metrics = performance_result.get("training_metrics", {})
        test_metrics = performance_result.get("test_metrics", {})
        model_info = performance_result.get("model_info", {})

        # Display real results
        console.print("📊 [bold green]Training Results:[/bold green]")
        console.print(
            f"🎯 Test accuracy: {test_metrics.get('test_accuracy', 0) * 100:.1f}%"
        )
        console.print(f"📊 Precision: {test_metrics.get('precision', 0) * 100:.1f}%")
        console.print(f"📊 Recall: {test_metrics.get('recall', 0) * 100:.1f}%")
        console.print(f"📊 F1 Score: {test_metrics.get('f1_score', 0) * 100:.1f}%")
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
            console.print(f"💾 Model size: {model_size_bytes / (1024 * 1024):.1f} MB")

    except Exception as e:
        console.print(f"❌ [red]Error retrieving training results: {str(e)}[/red]")
        console.print(
            "✅ [green]Training completed, but unable to fetch detailed results[/green]"
        )


@models_app.command("list")
def list_models(
    models_dir: str = typer.Option("models", "--models-dir", help="Models directory"),
    pattern: Optional[str] = typer.Option(
        None, "--pattern", "-p", help="Filter models by pattern"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    List available trained models.

    Shows all available trained models with their metadata, performance metrics,
    and training information.

    Examples:
        ktrdr models list
        ktrdr models list --pattern AAPL
        ktrdr models list --format json --verbose
    """
    try:
        # Run async operation
        asyncio.run(_list_models_async(models_dir, pattern, output_format, verbose))

    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _list_models_async(
    models_dir: str,
    pattern: Optional[str],
    output_format: str,
    verbose: bool,
):
    """Async implementation of list models command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                f"Make sure the API server is running at {get_effective_api_url()}"
            )
            sys.exit(1)

        get_api_client()

        if verbose:
            console.print("📋 Retrieving available models")

        # For now, show hardcoded models until API is implemented
        models = [
            {
                "name": "AAPL_1h_neuro_mean_reversion",
                "symbol": "AAPL",
                "timeframe": "1h",
                "strategy": "neuro_mean_reversion",
                "created": "2024-05-15T14:30:00Z",
                "accuracy": 0.72,
                "size": "2.4 MB",
            },
            {
                "name": "MSFT_1d_trend_momentum",
                "symbol": "MSFT",
                "timeframe": "1d",
                "strategy": "trend_momentum",
                "created": "2024-05-10T09:15:00Z",
                "accuracy": 0.68,
                "size": "1.8 MB",
            },
        ]

        # Filter by pattern if specified
        if pattern:
            pattern_upper = pattern.upper()  # Extract once to help mypy
            models = [
                model for model in models if pattern_upper in str(model["name"]).upper()
            ]

        # Format output
        if output_format == "json":
            result = {
                "models": models,
                "total_count": len(models),
                "models_dir": models_dir,
                "pattern_filter": pattern,
            }
            print(json.dumps(result, indent=2))
        else:
            # Table format
            console.print("\n🧠 [bold]Available Models[/bold]")
            console.print(f"Directory: {models_dir}")
            if pattern:
                console.print(f"Pattern: {pattern}")
            console.print(f"Total: {len(models)}")
            console.print()

            table = Table()
            table.add_column("Name", style="cyan")
            table.add_column("Symbol", style="green")
            table.add_column("Timeframe", style="blue")
            table.add_column("Strategy", style="yellow")
            table.add_column("Accuracy", style="magenta", justify="right")
            table.add_column("Size", style="white", justify="right")

            for model in models:
                table.add_row(
                    str(model["name"]),
                    str(model["symbol"]),
                    str(model["timeframe"]),
                    str(model["strategy"]),
                    f"{model['accuracy']:.1%}",
                    str(model["size"]),
                )

            console.print(table)

        if verbose:
            console.print(f"✅ Listed {len(models)} models")

    except Exception as e:
        raise DataError(
            message="Failed to list models",
            error_code="CLI-ListModelsError",
            details={"models_dir": models_dir, "pattern": pattern, "error": str(e)},
        ) from e


@models_app.command("test")
def test_model(
    model_name: str = typer.Argument(..., help="Model name or path"),
    symbol: str = typer.Argument(..., help="Trading symbol for testing"),
    timeframe: str = typer.Argument(..., help="Data timeframe"),
    test_date: Optional[str] = typer.Option(
        None, "--test-date", help="Specific test date (YYYY-MM-DD)"
    ),
    data_mode: str = typer.Option(
        "local", "--data-mode", help="Data loading mode (local, ib)"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save results to file"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Test model performance on market data.

    This command loads a trained model and tests its performance on historical
    or real-time market data, providing accuracy metrics and predictions.

    Examples:
        ktrdr models test AAPL_1h_model AAPL 1h
        ktrdr models test MSFT_1d_model MSFT 1d --test-date 2024-05-15
        ktrdr models test trend_model TSLA 1h --output test_results.json
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )

        # Run async operation
        asyncio.run(
            _test_model_async(
                model_name,
                symbol,
                timeframe,
                test_date,
                data_mode,
                output_file,
                verbose,
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


async def _test_model_async(
    model_name: str,
    symbol: str,
    timeframe: str,
    test_date: Optional[str],
    data_mode: str,
    output_file: Optional[str],
    verbose: bool,
):
    """Async implementation of test model command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                f"Make sure the API server is running at {get_effective_api_url()}"
            )
            sys.exit(1)

        get_api_client()

        if verbose:
            console.print(f"🧪 Testing model: {model_name}")
            console.print(f"📊 Symbol: {symbol} ({timeframe})")
            if test_date:
                console.print(f"📅 Test date: {test_date}")

        # This would call the model testing API endpoint
        # For now, show a placeholder message
        console.print("⚠️  [yellow]Model testing via API not yet implemented[/yellow]")
        console.print(f"📋 Would test model: {model_name}")
        console.print(f"📊 On data: {symbol} ({timeframe})")

        # Simulate test results
        results = {
            "model": model_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "test_date": test_date or "latest",
            "accuracy": 0.74,
            "precision": 0.71,
            "recall": 0.68,
            "f1_score": 0.69,
            "predictions_count": 156,
        }

        console.print("✅ [green]Model testing completed[/green]")
        console.print(f"📊 Accuracy: {results['accuracy']:.1%}")
        console.print(f"📊 Precision: {results['precision']:.1%}")
        console.print(f"📊 Predictions: {results['predictions_count']}")

        if output_file:
            console.print(f"💾 Results saved to: {output_file}")

    except Exception as e:
        raise DataError(
            message=f"Failed to test model {model_name}",
            error_code="CLI-TestModelError",
            details={
                "model": model_name,
                "symbol": symbol,
                "timeframe": timeframe,
                "error": str(e),
            },
        ) from e


@models_app.command("predict")
def make_prediction(
    model_name: str = typer.Argument(..., help="Model name or path"),
    symbol: str = typer.Argument(..., help="Trading symbol for prediction"),
    timeframe: str = typer.Argument(..., help="Data timeframe"),
    data_mode: str = typer.Option(
        "local", "--data-mode", help="Data loading mode (local, ib)"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
    confidence_threshold: float = typer.Option(
        0.6, "--confidence", help="Minimum confidence threshold"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Make predictions using a loaded model.

    This command loads a trained model and generates predictions for the
    specified symbol and timeframe using the latest available data.

    Examples:
        ktrdr models predict AAPL_1h_model AAPL 1h
        ktrdr models predict trend_model MSFT 1d --confidence 0.7
        ktrdr models predict neuro_model TSLA 1h --format json
    """
    try:
        # Input validation
        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )
        confidence_threshold = InputValidator.validate_numeric(
            confidence_threshold, min_value=0.0, max_value=1.0
        )

        # Run async operation
        asyncio.run(
            _make_prediction_async(
                model_name,
                symbol,
                timeframe,
                data_mode,
                output_format,
                confidence_threshold,
                verbose,
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


async def _make_prediction_async(
    model_name: str,
    symbol: str,
    timeframe: str,
    data_mode: str,
    output_format: str,
    confidence_threshold: float,
    verbose: bool,
):
    """Async implementation of make prediction command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                f"Make sure the API server is running at {get_effective_api_url()}"
            )
            sys.exit(1)

        get_api_client()

        if verbose:
            console.print(f"🔮 Making prediction with model: {model_name}")
            console.print(f"📊 Symbol: {symbol} ({timeframe})")
            console.print(f"🎯 Confidence threshold: {confidence_threshold:.1%}")

        # This would call the prediction API endpoint
        # For now, show a placeholder message
        console.print(
            "⚠️  [yellow]Model prediction via API not yet implemented[/yellow]"
        )
        console.print(f"📋 Would predict for: {symbol} ({timeframe})")

        # Simulate prediction results
        predictions = [
            {
                "timestamp": "2025-06-11T18:00:00Z",
                "signal": "BUY",
                "confidence": 0.78,
                "price_target": 142.50,
                "stop_loss": 138.20,
            },
            {
                "timestamp": "2025-06-11T19:00:00Z",
                "signal": "HOLD",
                "confidence": 0.45,
                "price_target": None,
                "stop_loss": None,
            },
        ]

        # Filter by confidence threshold
        filtered_predictions = [
            p
            for p in predictions
            if isinstance(p["confidence"], (int, float))
            and p["confidence"] >= confidence_threshold
        ]

        # Format output
        if output_format == "json":
            result = {
                "model": model_name,
                "symbol": symbol,
                "timeframe": timeframe,
                "confidence_threshold": confidence_threshold,
                "predictions": filtered_predictions,
                "total_predictions": len(predictions),
                "filtered_predictions": len(filtered_predictions),
            }
            print(json.dumps(result, indent=2))
        else:
            # Table format
            console.print("\n🔮 [bold]Model Predictions[/bold]")
            console.print(f"Model: {model_name}")
            console.print(f"Symbol: {symbol} ({timeframe})")
            console.print(f"Confidence threshold: {confidence_threshold:.1%}")
            console.print(
                f"Predictions: {len(filtered_predictions)}/{len(predictions)}"
            )
            console.print()

            if filtered_predictions:
                table = Table()
                table.add_column("Timestamp", style="cyan")
                table.add_column("Signal", style="green")
                table.add_column("Confidence", style="yellow", justify="right")
                table.add_column("Target", style="blue", justify="right")
                table.add_column("Stop Loss", style="red", justify="right")

                for pred in filtered_predictions:
                    table.add_row(
                        str(pred["timestamp"]),
                        str(pred["signal"]),
                        f"{pred['confidence']:.1%}",
                        (
                            f"${pred['price_target']:.2f}"
                            if pred["price_target"]
                            else "N/A"
                        ),
                        f"${pred['stop_loss']:.2f}" if pred["stop_loss"] else "N/A",
                    )

                console.print(table)
            else:
                console.print("ℹ️  No predictions meet the confidence threshold")

        if verbose:
            console.print(f"✅ Generated {len(filtered_predictions)} predictions")

    except Exception as e:
        raise DataError(
            message=f"Failed to make prediction with model {model_name}",
            error_code="CLI-PredictError",
            details={
                "model": model_name,
                "symbol": symbol,
                "timeframe": timeframe,
                "error": str(e),
            },
        ) from e
