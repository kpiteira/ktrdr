#!/usr/bin/env python3
"""
Execute True Generalization Test on USDJPY

This script loads the trained universal model and applies it to USDJPY data
for inference-only evaluation to test true cross-symbol generalization.
"""

import torch
import pandas as pd
import numpy as np
from pathlib import Path
from rich.console import Console
from rich.table import Table
import json

from ktrdr import get_logger
from ktrdr.data.data_manager import DataManager
from ktrdr.config.strategy_loader import strategy_loader
from ktrdr.training.zigzag_labeler import ZigZagLabeler
from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor
from ktrdr.indicators.indicator_engine import IndicatorEngine
from ktrdr.fuzzy.engine import FuzzyEngine
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

logger = get_logger(__name__)
console = Console()

def load_universal_model():
    """Load the pre-trained universal model."""
    model_path = Path("models/universal_generalization_model/EURUSD_GBPUSD_1h_v1")
    
    if not model_path.exists():
        raise FileNotFoundError(f"Universal model not found at: {model_path}")
    
    # Load model with safe globals
    import torch.serialization
    from ktrdr.neural.models.mlp import MultiSymbolMLPTradingModel, MultiSymbolMLP
    torch.serialization.add_safe_globals([MultiSymbolMLPTradingModel, MultiSymbolMLP])
    
    model = torch.load(model_path / "model_full.pt", map_location='cpu', weights_only=False)
    console.print(f"✅ Loaded universal model with {sum(p.numel() for p in model.parameters())} parameters")
    
    # Load training metrics for baseline comparison
    with open(model_path / "metrics.json", 'r') as f:
        training_metrics = json.load(f)
    
    return model, training_metrics

def prepare_symbol_data(symbol: str, start_date: str = "2024-01-01", end_date: str = "2024-06-01"):
    """Prepare and process data for a specific symbol."""
    console.print(f"📊 Preparing {symbol} data...")
    
    # Load data
    data_manager = DataManager()
    data = data_manager.load_data(symbol, "1h", mode="local")
    
    if data is None:
        raise ValueError(f"No data found for {symbol}")
    
    # Filter date range
    data = data.loc[start_date:end_date]
    console.print(f"   Loaded {len(data)} bars for {symbol}")
    
    if len(data) < 200:
        raise ValueError(f"Insufficient data for {symbol}: {len(data)} bars")
    
    return data

def process_symbol_features(data: pd.DataFrame, symbol: str):
    """Process symbol data into features using a simplified approach."""
    console.print(f"🔧 Processing features for {symbol}...")
    
    # Load strategy configuration
    strategy_config, is_v2 = strategy_loader.load_strategy_config("strategies/universal_generalization_model.yaml")
    console.print(f"   Loaded strategy config (v2: {is_v2})")
    
    # Calculate indicators directly using individual indicator classes
    indicators = {}
    
    # RSI
    from ktrdr.indicators.rsi_indicator import RSIIndicator
    rsi_indicator = RSIIndicator(period=14)
    indicators['rsi'] = rsi_indicator.compute(data)
    
    # MACD
    from ktrdr.indicators.macd_indicator import MACDIndicator
    macd_indicator = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
    macd_result = macd_indicator.compute(data)
    if isinstance(macd_result, pd.DataFrame):
        # Use the first column as the main MACD line
        indicators['macd'] = macd_result.iloc[:, 0]
    else:
        indicators['macd'] = macd_result
    
    # SMA
    from ktrdr.indicators.ma_indicators import SimpleMovingAverage
    sma_indicator = SimpleMovingAverage(period=20)
    indicators['sma'] = sma_indicator.compute(data)
    
    # Bollinger Bands
    from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator
    bb_indicator = BollingerBandsIndicator(period=20, multiplier=2.0)
    bb_result = bb_indicator.compute(data)
    if isinstance(bb_result, pd.DataFrame):
        # Use the first column or find a suitable column
        indicators['BollingerBands'] = bb_result.iloc[:, 0]
    else:
        indicators['BollingerBands'] = bb_result
    
    console.print(f"   Calculated {len(indicators)} indicators")
    
    # Create labels
    labeler = ZigZagLabeler()
    # Handle both dict and object formats
    if isinstance(strategy_config, dict):
        training_config = strategy_config['training']
        labels_config = training_config['labels']
        threshold = labels_config['zigzag_threshold']
        lookahead = labels_config['label_lookahead']
    else:
        threshold = strategy_config.training.labels.zigzag_threshold
        lookahead = strategy_config.training.labels.label_lookahead
    
    labels = labeler.generate_labels(data, threshold=threshold, lookahead=lookahead)
    console.print(f"   Created {len(labels)} labels")
    
    # Process fuzzy features
    if isinstance(strategy_config, dict):
        fuzzy_sets = strategy_config['fuzzy_sets']
        feature_config = strategy_config['model']['features']
    else:
        fuzzy_sets = strategy_config.fuzzy_sets
        feature_config = strategy_config.model.features
        
    fuzzy_engine = FuzzyEngine(fuzzy_sets)
    processor = FuzzyNeuralProcessor(
        feature_config=feature_config,
        fuzzy_engine=fuzzy_engine
    )
    
    # Convert indicator results for processing
    processed_indicators = {}
    for name, result in indicators.items():
        if hasattr(result, 'values'):
            processed_indicators[name] = result.values
        else:
            processed_indicators[name] = result
    
    # Create features
    features, fuzzy_features = processor.create_features(
        price_data=data,
        indicator_data=processed_indicators,
        labels=labels
    )
    
    console.print(f"   Generated {features.shape} price features")
    if fuzzy_features is not None:
        console.print(f"   Generated {fuzzy_features.shape} fuzzy features")
    
    # Combine features
    if fuzzy_features is not None and len(fuzzy_features) > 0:
        combined_features = torch.cat([features, fuzzy_features], dim=1)
    else:
        combined_features = features
    
    return combined_features, labels

