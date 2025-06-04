"""Command-line interface for backtesting system."""

import argparse
import sys
import json
from pathlib import Path
from typing import Optional

from .engine import BacktestingEngine, BacktestConfig


def main():
    """Main entry point for backtesting CLI."""
    parser = argparse.ArgumentParser(
        description="Run backtests on trained neuro-fuzzy trading strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic backtest
  python -m ktrdr.backtesting.cli --strategy strategies/neuro_mean_reversion.yaml \\
                                  --model models/neuro_mean_reversion/AAPL_1h_v1 \\
                                  --symbol AAPL --timeframe 1h \\
                                  --start-date 2024-01-01 --end-date 2024-06-01

  # Backtest with custom parameters
  python -m ktrdr.backtesting.cli --strategy strategies/momentum.yaml \\
                                  --symbol MSFT --timeframe 4h \\
                                  --start-date 2023-01-01 --end-date 2024-01-01 \\
                                  --capital 50000 --commission 0.002 \\
                                  --verbose --output results.json
        """
    )
    
    # Required arguments
    parser.add_argument(
        "--strategy",
        required=True,
        help="Path to strategy YAML configuration file"
    )
    
    parser.add_argument(
        "--symbol", 
        required=True,
        help="Trading symbol to backtest (e.g., AAPL, MSFT)"
    )
    
    parser.add_argument(
        "--timeframe",
        required=True,
        help="Timeframe for backtest data (e.g., 1h, 4h, 1d)"
    )
    
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date for backtest (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--end-date", 
        required=True,
        help="End date for backtest (YYYY-MM-DD)"
    )
    
    # Optional arguments
    parser.add_argument(
        "--model",
        help="Path to specific trained model (if not specified, uses latest for strategy/symbol/timeframe)"
    )
    
    parser.add_argument(
        "--capital",
        type=float,
        default=100000,
        help="Initial capital for backtest (default: 100000)"
    )
    
    parser.add_argument(
        "--commission",
        type=float,
        default=0.001,
        help="Commission rate as decimal (default: 0.001 = 0.1%%)"
    )
    
    parser.add_argument(
        "--slippage",
        type=float,
        default=0.0005,
        help="Slippage rate as decimal (default: 0.0005 = 0.05%%)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output with progress and trade details"
    )
    
    parser.add_argument(
        "--output",
        help="Output file for results (JSON format)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output except errors"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not Path(args.strategy).exists():
        print(f"Error: Strategy file not found: {args.strategy}")
        sys.exit(1)
    
    if args.model and not Path(args.model).exists():
        print(f"Error: Model path not found: {args.model}")
        sys.exit(1)
    
    if args.capital <= 0:
        print(f"Error: Capital must be positive, got {args.capital}")
        sys.exit(1)
    
    try:
        results = run_backtest(
            strategy_config_path=args.strategy,
            model_path=args.model,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.capital,
            commission=args.commission,
            slippage=args.slippage,
            verbose=args.verbose and not args.quiet,
            output_file=args.output,
            quiet=args.quiet
        )
        
        if not args.quiet:
            print(f"\n✅ Backtest completed successfully!")
            if args.output:
                print(f"📄 Results saved to: {args.output}")
        
        # Return results for programmatic use
        return results
        
    except Exception as e:
        if args.verbose and not args.quiet:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}")
        sys.exit(1)


def run_backtest(strategy_config_path: str,
                symbol: str,
                timeframe: str,
                start_date: str,
                end_date: str,
                model_path: Optional[str] = None,
                initial_capital: float = 100000,
                commission: float = 0.001,
                slippage: float = 0.0005,
                verbose: bool = False,
                output_file: Optional[str] = None,
                quiet: bool = False) -> dict:
    """Run a backtest with the given parameters.
    
    Args:
        strategy_config_path: Path to strategy YAML configuration
        symbol: Trading symbol
        timeframe: Data timeframe  
        start_date: Start date for backtest
        end_date: End date for backtest
        model_path: Optional path to specific model
        initial_capital: Initial capital amount
        commission: Commission rate
        slippage: Slippage rate
        verbose: Enable verbose output
        output_file: Optional output file path
        quiet: Suppress output
        
    Returns:
        Backtest results dictionary
    """
    if not quiet:
        print("🔬 KTRDR Backtesting Engine")
        print("=" * 50)
    
    # Create backtest configuration
    config = BacktestConfig(
        strategy_config_path=strategy_config_path,
        model_path=model_path,
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage,
        verbose=verbose
    )
    
    if verbose and not quiet:
        print(f"📋 Configuration:")
        print(f"  Strategy: {strategy_config_path}")
        print(f"  Model: {model_path if model_path else 'Latest available'}")
        print(f"  Symbol: {symbol}")
        print(f"  Timeframe: {timeframe}")
        print(f"  Period: {start_date} to {end_date}")
        print(f"  Capital: ${initial_capital:,.2f}")
        print(f"  Commission: {commission:.3f}%")
        print(f"  Slippage: {slippage:.3f}%")
        print()
    
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
    if output_file:
        # Add equity curve data for detailed analysis
        results_dict["equity_curve"] = results.equity_curve.reset_index().to_dict('records')
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)
    
    return results_dict


if __name__ == "__main__":
    main()