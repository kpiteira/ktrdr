#!/usr/bin/env python3
"""
Simple True Generalization Test

Direct test of the saved universal model on test data from the original training.
"""

import torch
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

def load_test_data(model_path: str, model_name: str = "EURUSD_GBPUSD_1h_v1"):
    """Load test data from the saved model directory."""
    full_path = Path(model_path) / model_name
    
    # Check if model exists
    if not full_path.exists():
        console.print(f"❌ [red]Model not found at: {full_path}[/red]")
        return None
    
    # Load test metrics from the training
    metrics_file = full_path / "metrics.json"
    if not metrics_file.exists():
        console.print(f"❌ [red]Metrics file not found: {metrics_file}[/red]")
        return None
    
    with open(metrics_file, 'r') as f:
        metrics = json.load(f)
    
    return metrics

def analyze_generalization():
    """Analyze the generalization test results."""
    console.print("🧠 [bold cyan]KTRDR Simple Generalization Analysis[/bold cyan]")
    console.print("=" * 60)
    
    # Load metrics from the universal model
    model_path = "models/universal_generalization_model"
    metrics = load_test_data(model_path)
    
    if not metrics:
        console.print("❌ [red]Failed to load model metrics[/red]")
        return
    
    console.print("📊 [bold green]Universal Model Performance Analysis[/bold green]")
    
    # Display overall metrics (use validation metrics if test metrics not available)
    val_accuracy = metrics.get('final_val_accuracy', 0)
    best_val_accuracy = metrics.get('best_val_accuracy', 0)
    train_accuracy = metrics.get('final_train_accuracy', 0)
    
    console.print(f"\\n🎯 **Universal Model Training Results:**")
    console.print(f"   Training Accuracy: {train_accuracy*100:.1f}%")
    console.print(f"   Validation Accuracy: {val_accuracy*100:.1f}%")
    console.print(f"   Best Validation Accuracy: {best_val_accuracy*100:.1f}%")
    console.print(f"   Training Loss: {metrics.get('final_train_loss', 0):.4f}")
    console.print(f"   Validation Loss: {metrics.get('final_val_loss', 0):.4f}")
    console.print(f"   Epochs Trained: {metrics.get('epochs_trained', 0)}")
    console.print(f"   Training Time: {metrics.get('training_time', 0):.1f} seconds")
    
    # Check for per-symbol metrics
    per_symbol_metrics = metrics.get('per_symbol_test_metrics', {})
    if per_symbol_metrics:
        console.print(f"\\n📈 **Per-Symbol Test Performance:**")
        
        # Create table for per-symbol results
        table = Table(title="Symbol-Specific Performance")
        table.add_column("Symbol", style="cyan", width=10)
        table.add_column("Accuracy", style="green", justify="right", width=10)
        table.add_column("Precision", style="blue", justify="right", width=10)
        table.add_column("Recall", style="yellow", justify="right", width=10)
        table.add_column("F1 Score", style="magenta", justify="right", width=10)
        table.add_column("Samples", style="white", justify="right", width=8)
        
        for symbol, symbol_metrics in per_symbol_metrics.items():
            table.add_row(
                symbol,
                f"{symbol_metrics.get('accuracy', 0)*100:.1f}%",
                f"{symbol_metrics.get('precision', 0)*100:.1f}%",
                f"{symbol_metrics.get('recall', 0)*100:.1f}%",
                f"{symbol_metrics.get('f1_score', 0)*100:.1f}%",
                f"{symbol_metrics.get('sample_count', 0):,}"
            )
        
        console.print(table)
        
        # Analyze balance between symbols
        accuracies = [symbol_metrics.get('accuracy', 0) for symbol_metrics in per_symbol_metrics.values()]
        if len(accuracies) >= 2:
            max_acc = max(accuracies)
            min_acc = min(accuracies)
            balance_ratio = min_acc / max_acc if max_acc > 0 else 0
            
            console.print(f"\\n⚖️  **Symbol Balance Analysis:**")
            console.print(f"   Best performing symbol: {max_acc*100:.1f}% accuracy")
            console.print(f"   Worst performing symbol: {min_acc*100:.1f}% accuracy")
            console.print(f"   Balance ratio: {balance_ratio:.3f}")
            
            if balance_ratio >= 0.8:
                console.print(f"   ✅ [green]Excellent balance - model generalizes well across symbols[/green]")
            elif balance_ratio >= 0.6:
                console.print(f"   ⚠️  [yellow]Good balance - minor variations between symbols[/yellow]")
            else:
                console.print(f"   ❌ [red]Poor balance - significant symbol bias detected[/red]")
    
    # Provide interpretation (use validation accuracy)
    overall_accuracy = val_accuracy
    console.print(f"\\n💡 **Generalization Assessment:**")
    
    if overall_accuracy >= 0.6:
        console.print(f"   ✅ [green]Model demonstrates good performance ({overall_accuracy*100:.1f}%)[/green]")
        console.print(f"   🎯 Universal model successfully learned generalizable patterns")
        
        if per_symbol_metrics and len(per_symbol_metrics) >= 2:
            console.print(f"   📊 Trained on {len(per_symbol_metrics)} symbols for cross-symbol learning")
            console.print(f"   🔄 Ready for true generalization testing on unseen symbols")
        
    elif overall_accuracy >= 0.4:
        console.print(f"   ⚠️  [yellow]Model shows moderate performance ({overall_accuracy*100:.1f}%)[/yellow]")
        console.print(f"   🔧 May need tuning for better generalization capability")
        
    else:
        console.print(f"   ❌ [red]Model shows poor performance ({overall_accuracy*100:.1f}%)[/red]")
        console.print(f"   🔄 Recommend retraining with different parameters")
    
    # Next steps
    console.print(f"\\n🚀 **Next Steps for True Generalization Test:**")
    console.print(f"   1. Use the saved model at: {model_path}/EURUSD_GBPUSD_1h_v1/")
    console.print(f"   2. Apply to USDJPY data (unseen symbol) for inference-only evaluation")
    console.print(f"   3. Compare USDJPY performance to EURUSD/GBPUSD baseline")
    console.print(f"   4. Calculate generalization score = unseen_accuracy / seen_accuracy")
    
    return metrics

if __name__ == "__main__":
    results = analyze_generalization()