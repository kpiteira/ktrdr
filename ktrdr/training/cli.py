"""Command-line interface for strategy training."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .train_strategy import StrategyTrainer


def main():
    """Main entry point for training CLI."""
    parser = argparse.ArgumentParser(
        description="Train neuro-fuzzy trading strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train AAPL strategy for 1 hour timeframe
  python -m ktrdr.training.cli --strategy strategies/neuro_mean_reversion.yaml \\
                               --symbol AAPL --timeframe 1h \\
                               --start-date 2023-01-01 --end-date 2023-12-31

  # Train with custom model output directory
  python -m ktrdr.training.cli --strategy strategies/momentum.yaml \\
                               --symbol MSFT --timeframe 4h \\
                               --start-date 2022-01-01 --end-date 2024-01-01 \\
                               --models-dir custom_models
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
        help="Trading symbol to train on (e.g., AAPL, MSFT)"
    )
    
    parser.add_argument(
        "--timeframe",
        required=True,
        help="Timeframe for training data (e.g., 1h, 4h, 1d)"
    )
    
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date for training data (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--end-date", 
        required=True,
        help="End date for training data (YYYY-MM-DD)"
    )
    
    # Optional arguments
    parser.add_argument(
        "--models-dir",
        default="models",
        help="Directory to store trained models (default: models)"
    )
    
    parser.add_argument(
        "--validation-split",
        type=float,
        default=0.2,
        help="Fraction of data to use for validation (default: 0.2)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without training"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not Path(args.strategy).exists():
        print(f"Error: Strategy file not found: {args.strategy}")
        sys.exit(1)
    
    if args.validation_split <= 0 or args.validation_split >= 1:
        print(f"Error: Validation split must be between 0 and 1, got {args.validation_split}")
        sys.exit(1)
    
    try:
        train_strategy(
            strategy_config_path=args.strategy,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date,
            models_dir=args.models_dir,
            validation_split=args.validation_split,
            verbose=args.verbose,
            dry_run=args.dry_run
        )
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}")
        sys.exit(1)


def train_strategy(strategy_config_path: str,
                  symbol: str,
                  timeframe: str,
                  start_date: str,
                  end_date: str,
                  models_dir: str = "models",
                  validation_split: float = 0.2,
                  verbose: bool = False,
                  dry_run: bool = False) -> Optional[dict]:
    """Train a strategy with the given parameters.
    
    Args:
        strategy_config_path: Path to strategy YAML configuration
        symbol: Trading symbol
        timeframe: Data timeframe
        start_date: Start date for training
        end_date: End date for training
        models_dir: Directory to store models
        validation_split: Validation data split
        verbose: Enable verbose output
        dry_run: Validate only, don't train
        
    Returns:
        Training results dictionary if successful
    """
    print("🚀 KTRDR Neuro-Fuzzy Strategy Training")
    print("=" * 50)
    
    if verbose:
        print(f"Configuration:")
        print(f"  Strategy: {strategy_config_path}")
        print(f"  Symbol: {symbol}")
        print(f"  Timeframe: {timeframe}")
        print(f"  Date range: {start_date} to {end_date}")
        print(f"  Models directory: {models_dir}")
        print(f"  Validation split: {validation_split}")
        print()
    
    if dry_run:
        print("🔍 Dry run mode - validating configuration...")
        # Load and validate configuration
        trainer = StrategyTrainer(models_dir)
        config = trainer._load_strategy_config(strategy_config_path)
        
        print("✅ Configuration validation passed!")
        print(f"Strategy name: {config['name']}")
        print(f"Indicators: {len(config['indicators'])}")
        print(f"Fuzzy sets: {len(config['fuzzy_sets'])}")
        print(f"Model type: {config['model']['type']}")
        return None
    
    # Create trainer and run training
    trainer = StrategyTrainer(models_dir)
    
    try:
        results = trainer.train_strategy(
            strategy_config_path=strategy_config_path,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split
        )
        
        # Print results summary
        print("\n" + "=" * 50)
        print("🎉 TRAINING COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        
        print(f"📁 Model saved to: {results['model_path']}")
        
        # Training metrics
        metrics = results['training_metrics']
        print(f"\n📊 Training Results:")
        print(f"  Final Training Accuracy: {metrics.get('final_train_accuracy', 0):.3f}")
        print(f"  Best Validation Accuracy: {metrics.get('best_val_accuracy', 0):.3f}")
        print(f"  Test Accuracy: {metrics.get('test_accuracy', 'N/A')}")
        print(f"  Epochs Trained: {metrics.get('epochs_trained', 0)}")
        
        # Label distribution
        label_dist = results['label_distribution']
        print(f"\n🏷️  Label Distribution:")
        print(f"  BUY signals: {label_dist['buy_pct']:.1f}% ({label_dist['buy_count']} samples)")
        print(f"  HOLD signals: {label_dist['hold_pct']:.1f}% ({label_dist['hold_count']} samples)")
        print(f"  SELL signals: {label_dist['sell_pct']:.1f}% ({label_dist['sell_count']} samples)")
        
        # Top features
        feature_importance = results['feature_importance']
        if feature_importance:
            print(f"\n🎯 Top 5 Most Important Features:")
            sorted_features = sorted(feature_importance.items(), 
                                   key=lambda x: abs(x[1]), reverse=True)
            for feature, importance in sorted_features[:5]:
                print(f"  {feature}: {importance:.4f}")
        
        # Data summary
        data_summary = results['data_summary']
        print(f"\n📈 Data Summary:")
        print(f"  Total samples: {data_summary['total_samples']:,}")
        print(f"  Features: {data_summary['feature_count']}")
        print(f"  Symbol: {data_summary['symbol']}")
        print(f"  Timeframe: {data_summary['timeframe']}")
        
        print(f"\n💡 Next Steps:")
        print(f"  1. Run backtesting to evaluate strategy performance")
        print(f"  2. Consider training on additional symbols")
        print(f"  3. Experiment with different model architectures")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise


if __name__ == "__main__":
    main()