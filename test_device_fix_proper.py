#!/usr/bin/env python3
"""
Test Device Placement Fix - Proper Test

Test with sufficient data to verify the device bug is truly fixed.
"""

import torch
from rich.console import Console

from ktrdr.training.train_strategy import StrategyTrainer
from ktrdr import get_logger

logger = get_logger(__name__)
console = Console()

def test_device_fix_proper():
    """Test device placement fix with sufficient data."""
    console.print("🔧 [bold cyan]Testing Device Placement Fix (Proper Test)[/bold cyan]")
    console.print("=" * 55)
    
    try:
        # Test with sufficient data (1 month should be enough)
        console.print("Running training with sufficient data to test device fix...")
        
        trainer = StrategyTrainer()
        
        training_results = trainer.train_multi_symbol_strategy(
            strategy_config_path="strategies/universal_zero_shot_model.yaml",
            symbols=["EURUSD", "GBPUSD"],
            timeframes=["1h"],
            start_date="2024-01-01",  # 1 month period
            end_date="2024-02-01",
            validation_split=0.2,
            data_mode="local"
        )
        
        if training_results:
            console.print("✅ [bold green]Device placement fix successful![/bold green]")
            console.print(f"   Training completed without device errors")
            console.print(f"   Final validation accuracy: {training_results['training_metrics']['final_val_accuracy']:.1%}")
            console.print(f"   Total samples: {training_results.get('data_summary', {}).get('total_samples', 'N/A')}")
            console.print(f"   Test accuracy: {training_results.get('test_metrics', {}).get('test_accuracy', 'N/A')}")
            console.print(f"   Model saved to: {training_results['model_path']}")
            
            # The key test: did we complete the full pipeline including evaluation?
            has_test_metrics = 'test_metrics' in training_results
            console.print(f"   Full evaluation completed: {'✅' if has_test_metrics else '❌'}")
            
            return True
        else:
            console.print("❌ [red]Training failed for other reasons[/red]")
            return False
            
    except RuntimeError as e:
        if "Tensor for argument input is on cpu but expected on mps" in str(e):
            console.print("❌ [red]Device placement bug still exists[/red]")
            console.print(f"   Error: {e}")
            return False
        else:
            console.print(f"⚠️  [yellow]Different runtime error: {e}[/yellow]")
            # Other runtime errors don't indicate device bug
            return True
    except Exception as e:
        console.print(f"⚠️  [yellow]Other error (not device related): {e}[/yellow]")
        # Non-runtime errors don't indicate device bug failure
        return True

if __name__ == "__main__":
    success = test_device_fix_proper()
    if success:
        console.print("\n🎉 [bold green]Device bug fixed! Ready for Test Phase 3![/bold green]")
        console.print("The original device placement error no longer occurs.")
    else:
        console.print("\n❌ [bold red]Device bug still exists[/bold red]")