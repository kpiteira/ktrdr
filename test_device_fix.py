#!/usr/bin/env python3
"""
Test Device Placement Fix

Quick test to verify the device placement bug is fixed.
"""

import torch
from rich.console import Console

from ktrdr.training.train_strategy import StrategyTrainer
from ktrdr import get_logger

logger = get_logger(__name__)
console = Console()

def test_device_fix():
    """Test that the device placement fix works."""
    console.print("🔧 [bold cyan]Testing Device Placement Fix[/bold cyan]")
    console.print("=" * 50)
    
    try:
        # Quick training run to test the fix
        console.print("Running minimal training to test device fix...")
        
        trainer = StrategyTrainer()
        
        training_results = trainer.train_multi_symbol_strategy(
            strategy_config_path="strategies/universal_zero_shot_model.yaml",
            symbols=["EURUSD", "GBPUSD"],
            timeframes=["1h"],
            start_date="2024-06-01",  # Very short period
            end_date="2024-06-03",   # Just 2 days
            validation_split=0.2,
            data_mode="local"
        )
        
        if training_results:
            console.print("✅ [bold green]Device placement fix successful![/bold green]")
            console.print(f"   Training completed without device errors")
            console.print(f"   Final validation accuracy: {training_results['training_metrics']['final_val_accuracy']:.1%}")
            console.print(f"   Model saved to: {training_results['model_path']}")
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
            console.print(f"❌ [red]Different error occurred: {e}[/red]")
            return False
    except Exception as e:
        console.print(f"❌ [red]Unexpected error: {e}[/red]")
        return False

if __name__ == "__main__":
    success = test_device_fix()
    if success:
        console.print("\n🎉 [bold green]Device bug fixed! Ready for Test Phase 3![/bold green]")
    else:
        console.print("\n❌ [bold red]Device bug still needs work[/bold red]")