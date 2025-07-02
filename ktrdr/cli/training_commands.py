"""Training commands for the main CLI."""

import asyncio
import signal
import typer
import yaml
import json
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
)
from datetime import datetime
import sys

from ktrdr.cli.api_client import get_api_client
from ktrdr.config.validation import InputValidator
from ktrdr.errors import ValidationError

# Rich console for formatted output
console = Console()
error_console = Console(stderr=True)

# Global variable to track cancellation
cancelled = False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global cancelled
    cancelled = True
    console.print("\n[yellow]⏹️  Cancellation requested. Stopping training...[/yellow]")


def train_strategy(
    strategy: str = typer.Argument(
        ..., help="Path to strategy YAML configuration file"
    ),
    symbol: str = typer.Argument(
        ..., help="Trading symbol to train on (e.g., AAPL, MSFT)"
    ),
    timeframe: str = typer.Argument(
        ..., help="Timeframe for training data (e.g., 1h, 4h, 1d)"
    ),
    start_date: str = typer.Option(
        ..., "--start-date", help="Start date for training data (YYYY-MM-DD)"
    ),
    end_date: str = typer.Option(
        ..., "--end-date", help="End date for training data (YYYY-MM-DD)"
    ),
    models_dir: str = typer.Option(
        "models", "--models-dir", help="Directory to store trained models"
    ),
    validation_split: float = typer.Option(
        0.2, "--validation-split", help="Fraction of data for validation"
    ),
    epochs: Optional[int] = typer.Option(
        None, "--epochs", help="Override number of training epochs"
    ),
    data_mode: str = typer.Option(
        "local", "--data-mode", help="Data loading mode: 'local', 'ib', or 'full'"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output with progress"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Validate configuration without training"
    ),
    save_model: Optional[str] = typer.Option(
        None, "--save-model", help="Save trained model with this name"
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress all output except errors"
    ),
    detailed_analytics: bool = typer.Option(
        False, "--detailed-analytics", help="Enable detailed training analytics with CSV/JSON export"
    ),
):
    """
    Train a neuro-fuzzy trading strategy using the KTRDR API.

    This command uses the async API to train neural network models with real-time
    progress updates. The training can be cancelled with Ctrl+C.

    Examples:
        ktrdr train strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-01-01 --end-date 2024-06-01
        ktrdr train strategies/momentum.yaml MSFT 4h --start-date 2023-01-01 --end-date 2024-01-01 --epochs 100 --save-model msft_momentum_v1
    """
    # Use asyncio to run the async function
    return asyncio.run(
        _train_strategy_async(
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            models_dir=models_dir,
            validation_split=validation_split,
            epochs=epochs,
            data_mode=data_mode,
            verbose=verbose,
            dry_run=dry_run,
            save_model=save_model,
            quiet=quiet,
            detailed_analytics=detailed_analytics,
        )
    )


