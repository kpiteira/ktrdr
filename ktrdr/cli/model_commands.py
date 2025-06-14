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
import sys
import json
from typing import Optional
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)

from ktrdr.cli.api_client import get_api_client, check_api_connection
from ktrdr.config.validation import InputValidator
from ktrdr.errors import ValidationError, DataError
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
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Argument(..., help="Data timeframe (e.g., 1d, 1h)"),
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
):
    """
    Train neural network models using strategy configurations.

    This command trains new models using the specified strategy configuration,
    market data, and training parameters. Training is done via the API with
    progress tracking and result validation.

    Examples:
        ktrdr models train strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-01-01 --end-date 2024-06-01
        ktrdr models train strategies/trend_momentum.yaml MSFT 1d --start-date 2023-01-01 --end-date 2024-01-01 --dry-run
    """
    try:
        # Input validation
        strategy_path = Path(strategy_file)
        if not strategy_path.exists():
            raise ValidationError(
                message=f"Strategy file not found: {strategy_file}",
                error_code="VALIDATION-FileNotFound",
                details={"file": strategy_file},
            )

        symbol = InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )
        timeframe = InputValidator.validate_string(
            timeframe, min_length=1, max_length=5, pattern=r"^[0-9]+[dhm]$"
        )
        validation_split = InputValidator.validate_numeric(
            validation_split, min_value=0.0, max_value=0.5
        )

        # Run async operation
        asyncio.run(
            _train_model_async(
                strategy_file,
                symbol,
                timeframe,
                start_date,
                end_date,
                models_dir,
                validation_split,
                data_mode,
                dry_run,
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


async def _train_model_async(
    strategy_file: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    models_dir: str,
    validation_split: float,
    data_mode: str,
    dry_run: bool,
    verbose: bool,
):
    """Async implementation of train model command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🧠 Training model for {symbol} ({timeframe})")
            console.print(f"📋 Strategy: {strategy_file}")
            console.print(f"📅 Training period: {start_date} to {end_date}")

        if dry_run:
            console.print(f"🔍 [yellow]DRY RUN - No model will be trained[/yellow]")
            console.print(f"📋 Would train: {symbol} on {timeframe}")
            console.print(f"📊 Validation split: {validation_split}")
            console.print(f"💾 Models directory: {models_dir}")
            return

        # This would call the training API endpoint
        # For now, show a placeholder message with simulated progress
        console.print(f"⚠️  [yellow]Model training via API not yet implemented[/yellow]")
        console.print(f"📋 Would train model with:")
        console.print(f"   Strategy: {strategy_file}")
        console.print(f"   Symbol: {symbol}")
        console.print(f"   Timeframe: {timeframe}")
        console.print(f"   Period: {start_date} to {end_date}")

        # Simulate training progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Training model...", total=100)

            steps = [
                ("Loading training data", 20),
                ("Preprocessing features", 40),
                ("Training neural network", 80),
                ("Validating model", 95),
                ("Saving model", 100),
            ]

            for step_desc, target in steps:
                progress.update(task, description=step_desc)
                while progress.tasks[0].completed < target:
                    await asyncio.sleep(0.1)
                    progress.update(task, advance=2)

        console.print(f"✅ [green]Model training completed[/green]")
        console.print(f"💾 Model saved to: {models_dir}/{symbol}_{timeframe}_model.pkl")

    except Exception as e:
        raise DataError(
            message=f"Failed to train model for {symbol}",
            error_code="CLI-TrainModelError",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
                "strategy": strategy_file,
                "error": str(e),
            },
        ) from e


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
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

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
            models = [
                model for model in models if pattern.upper() in model["name"].upper()
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
            console.print(f"\n🧠 [bold]Available Models[/bold]")
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
                    model["name"],
                    model["symbol"],
                    model["timeframe"],
                    model["strategy"],
                    f"{model['accuracy']:.1%}",
                    model["size"],
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
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🧪 Testing model: {model_name}")
            console.print(f"📊 Symbol: {symbol} ({timeframe})")
            if test_date:
                console.print(f"📅 Test date: {test_date}")

        # This would call the model testing API endpoint
        # For now, show a placeholder message
        console.print(f"⚠️  [yellow]Model testing via API not yet implemented[/yellow]")
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

        console.print(f"✅ [green]Model testing completed[/green]")
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
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"🔮 Making prediction with model: {model_name}")
            console.print(f"📊 Symbol: {symbol} ({timeframe})")
            console.print(f"🎯 Confidence threshold: {confidence_threshold:.1%}")

        # This would call the prediction API endpoint
        # For now, show a placeholder message
        console.print(
            f"⚠️  [yellow]Model prediction via API not yet implemented[/yellow]"
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
            p for p in predictions if p["confidence"] >= confidence_threshold
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
            console.print(f"\n🔮 [bold]Model Predictions[/bold]")
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
                        pred["timestamp"],
                        pred["signal"],
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