def evaluate_model_on_symbol(model, symbol: str, symbol_index: int, is_seen: bool):
    """Evaluate the universal model on a specific symbol."""
    console.print(f"🧠 Evaluating model on {symbol} ({'seen' if is_seen else 'unseen'} symbol)...")
    
    # Prepare data
    data = prepare_symbol_data(symbol)
    features, labels = process_symbol_features(data, symbol)
    
    # Create symbol indices
    symbol_indices = torch.full((len(features),), symbol_index, dtype=torch.long)
    
    # Make predictions
    model.eval()
    with torch.no_grad():
        predictions = model(features, symbol_indices)
        predicted_classes = torch.argmax(predictions, dim=1)
        confidence_scores = torch.max(torch.softmax(predictions, dim=1), dim=1)[0]
    
    # Calculate metrics
    actual_labels = labels.numpy()
    predicted_labels = predicted_classes.numpy()
    
    accuracy = accuracy_score(actual_labels, predicted_labels)
    precision = precision_score(actual_labels, predicted_labels, average='weighted', zero_division=0)
    recall = recall_score(actual_labels, predicted_labels, average='weighted', zero_division=0)
    f1 = f1_score(actual_labels, predicted_labels, average='weighted', zero_division=0)
    mean_confidence = float(confidence_scores.mean())
    
    console.print(f"   ✅ {symbol}: {accuracy:.1%} accuracy, {mean_confidence:.3f} confidence")
    
    return {
        "symbol": symbol,
        "is_seen": is_seen,
        "symbol_index": symbol_index,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "mean_confidence": mean_confidence,
        "sample_count": len(actual_labels)
    }

def run_true_generalization_test():
    """Execute the complete true generalization test."""
    console.print("🧠 [bold cyan]KTRDR True Generalization Test - USDJPY Evaluation[/bold cyan]")
    console.print("=" * 70)
    
    try:
        # Step 1: Load universal model
        console.print("📂 Step 1: Loading universal model...")
        model, training_metrics = load_universal_model()
        
        baseline_val_accuracy = training_metrics.get('final_val_accuracy', 0)
        console.print(f"   Baseline validation accuracy: {baseline_val_accuracy:.1%}")
        
        # Step 2: Test on seen symbols for baseline
        console.print("\n📊 Step 2: Testing on seen symbols (baseline)...")
        seen_results = {}
        
        # EURUSD (symbol index 0)
        eurusd_result = evaluate_model_on_symbol(model, "EURUSD", 0, True)
        seen_results["EURUSD"] = eurusd_result
        
        # GBPUSD (symbol index 1) 
        gbpusd_result = evaluate_model_on_symbol(model, "GBPUSD", 1, True)
        seen_results["GBPUSD"] = gbpusd_result
        
        # Step 3: Test on unseen symbol - THE KEY TEST
        console.print("\n🔍 Step 3: Testing on USDJPY (UNSEEN SYMBOL) - True Generalization Test...")
        usdjpy_result = evaluate_model_on_symbol(model, "USDJPY", 2, False)  # Symbol index 2 (new)
        
        # Step 4: Analyze results
        console.print("\n📈 Step 4: Analyzing generalization performance...")
        
        # Calculate averages for seen symbols
        seen_accuracies = [result["accuracy"] for result in seen_results.values()]
        seen_confidences = [result["mean_confidence"] for result in seen_results.values()]
        
        avg_seen_accuracy = np.mean(seen_accuracies)
        avg_seen_confidence = np.mean(seen_confidences)
        
        unseen_accuracy = usdjpy_result["accuracy"]
        unseen_confidence = usdjpy_result["mean_confidence"]
        
        # Calculate generalization score
        generalization_score = unseen_accuracy / avg_seen_accuracy if avg_seen_accuracy > 0 else 0
        confidence_retention = unseen_confidence / avg_seen_confidence if avg_seen_confidence > 0 else 0
        
        # Display results
        display_results(seen_results, usdjpy_result, {
            "avg_seen_accuracy": avg_seen_accuracy,
            "unseen_accuracy": unseen_accuracy,
            "generalization_score": generalization_score,
            "avg_seen_confidence": avg_seen_confidence,
            "unseen_confidence": unseen_confidence,
            "confidence_retention": confidence_retention,
            "baseline_val_accuracy": baseline_val_accuracy
        })
        
        return {
            "seen_results": seen_results,
            "unseen_result": usdjpy_result,
            "generalization_score": generalization_score,
            "confidence_retention": confidence_retention
        }
        
    except Exception as e:
        console.print(f"❌ [red]Test failed: {str(e)}[/red]")
        logger.error(f"Generalization test error: {e}", exc_info=True)
        return None