async def _train_strategy_async(
    strategy: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    models_dir: str,
    validation_split: float,
    epochs: Optional[int],
    data_mode: str,
    verbose: bool,
    dry_run: bool,
    save_model: Optional[str],
    quiet: bool,
    detailed_analytics: bool,
):
    """Run training using async API with progress tracking."""
    global cancelled
    cancelled = False

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Get API client
    api_client = get_api_client()
    operation_id = None

    try:
        if not quiet:
            console.print("[cyan]🏋️ KTRDR Neural Network Training[/cyan]")
            console.print("=" * 50)

        # Validate inputs
        strategy_path = Path(strategy)
        if not strategy_path.exists():
            console.print(
                f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]"
            )
            raise typer.Exit(1)

        symbol_validated = InputValidator.validate_string(
            symbol.upper(),
            min_length=1,
            max_length=20,
            pattern=r"^[A-Za-z0-9\-\.]+$",
        )

        if validation_split <= 0 or validation_split >= 1:
            console.print(
                f"[red]❌ Error: Validation split must be between 0 and 1, got {validation_split}[/red]"
            )
            raise typer.Exit(1)

        # Load and prepare strategy configuration
        with open(strategy_path, "r") as f:
            strategy_config = yaml.safe_load(f)

        # Extract or build training config
        training_config = {
            "model_type": "mlp",
            "hidden_layers": [64, 32, 16],
            "epochs": epochs or 100,
            "learning_rate": 0.001,
            "batch_size": 32,
            "validation_split": validation_split,
            "early_stopping": {"patience": 10, "monitor": "val_accuracy"},
            "optimizer": "adam",
            "dropout_rate": 0.2,
        }

        # Override with strategy-specific config if available
        if "model" in strategy_config and "training" in strategy_config["model"]:
            training_config.update(strategy_config["model"]["training"])

        # Override epochs if specified
        if epochs:
            training_config["epochs"] = epochs

        if verbose and not quiet:
            console.print(f"📋 Configuration:")
            console.print(f"  Strategy: [blue]{strategy}[/blue]")
            console.print(f"  Symbol: [blue]{symbol_validated}[/blue]")
            console.print(f"  Timeframe: [blue]{timeframe}[/blue]")
            console.print(
                f"  Training Period: [blue]{start_date}[/blue] to [blue]{end_date}[/blue]"
            )
            console.print(f"  Epochs: [blue]{training_config['epochs']}[/blue]")
            console.print(f"  Validation Split: [blue]{validation_split:.1%}[/blue]")
            console.print(f"  Data Mode: [blue]{data_mode}[/blue]")
            if detailed_analytics:
                console.print("  Analytics: [green]✅ Detailed analytics enabled[/green]")
            console.print()

        if dry_run:
            if not quiet:
                console.print(
                    "[yellow]🔍 DRY RUN - No training will be started[/yellow]"
                )
            return None

        # Start training via API
        if not quiet:
            console.print("🚀 Starting neural network training...")

        response = await api_client.start_training(
            strategy_config=strategy_config,
            symbol=symbol_validated,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            training_config=training_config,
            models_dir=models_dir,
            data_mode=data_mode,
            validation_split=validation_split,
            dry_run=dry_run,
            detailed_analytics=detailed_analytics,
        )

        if not response.get("success"):
            console.print(
                f"[red]❌ Failed to start training: {response.get('error', 'Unknown error')}[/red]"
            )
            raise typer.Exit(1)

        # Get operation ID
        operation_id = response.get("task_id")

        if not quiet:
            console.print(f"⚡ Started training operation: {operation_id}")
            if response.get("estimated_duration_minutes"):
                console.print(
                    f"⏱️  Estimated duration: [yellow]{response['estimated_duration_minutes']} minutes[/yellow]"
                )

        # Poll for progress with Rich progress bar
        if not quiet and verbose:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("Training neural network...", total=100)

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
                        current_step = progress_info.get("current_step", "Training...")

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

                        # Build enhanced description with batch info
                        description = (
                            current_step[:70] + "..."
                            if len(current_step) > 70
                            else current_step
                        )

                        # Add items processed info if available (batches for training)
                        items_processed = progress_info.get("items_processed", 0)
                        items_total = progress_info.get("items_total")
                        if items_processed > 0:
                            if items_total:
                                description += (
                                    f" ({items_processed:,}/{items_total:,} batches)"
                                )
                            else:
                                description += f" ({items_processed:,} batches)"

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
                        await asyncio.sleep(2.0)

                    except Exception as e:
                        if not quiet:
                            console.print(
                                f"[yellow]Warning: Failed to get training status: {str(e)}[/yellow]"
                            )
                        break
        else:
            # Simple polling without progress display
            while not cancelled:
                try:
                    status_response = await api_client.get_operation_status(operation_id)
                    operation_data = status_response.get("data", {})
                    status = operation_data.get("status")

                    if status in ["completed", "failed", "cancelled"]:
                        break

                    await asyncio.sleep(5.0)

                except Exception as e:
                    if not quiet:
                        console.print(
                            f"[yellow]Warning: Failed to get training status: {str(e)}[/yellow]"
                        )
                    break

        # Handle cancellation
        if cancelled and operation_id:
            try:
                cancel_response = await api_client.cancel_operation(
                    operation_id=operation_id,
                    reason="User requested cancellation via CLI",
                )
                if not quiet:
                    console.print("⏹️  Training cancelled successfully")
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
                console.print(f"[red]❌ Training failed: {error_message}[/red]")
                raise typer.Exit(1)
            elif final_status == "cancelled":
                console.print("[yellow]⏹️  Training was cancelled[/yellow]")
                return None
        except Exception as e:
            console.print(f"[red]❌ Failed to get final status: {str(e)}[/red]")
            raise typer.Exit(1)

        # Get performance metrics
        try:
            performance_response = await api_client.get_training_performance(
                operation_id
            )
            if performance_response.get("success"):
                performance_data = performance_response["data"]

                if not quiet:
                    console.print(
                        f"\n[green]✅ Training completed successfully![/green]"
                    )
                    console.print(f"\n[cyan]📊 Performance Summary:[/cyan]")
                    console.print("=" * 50)

                    training_metrics = performance_data.get("training_metrics", {})
                    test_metrics = performance_data.get("test_metrics", {})

                    if training_metrics:
                        console.print(
                            f"📈 Final Training Accuracy: [cyan]{training_metrics.get('final_train_accuracy', 'N/A'):.3f}[/cyan]"
                        )
                        console.print(
                            f"📊 Final Validation Accuracy: [cyan]{training_metrics.get('final_val_accuracy', 'N/A'):.3f}[/cyan]"
                        )
                        console.print(
                            f"⏱️  Training Time: [yellow]{training_metrics.get('training_time_minutes', 'N/A'):.1f} minutes[/yellow]"
                        )

                    if test_metrics:
                        console.print(
                            f"🎯 Test Accuracy: [green]{test_metrics.get('test_accuracy', 'N/A'):.3f}[/green]"
                        )
                        console.print(
                            f"🔍 Precision: [green]{test_metrics.get('precision', 'N/A'):.3f}[/green]"
                        )
                        console.print(
                            f"📊 Recall: [green]{test_metrics.get('recall', 'N/A'):.3f}[/green]"
                        )
                        console.print(
                            f"🏆 F1 Score: [green]{test_metrics.get('f1_score', 'N/A'):.3f}[/green]"
                        )

                # Save model if requested
                if save_model and not quiet:
                    await _save_trained_model_async(
                        api_client, operation_id, save_model, verbose
                    )

        except Exception as e:
            console.print(
                f"[yellow]Warning: Failed to get performance metrics: {str(e)}[/yellow]"
            )

    except Exception as e:
        if "Ctrl+C" not in str(e):  # Don't show error for user cancellation
            console.print(f"[red]❌ Training failed: {str(e)}[/red]")
            if verbose and not quiet:
                import traceback

                console.print(traceback.format_exc())
        raise typer.Exit(1)


