"""Training commands for the main CLI."""

import typer
import asyncio
import httpx
import yaml
import json
import time
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from datetime import datetime
import sys

from ktrdr.config.validation import InputValidator
from ktrdr.errors import ValidationError

# Rich console for formatted output
console = Console()
error_console = Console(stderr=True)


def train_strategy(
    strategy: str = typer.Argument(..., help="Path to strategy YAML configuration file"),
    symbol: str = typer.Argument(..., help="Trading symbol to train on (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Argument(..., help="Timeframe for training data (e.g., 1h, 4h, 1d)"),
    start_date: str = typer.Option(..., "--start-date", help="Start date for training data (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end-date", help="End date for training data (YYYY-MM-DD)"),
    models_dir: str = typer.Option("models", "--models-dir", help="Directory to store trained models"),
    validation_split: float = typer.Option(0.2, "--validation-split", help="Fraction of data for validation"),
    epochs: Optional[int] = typer.Option(None, "--epochs", help="Override number of training epochs"),
    data_mode: str = typer.Option("local", "--data-mode", help="Data loading mode: 'local', 'ib', or 'full'"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate configuration without training"),
    save_model: Optional[str] = typer.Option(None, "--save-model", help="Save trained model with this name"),
):
    """
    Train a neuro-fuzzy trading strategy using the KTRDR API.
    
    This command trains a neural network model based on the strategy configuration,
    using historical price data and technical indicators with fuzzy logic.
    
    Examples:
        ktrdr train strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-01-01 --end-date 2024-06-01
        ktrdr train strategies/momentum.yaml MSFT 4h --start-date 2023-01-01 --end-date 2024-01-01 --epochs 100 --save-model msft_momentum_v1
    """
    
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"

    async def call_training_api():
        """Call the training API endpoints."""
        try:
            # Validate inputs
            strategy_path = Path(strategy)
            if not strategy_path.exists():
                raise ValidationError(f"Strategy file not found: {strategy_path}")
            
            symbol_validated = InputValidator.validate_string(
                symbol.upper(), min_length=1, max_length=20, pattern=r"^[A-Za-z0-9\-\.]+$"
            )
            
            if validation_split <= 0 or validation_split >= 1:
                raise ValidationError(f"Validation split must be between 0 and 1, got {validation_split}")

            # Load and prepare strategy configuration
            with open(strategy_path, 'r') as f:
                strategy_config = yaml.safe_load(f)
            
            # Extract or build training config
            training_config = {
                "model_type": "mlp",
                "hidden_layers": [64, 32, 16],
                "epochs": epochs or 100,
                "learning_rate": 0.001,
                "batch_size": 32,
                "validation_split": validation_split,
                "early_stopping": {
                    "patience": 10,
                    "monitor": "val_accuracy"
                },
                "optimizer": "adam",
                "dropout_rate": 0.2
            }
            
            # Override with strategy-specific config if available
            if 'model' in strategy_config and 'training' in strategy_config['model']:
                training_config.update(strategy_config['model']['training'])
            
            # Override epochs if specified
            if epochs:
                training_config['epochs'] = epochs

            # Build request payload
            payload = {
                "symbol": symbol_validated,
                "timeframe": timeframe,
                "config": training_config,
                "start_date": start_date,
                "end_date": end_date
            }

            console.print(f"\n🏋️ [bold blue]KTRDR Neural Network Training[/bold blue]")
            console.print("=" * 50)
            console.print(f"📋 Configuration:")
            console.print(f"  Strategy: [blue]{strategy}[/blue]")
            console.print(f"  Symbol: [blue]{symbol_validated}[/blue]") 
            console.print(f"  Timeframe: [blue]{timeframe}[/blue]")
            console.print(f"  Training Period: [blue]{start_date}[/blue] to [blue]{end_date}[/blue]")
            console.print(f"  Epochs: [blue]{training_config['epochs']}[/blue]")
            console.print(f"  Validation Split: [blue]{validation_split:.1%}[/blue]")
            console.print(f"  Data Mode: [blue]{data_mode}[/blue]")
            console.print()
            
            if dry_run:
                console.print("[yellow]🔍 DRY RUN - No training will be started[/yellow]")
                console.print(f"Would send request: {json.dumps(payload, indent=2)}")
                return

            # Show request details if verbose
            if verbose:
                console.print(f"Request payload:")
                console.print(json.dumps(payload, indent=2))
                console.print()

            # Start training
            console.print(f"🚀 [green]Starting neural network training...[/green]")
            start_time = datetime.now()
            
            async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout for start
                response = await client.post(
                    "http://localhost:8000/api/v1/training/start",
                    json=payload
                )
                
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    task_id = result['task_id']
                    console.print(f"✅ Training started successfully!")
                    console.print(f"📋 Task ID: [cyan]{task_id}[/cyan]")
                    console.print(f"⏱️  Estimated duration: [yellow]{result.get('estimated_duration_minutes', 30)} minutes[/yellow]")
                    console.print()
                    
                    # Monitor training progress
                    await monitor_training_progress(task_id, verbose)
                    
                    # Save model if requested
                    if save_model:
                        await save_trained_model(task_id, save_model, verbose)
                    
                else:
                    error_console.print(f"[bold red]Training failed:[/bold red] {result.get('message', 'Unknown error')}")
                    sys.exit(1)
            else:
                error_console.print(f"[bold red]API Error:[/bold red] {response.status_code}")
                try:
                    error_detail = response.json().get('detail', response.text)
                    error_console.print(f"Details: {error_detail}")
                except:
                    error_console.print(f"Response: {response.text}")
                sys.exit(1)
                
        except ValidationError as e:
            error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
            sys.exit(1)
        except httpx.ConnectError:
            error_console.print("[bold red]Connection error:[/bold red] Could not connect to KTRDR API server")
            error_console.print("Make sure the API server is running at http://localhost:8000")
            sys.exit(1)
        except httpx.TimeoutException:
            error_console.print("[bold red]Timeout error:[/bold red] Request took longer than 5 minutes")
            error_console.print("Training startup should be quick. Check API server status.")
            sys.exit(1)
        except Exception as e:
            error_console.print(f"[bold red]Unexpected error:[/bold red] {str(e)}")
            if verbose:
                import traceback
                error_console.print(traceback.format_exc())
            sys.exit(1)

    async def monitor_training_progress(task_id: str, verbose: bool):
        """Monitor training progress with live updates."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("Training neural network...", total=100)
            
            completed = False
            last_progress = 0
            
            while not completed:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(f"http://localhost:8000/api/v1/training/{task_id}")
                    
                    if response.status_code == 200:
                        status = response.json()
                        current_progress = status.get('progress', 0)
                        training_status = status.get('status', 'unknown')
                        current_epoch = status.get('current_epoch', 0)
                        total_epochs = status.get('total_epochs', 100)
                        
                        # Update progress bar
                        progress.update(task, completed=current_progress)
                        
                        # Update description with current info
                        if current_epoch:
                            progress.update(task, description=f"Training... Epoch {current_epoch}/{total_epochs}")
                        
                        # Show metrics if verbose and available
                        if verbose and status.get('current_metrics') and current_progress > last_progress:
                            metrics = status['current_metrics']
                            console.print(f"  📊 Epoch {current_epoch}: Loss={metrics.get('train_loss', 'N/A'):.4f}, Accuracy={metrics.get('train_accuracy', 'N/A'):.3f}")
                        
                        last_progress = current_progress
                        
                        # Check if training is complete
                        if training_status == 'completed':
                            completed = True
                            progress.update(task, completed=100, description="Training completed!")
                        elif training_status == 'failed':
                            error_msg = status.get('error', 'Unknown error')
                            progress.update(task, description=f"Training failed: {error_msg}")
                            completed = True
                            sys.exit(1)
                        
                    else:
                        console.print(f"[yellow]Warning: Could not get training status (HTTP {response.status_code})[/yellow]")
                    
                    if not completed:
                        await asyncio.sleep(5)  # Check every 5 seconds
                        
                except httpx.ConnectError:
                    console.print("[yellow]Warning: Lost connection to API server, retrying...[/yellow]")
                    await asyncio.sleep(10)
                except Exception as e:
                    if verbose:
                        console.print(f"[yellow]Warning: Error checking status: {e}[/yellow]")
                    await asyncio.sleep(10)
        
        # Get final performance metrics
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"http://localhost:8000/api/v1/training/{task_id}/performance")
            
            if response.status_code == 200:
                performance = response.json()
                if performance.get('success'):
                    console.print(f"\n📊 [bold green]Training Results:[/bold green]")
                    
                    training_metrics = performance.get('training_metrics', {})
                    test_metrics = performance.get('test_metrics', {})
                    
                    if training_metrics:
                        console.print(f"  Final Training Accuracy: [cyan]{training_metrics.get('final_train_accuracy', 'N/A'):.3f}[/cyan]")
                        console.print(f"  Final Validation Accuracy: [cyan]{training_metrics.get('final_val_accuracy', 'N/A'):.3f}[/cyan]")
                        console.print(f"  Training Time: [yellow]{training_metrics.get('training_time_minutes', 'N/A'):.1f} minutes[/yellow]")
                    
                    if test_metrics:
                        console.print(f"  Test Accuracy: [green]{test_metrics.get('test_accuracy', 'N/A'):.3f}[/green]")
                        console.print(f"  Precision: [green]{test_metrics.get('precision', 'N/A'):.3f}[/green]")
                        console.print(f"  Recall: [green]{test_metrics.get('recall', 'N/A'):.3f}[/green]")
                        console.print(f"  F1 Score: [green]{test_metrics.get('f1_score', 'N/A'):.3f}[/green]")
                        
        except Exception as e:
            if verbose:
                console.print(f"[yellow]Warning: Could not retrieve performance metrics: {e}[/yellow]")

    async def save_trained_model(task_id: str, model_name: str, verbose: bool):
        """Save the trained model."""
        console.print(f"\n💾 Saving model as '{model_name}'...")
        
        try:
            payload = {
                "task_id": task_id,
                "model_name": model_name,
                "description": f"Model trained via CLI on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/models/save",
                    json=payload
                )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    console.print(f"✅ Model saved successfully!")
                    console.print(f"📋 Model ID: [cyan]{result.get('model_id')}[/cyan]")
                    console.print(f"📁 Model Path: [green]{result.get('model_path')}[/green]")
                    if result.get('model_size_mb'):
                        console.print(f"💽 Size: [yellow]{result.get('model_size_mb'):.1f} MB[/yellow]")
                else:
                    console.print(f"[red]Failed to save model: {result.get('message', 'Unknown error')}[/red]")
            else:
                console.print(f"[red]Failed to save model (HTTP {response.status_code})[/red]")
                if verbose:
                    console.print(f"Response: {response.text}")
                    
        except Exception as e:
            console.print(f"[red]Error saving model: {e}[/red]")

    # Run the async function
    try:
        asyncio.run(call_training_api())
    except KeyboardInterrupt:
        console.print("\n⏹️ Training interrupted by user")
        sys.exit(1)


def list_models(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information")
):
    """
    List all available trained neural network models.
    
    Example:
        ktrdr list-models
        ktrdr list-models --verbose
    """
    
    async def call_list_models_api():
        """Call the models list API endpoint."""
        try:
            console.print(f"\n📋 [bold blue]Available Neural Network Models[/bold blue]")
            console.print("=" * 50)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get("http://localhost:8000/api/v1/models")
                
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    models = result.get('models', [])
                    
                    if not models:
                        console.print("No trained models found.")
                        return
                    
                    console.print(f"Found {len(models)} trained models:\n")
                    
                    for model in models:
                        console.print(f"🧠 [bold cyan]{model.get('model_name', 'N/A')}[/bold cyan]")
                        console.print(f"  Symbol: [blue]{model.get('symbol', 'N/A')}[/blue]")
                        console.print(f"  Timeframe: [blue]{model.get('timeframe', 'N/A')}[/blue]")
                        console.print(f"  Created: [yellow]{model.get('created_at', 'N/A')}[/yellow]")
                        
                        if verbose:
                            console.print(f"  Model ID: [dim]{model.get('model_id', 'N/A')}[/dim]")
                            console.print(f"  Training Accuracy: [green]{model.get('training_accuracy', 'N/A'):.3f}[/green]")
                            console.print(f"  Test Accuracy: [green]{model.get('test_accuracy', 'N/A'):.3f}[/green]")
                            if model.get('description'):
                                console.print(f"  Description: [dim]{model.get('description')}[/dim]")
                        
                        console.print()
                else:
                    error_console.print(f"[bold red]Failed to list models:[/bold red] {result.get('message', 'Unknown error')}")
                    sys.exit(1)
            else:
                error_console.print(f"[bold red]API Error:[/bold red] {response.status_code}")
                try:
                    error_detail = response.json().get('detail', response.text)
                    error_console.print(f"Details: {error_detail}")
                except:
                    error_console.print(f"Response: {response.text}")
                sys.exit(1)
                
        except httpx.ConnectError:
            error_console.print("[bold red]Connection error:[/bold red] Could not connect to KTRDR API server")
            error_console.print("Make sure the API server is running at http://localhost:8000")
            sys.exit(1)
        except httpx.TimeoutException:
            error_console.print("[bold red]Timeout error:[/bold red] Request took longer than expected")
            sys.exit(1)
        except Exception as e:
            error_console.print(f"[bold red]Unexpected error:[/bold red] {str(e)}")
            if verbose:
                import traceback
                error_console.print(traceback.format_exc())
            sys.exit(1)
    
    # Run the async function
    try:
        asyncio.run(call_list_models_api())
    except KeyboardInterrupt:
        console.print("\n⏹️ Listing interrupted by user")
        sys.exit(1)


def test_model(
    model_name: str = typer.Argument(..., help="Name of the model to test"),
    symbol: str = typer.Argument(..., help="Trading symbol to test on (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Option("1h", "--timeframe", "-t", help="Timeframe for prediction"),
    test_date: Optional[str] = typer.Option(None, "--test-date", help="Specific date to test (YYYY-MM-DD)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed prediction information")
):
    """
    Test a trained neural network model's prediction capability.
    
    Examples:
        ktrdr test-model aapl_momentum_v1 AAPL
        ktrdr test-model msft_strategy MSFT --timeframe 4h --test-date 2024-06-01
    """
    
    async def call_test_model_api():
        """Call the model prediction API endpoint."""
        try:
            # First load the model
            console.print(f"\n🧠 [bold blue]Testing Model: {model_name}[/bold blue]")
            console.print("=" * 50)
            console.print(f"Loading model...")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                load_response = await client.post(f"http://localhost:8000/api/v1/models/{model_name}/load")
            
            if load_response.status_code != 200:
                error_console.print(f"[bold red]Failed to load model:[/bold red] HTTP {load_response.status_code}")
                try:
                    error_detail = load_response.json().get('detail', load_response.text)
                    error_console.print(f"Details: {error_detail}")
                except:
                    error_console.print(f"Response: {load_response.text}")
                sys.exit(1)
            
            load_result = load_response.json()
            if not load_result.get('success') or not load_result.get('model_loaded'):
                error_console.print(f"[bold red]Failed to load model:[/bold red] {load_result.get('model_info', {}).get('error', 'Unknown error')}")
                sys.exit(1)
            
            console.print(f"✅ Model loaded successfully!")
            
            # Show model info if verbose
            if verbose:
                model_info = load_result.get('model_info', {})
                console.print(f"\n📋 Model Information:")
                console.print(f"  Symbol: [blue]{model_info.get('symbol', 'N/A')}[/blue]")
                console.print(f"  Timeframe: [blue]{model_info.get('timeframe', 'N/A')}[/blue]")
                console.print(f"  Architecture: [cyan]{model_info.get('architecture', 'N/A')}[/cyan]")
                console.print(f"  Training Accuracy: [green]{model_info.get('training_accuracy', 'N/A'):.3f}[/green]")
                console.print(f"  Test Accuracy: [green]{model_info.get('test_accuracy', 'N/A'):.3f}[/green]")
            
            # Make prediction
            console.print(f"\n🔮 Making prediction...")
            
            symbol_validated = InputValidator.validate_string(
                symbol.upper(), min_length=1, max_length=20, pattern=r"^[A-Za-z0-9\-\.]+$"
            )
            
            payload = {
                "model_name": model_name,
                "symbol": symbol_validated,
                "timeframe": timeframe
            }
            
            if test_date:
                payload["test_date"] = test_date
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                pred_response = await client.post(
                    "http://localhost:8000/api/v1/models/predict",
                    json=payload
                )
            
            if pred_response.status_code == 200:
                result = pred_response.json()
                if result.get('success'):
                    prediction = result.get('prediction', {})
                    input_features = result.get('input_features', {})
                    
                    console.print(f"\n🎯 [bold green]Prediction Results[/bold green]")
                    console.print(f"  Symbol: [blue]{result.get('symbol')}[/blue]")
                    console.print(f"  Test Date: [yellow]{result.get('test_date')}[/yellow]")
                    console.print(f"  Signal: [bold cyan]{prediction.get('signal', 'N/A').upper()}[/bold cyan]")
                    console.print(f"  Confidence: [green]{prediction.get('confidence', 0):.1%}[/green]")
                    console.print(f"  Signal Strength: [yellow]{prediction.get('signal_strength', 0):.3f}[/yellow]")
                    
                    # Show fuzzy outputs
                    fuzzy_outputs = prediction.get('fuzzy_outputs', {})
                    if fuzzy_outputs:
                        console.print(f"\n🔀 Fuzzy Logic Outputs:")
                        console.print(f"  Bullish: [green]{fuzzy_outputs.get('bullish', 0):.3f}[/green]")
                        console.print(f"  Bearish: [red]{fuzzy_outputs.get('bearish', 0):.3f}[/red]")
                        console.print(f"  Neutral: [yellow]{fuzzy_outputs.get('neutral', 0):.3f}[/yellow]")
                    
                    # Show input features if verbose
                    if verbose and input_features:
                        console.print(f"\n📊 Input Features:")
                        for feature, value in input_features.items():
                            console.print(f"  {feature}: [cyan]{value:.4f}[/cyan]")
                            
                else:
                    error_console.print(f"[bold red]Prediction failed:[/bold red] {result.get('message', 'Unknown error')}")
                    sys.exit(1)
            else:
                error_console.print(f"[bold red]API Error:[/bold red] {pred_response.status_code}")
                try:
                    error_detail = pred_response.json().get('detail', pred_response.text)
                    error_console.print(f"Details: {error_detail}")
                except:
                    error_console.print(f"Response: {pred_response.text}")
                sys.exit(1)
                
        except ValidationError as e:
            error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
            sys.exit(1)
        except httpx.ConnectError:
            error_console.print("[bold red]Connection error:[/bold red] Could not connect to KTRDR API server")
            error_console.print("Make sure the API server is running at http://localhost:8000")
            sys.exit(1)
        except httpx.TimeoutException:
            error_console.print("[bold red]Timeout error:[/bold red] Request took longer than expected")
            sys.exit(1)
        except Exception as e:
            error_console.print(f"[bold red]Unexpected error:[/bold red] {str(e)}")
            if verbose:
                import traceback
                error_console.print(traceback.format_exc())
            sys.exit(1)
    
    # Run the async function
    try:
        asyncio.run(call_test_model_api())
    except KeyboardInterrupt:
        console.print("\n⏹️ Testing interrupted by user")
        sys.exit(1)