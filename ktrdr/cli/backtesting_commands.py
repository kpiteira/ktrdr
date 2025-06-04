"""Backtesting commands for the main CLI."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
import json

from ktrdr.backtesting.engine import BacktestingEngine, BacktestConfig

# Rich console for formatted output
console = Console()


def run_backtest(
    strategy: str = typer.Argument(..., help="Path to strategy YAML configuration file"),
    symbol: str = typer.Argument(..., help="Trading symbol to backtest (e.g., AAPL, MSFT)"),
    timeframe: str = typer.Argument(..., help="Timeframe for backtest data (e.g., 1h, 4h, 1d)"),
    start_date: str = typer.Option(..., "--start-date", help="Start date for backtest (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end-date", help="End date for backtest (YYYY-MM-DD)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Path to specific trained model"),
    capital: float = typer.Option(100000, "--capital", "-c", help="Initial capital for backtest"),
    commission: float = typer.Option(0.001, "--commission", help="Commission rate as decimal (0.001 = 0.1%)"),
    slippage: float = typer.Option(0.0005, "--slippage", help="Slippage rate as decimal (0.0005 = 0.05%)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output with progress"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for results (JSON format)"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress all output except errors"),
):
    """
    Run a backtest on a trained trading strategy.
    
    This command simulates trading using a trained neuro-fuzzy model to evaluate
    strategy performance on historical data.
    
    Examples:
        ktrdr backtest strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-07-01 --end-date 2024-12-31
        ktrdr backtest strategies/momentum.yaml MSFT 4h --start-date 2023-01-01 --end-date 2024-01-01 --capital 50000
    """
    # Validate arguments
    strategy_path = Path(strategy)
    if not strategy_path.exists():
        console.print(f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]")
        raise typer.Exit(1)
    
    if model and not Path(model).exists():
        console.print(f"[red]❌ Error: Model path not found: {model}[/red]")
        raise typer.Exit(1)
    
    if capital <= 0:
        console.print(f"[red]❌ Error: Capital must be positive, got {capital}[/red]")
        raise typer.Exit(1)
    
    try:
        if not quiet:
            console.print("[cyan]🔬 KTRDR Backtesting Engine[/cyan]")
            console.print("=" * 50)
        
        # Create backtest configuration
        config = BacktestConfig(
            strategy_config_path=str(strategy_path),
            model_path=model,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=capital,
            commission=commission,
            slippage=slippage,
            verbose=verbose and not quiet
        )
        
        if verbose and not quiet:
            console.print(f"📋 Configuration:")
            console.print(f"  Strategy: [blue]{strategy}[/blue]")
            console.print(f"  Model: [blue]{model if model else 'Latest available'}[/blue]")
            console.print(f"  Symbol: [blue]{symbol}[/blue]")
            console.print(f"  Timeframe: [blue]{timeframe}[/blue]")
            console.print(f"  Period: [blue]{start_date}[/blue] to [blue]{end_date}[/blue]")
            console.print(f"  Capital: [green]${capital:,.2f}[/green]")
            console.print(f"  Commission: [yellow]{commission*100:.3f}%[/yellow]")
            console.print(f"  Slippage: [yellow]{slippage*100:.3f}%[/yellow]")
            console.print()
        
        # Create and run backtest
        engine = BacktestingEngine(config)
        results = engine.run()
        
        # Convert results to dictionary for serialization
        results_dict = results.to_dict()
        
        # Add trade details if requested
        if verbose:
            results_dict["trades"] = [
                {
                    "trade_id": trade.trade_id,
                    "side": trade.side,
                    "entry_time": trade.entry_time.isoformat(),
                    "entry_price": trade.entry_price,
                    "exit_time": trade.exit_time.isoformat(),
                    "exit_price": trade.exit_price,
                    "quantity": trade.quantity,
                    "net_pnl": trade.net_pnl,
                    "return_pct": trade.return_pct,
                    "holding_period_hours": trade.holding_period_hours
                }
                for trade in results.trades
            ]
        
        # Save results if output file specified
        if output:
            # Add equity curve data for detailed analysis
            results_dict["equity_curve"] = results.equity_curve.reset_index().to_dict('records')
            
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(results_dict, f, indent=2, default=str)
        
        if not quiet:
            # Display summary
            console.print("\n[green]✅ Backtest completed successfully![/green]")
            if output:
                console.print(f"[cyan]📄 Results saved to: {output}[/cyan]")
            
            # Print performance summary
            console.print(f"\n[cyan]📊 Performance Summary:[/cyan]")
            console.print("=" * 50)
            
            metrics = results.metrics
            console.print(f"💰 Total Return: [green]${metrics.total_return:,.2f} ({metrics.total_return_pct:.2f}%)[/green]")
            console.print(f"📈 Sharpe Ratio: [yellow]{metrics.sharpe_ratio:.3f}[/yellow]")
            console.print(f"📉 Max Drawdown: [red]${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct:.2f}%)[/red]")
            console.print(f"🎯 Win Rate: [blue]{metrics.win_rate:.1f}%[/blue] ({metrics.winning_trades}/{metrics.total_trades})")
            console.print(f"🏷️ Total Trades: [blue]{metrics.total_trades}[/blue]")
            
        return results_dict
        
    except Exception as e:
        console.print(f"[red]❌ Backtest failed: {str(e)}[/red]")
        if verbose and not quiet:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)