async def _save_trained_model_async(
    api_client, task_id: str, model_name: str, verbose: bool
):
    """Save the trained model using the API client."""
    try:
        console.print(f"\n💾 Saving model as '{model_name}'...")

        response = await api_client.save_model(
            task_id=task_id,
            model_name=model_name,
            description=f"Model trained via CLI on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )

        console.print(f"✅ Model saved successfully!")
        console.print(f"📋 Model ID: [cyan]{response.get('model_id')}[/cyan]")
        console.print(f"📁 Model Path: [green]{response.get('model_path')}[/green]")
        if response.get("model_size_mb"):
            console.print(
                f"💽 Size: [yellow]{response.get('model_size_mb'):.1f} MB[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error saving model: {e}[/red]")


def list_models(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    )
):
    """
    List all available trained neural network models.

    Example:
        ktrdr list-models
        ktrdr list-models --verbose
    """
    # Use asyncio to run the async function
    return asyncio.run(_list_models_async(verbose))


async def _list_models_async(verbose: bool):
    """List models using the API client."""
    try:
        api_client = get_api_client()

        console.print(f"\n📋 [bold blue]Available Neural Network Models[/bold blue]")
        console.print("=" * 50)

        models = await api_client.list_models()

        if not models:
            console.print("No trained models found.")
            return

        console.print(f"Found {len(models)} trained models:\n")

        for model in models:
            console.print(f"🧠 [bold cyan]{model.get('model_name', 'N/A')}[/bold cyan]")
            console.print(f"  Symbol: [blue]{model.get('symbol', 'N/A')}[/blue]")
            console.print(f"  Timeframe: [blue]{model.get('timeframe', 'N/A')}[/blue]")
            console.print(
                f"  Created: [yellow]{model.get('created_at', 'N/A')}[/yellow]"
            )

            if verbose:
                console.print(f"  Model ID: [dim]{model.get('model_id', 'N/A')}[/dim]")
                console.print(
                    f"  Training Accuracy: [green]{model.get('training_accuracy', 'N/A'):.3f}[/green]"
                )
                console.print(
                    f"  Test Accuracy: [green]{model.get('test_accuracy', 'N/A'):.3f}[/green]"
                )
                if model.get("description"):
                    console.print(
                        f"  Description: [dim]{model.get('description')}[/dim]"
                    )

            console.print()

    except Exception as e:
        error_console.print(f"[bold red]Error listing models:[/bold red] {str(e)}")
        if verbose:
            import traceback

            error_console.print(traceback.format_exc())
        sys.exit(1)