def display_results(seen_results, unseen_result, analysis):
    """Display formatted test results."""
    console.print("\n📊 [bold green]True Generalization Test Results[/bold green]")
    
    # Results table
    table = Table(title="Cross-Symbol Performance Comparison")
    table.add_column("Symbol", style="cyan", width=10)
    table.add_column("Type", style="yellow", width=8)
    table.add_column("Accuracy", style="green", justify="right", width=10)
    table.add_column("Precision", style="blue", justify="right", width=10)
    table.add_column("Confidence", style="magenta", justify="right", width=10)
    table.add_column("Samples", style="white", justify="right", width=8)
    
    # Add seen symbols
    for symbol, result in seen_results.items():
        table.add_row(
            symbol,
            "Seen",
            f"{result['accuracy']:.1%}",
            f"{result['precision']:.1%}",
            f"{result['mean_confidence']:.3f}",
            f"{result['sample_count']:,}"
        )
    
    # Add unseen symbol
    table.add_row(
        unseen_result["symbol"],
        "[red]Unseen[/red]",
        f"{unseen_result['accuracy']:.1%}",
        f"{unseen_result['precision']:.1%}",
        f"{unseen_result['mean_confidence']:.3f}",
        f"{unseen_result['sample_count']:,}"
    )
    
    console.print(table)
    
    # Analysis summary
    console.print(f"\n🎯 [bold]Generalization Analysis:[/bold]")
    console.print(f"   Baseline (Training): {analysis['baseline_val_accuracy']:.1%}")
    console.print(f"   Average Seen Performance: {analysis['avg_seen_accuracy']:.1%}")
    console.print(f"   Unseen Symbol (USDJPY): {analysis['unseen_accuracy']:.1%}")
    console.print(f"   Generalization Score: {analysis['generalization_score']:.3f}")
    console.print(f"   Confidence Retention: {analysis['confidence_retention']:.1%}")
    
    # Interpretation
    gen_score = analysis['generalization_score']
    console.print(f"\n💡 [bold]Test Results:[/bold]")
    
    if gen_score >= 0.9:
        console.print(f"   ✅ [bold green]EXCELLENT GENERALIZATION[/bold green]")
        console.print(f"   🎯 Universal patterns successfully transfer to unseen symbols")
    elif gen_score >= 0.7:
        console.print(f"   ✅ [bold green]GOOD GENERALIZATION[/bold green]") 
        console.print(f"   🎯 Model adapts well to new symbols with minor performance drop")
    elif gen_score >= 0.5:
        console.print(f"   ⚠️  [bold yellow]MODERATE GENERALIZATION[/bold yellow]")
        console.print(f"   🔧 Shows some transfer capability but may need improvement")
    else:
        console.print(f"   ❌ [bold red]POOR GENERALIZATION[/bold red]")
        console.print(f"   🔄 Significant symbol-specific overfitting detected")
    
    # Confidence analysis
    conf_retention = analysis['confidence_retention']
    if conf_retention >= 0.8:
        console.print(f"   📊 Strong confidence retention ({conf_retention:.1%})")
    elif conf_retention >= 0.6:
        console.print(f"   📊 Moderate confidence retention ({conf_retention:.1%})")
    else:
        console.print(f"   📊 Weak confidence retention ({conf_retention:.1%}) - model uncertainty on unseen symbols")

if __name__ == "__main__":
    results = run_true_generalization_test()
    if results:
        console.print(f"\n🚀 [bold]True generalization test completed successfully![/bold]")
    else:
        console.print(f"\n❌ [bold red]True generalization test failed![/bold red]")