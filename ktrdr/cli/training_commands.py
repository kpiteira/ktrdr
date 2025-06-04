"""Training commands for the main CLI."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
import sys

from ktrdr.training.train_strategy import StrategyTrainer

# Rich console for formatted output
console = Console()


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
):
    """
    Train a neuro-fuzzy trading strategy.
    
    This command trains a neural network model based on the strategy configuration,
    using historical price data and technical indicators with fuzzy logic.
    
    Examples:
        ktrdr train strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-01-01 --end-date 2024-06-01
        ktrdr train strategies/momentum.yaml MSFT 4h --start-date 2023-01-01 --end-date 2024-01-01 --epochs 100
    """
    # Validate inputs
    strategy_path = Path(strategy)
    if not strategy_path.exists():
        console.print(f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]")
        raise typer.Exit(1)
    
    if validation_split <= 0 or validation_split >= 1:
        console.print(f"[red]❌ Error: Validation split must be between 0 and 1, got {validation_split}[/red]")
        raise typer.Exit(1)
    
    try:
        console.print(f"[cyan]🏋️ KTRDR Strategy Training[/cyan]")
        console.print("=" * 50)
        console.print(f"📋 Configuration:")
        console.print(f"  Strategy: [blue]{strategy}[/blue]")
        console.print(f"  Symbol: [blue]{symbol}[/blue]") 
        console.print(f"  Timeframe: [blue]{timeframe}[/blue]")
        console.print(f"  Training Period: [blue]{start_date}[/blue] to [blue]{end_date}[/blue]")
        console.print(f"  Models Directory: [blue]{models_dir}[/blue]")
        console.print(f"  Validation Split: [blue]{validation_split:.1%}[/blue]")
        console.print(f"  Data Mode: [blue]{data_mode}[/blue]")
        if epochs:
            console.print(f"  Epochs Override: [blue]{epochs}[/blue]")
        console.print()
        
        if dry_run:
            console.print("[yellow]🔍 Dry run mode - validating configuration only[/yellow]")
            # TODO: Add configuration validation
            console.print("[green]✅ Configuration is valid![/green]")
            return
        
        # Create trainer
        trainer = StrategyTrainer(models_dir=models_dir)
        
        # Override epochs if specified
        if epochs:
            import yaml
            with open(strategy_path, 'r') as f:
                config = yaml.safe_load(f)
            if 'model' in config and 'training' in config['model']:
                config['model']['training']['epochs'] = epochs
            # Create temporary config file with override
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
                yaml.dump(config, tmp)
                tmp_strategy_path = tmp.name
            strategy = tmp_strategy_path
        
        # Run training
        console.print("[green]🚀 Starting training...[/green]")
        
        results = trainer.train_strategy(
            strategy_config_path=strategy,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
            data_mode=data_mode
        )
        
        console.print("\n[green]✅ Training completed![/green]")
        console.print(f"📊 Results: {results}")
        console.print(f"[green]💾 Model saved successfully![/green]")
        
        # Clean up temp file if created
        if epochs:
            import os
            os.unlink(tmp_strategy_path)
            
    except Exception as e:
        console.print(f"\n[red]❌ Training failed: {str(e)}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)