def test_model(
    model_name: str = typer.Argument(..., help="Name of the model to test"),
    symbol: str = typer.Argument(
        ..., help="Trading symbol to test on (e.g., AAPL, MSFT)"
    ),
    timeframe: str = typer.Option(
        "1h", "--timeframe", "-t", help="Timeframe for prediction"
    ),
    test_date: Optional[str] = typer.Option(
        None, "--test-date", help="Specific date to test (YYYY-MM-DD)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed prediction information"
    ),
):
    """
    Test a trained neural network model's prediction capability.

    Examples:
        ktrdr test-model aapl_momentum_v1 AAPL
        ktrdr test-model msft_strategy MSFT --timeframe 4h --test-date 2024-06-01
    """
    # Use asyncio to run the async function
    return asyncio.run(
        _test_model_async(model_name, symbol, timeframe, test_date, verbose)
    )


async def _test_model_async(
    model_name: str,
    symbol: str,
    timeframe: str,
    test_date: Optional[str],
    verbose: bool,
):
    """Test model using the API client."""
    try:
        api_client = get_api_client()

        console.print(f"\n🧠 [bold blue]Testing Model: {model_name}[/bold blue]")
        console.print("=" * 50)
        console.print(f"Loading model...")

        # First load the model
        load_response = await api_client.load_model(model_name)
        console.print(f"✅ Model loaded successfully!")

        # Show model info if verbose
        if verbose:
            model_info = load_response.get("model_info", {})
            console.print(f"\n📋 Model Information:")
            console.print(f"  Symbol: [blue]{model_info.get('symbol', 'N/A')}[/blue]")
            console.print(
                f"  Timeframe: [blue]{model_info.get('timeframe', 'N/A')}[/blue]"
            )
            console.print(
                f"  Architecture: [cyan]{model_info.get('architecture', 'N/A')}[/cyan]"
            )
            console.print(
                f"  Training Accuracy: [green]{model_info.get('training_accuracy', 'N/A'):.3f}[/green]"
            )
            console.print(
                f"  Test Accuracy: [green]{model_info.get('test_accuracy', 'N/A'):.3f}[/green]"
            )

        # Make prediction
        console.print(f"\n🔮 Making prediction...")

        symbol_validated = InputValidator.validate_string(
            symbol.upper(),
            min_length=1,
            max_length=20,
            pattern=r"^[A-Za-z0-9\-\.]+$",
        )

        prediction_response = await api_client.predict(
            model_name=model_name,
            symbol=symbol_validated,
            timeframe=timeframe,
            test_date=test_date,
        )

        prediction = prediction_response.get("prediction", {})
        input_features = prediction_response.get("input_features", {})

        console.print(f"\n🎯 [bold green]Prediction Results[/bold green]")
        console.print(f"  Symbol: [blue]{prediction_response.get('symbol')}[/blue]")
        console.print(
            f"  Test Date: [yellow]{prediction_response.get('test_date')}[/yellow]"
        )
        console.print(
            f"  Signal: [bold cyan]{prediction.get('signal', 'N/A').upper()}[/bold cyan]"
        )
        console.print(
            f"  Confidence: [green]{prediction.get('confidence', 0):.1%}[/green]"
        )
        console.print(
            f"  Signal Strength: [yellow]{prediction.get('signal_strength', 0):.3f}[/yellow]"
        )

        # Show fuzzy outputs
        fuzzy_outputs = prediction.get("fuzzy_outputs", {})
        if fuzzy_outputs:
            console.print(f"\n🔀 Fuzzy Logic Outputs:")
            console.print(
                f"  Bullish: [green]{fuzzy_outputs.get('bullish', 0):.3f}[/green]"
            )
            console.print(
                f"  Bearish: [red]{fuzzy_outputs.get('bearish', 0):.3f}[/red]"
            )
            console.print(
                f"  Neutral: [yellow]{fuzzy_outputs.get('neutral', 0):.3f}[/yellow]"
            )

        # Show input features if verbose
        if verbose and input_features:
            console.print(f"\n📊 Input Features:")
            for feature, value in input_features.items():
                console.print(f"  {feature}: [cyan]{value:.4f}[/cyan]")

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error testing model:[/bold red] {str(e)}")
        if verbose:
            import traceback

            error_console.print(traceback.format_exc())
        sys.exit(1)
