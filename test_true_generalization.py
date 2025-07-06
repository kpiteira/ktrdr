#!/usr/bin/env python3
"""
True Generalization Test - Phase 5

Tests whether the universal model trained on EURUSD + GBPUSD can generalize 
to unseen USDJPY without retraining.

This script:
1. Loads the pre-trained universal model from EURUSD + GBPUSD training
2. Applies it to USDJPY data for inference-only evaluation
3. Compares performance on seen vs unseen symbols
4. Validates true cross-symbol generalization capability
"""

import asyncio
import torch
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

from ktrdr import get_logger
from ktrdr.data.data_manager import DataManager
from ktrdr.training.train_strategy import StrategyTrainer
from ktrdr.training.model_storage import ModelStorage
from ktrdr.config.strategy_loader import strategy_loader
from ktrdr.training.multi_symbol_data_loader import MultiSymbolDataLoader
from ktrdr.neural.models.mlp import MultiSymbolMLPTradingModel
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from rich.console import Console
from rich.table import Table

logger = get_logger(__name__)
console = Console()

class GeneralizationTester:
    """Test true cross-symbol generalization capabilities."""
    
    def __init__(self):
        self.data_manager = DataManager()
        self.model_storage = ModelStorage()
        
    async def run_generalization_test(self) -> Dict[str, Any]:
        """Run the complete generalization test."""
        console.print("🧠 [bold cyan]KTRDR True Generalization Test - Phase 5[/bold cyan]")
        console.print("=" * 60)
        
        # Step 1: Load the pre-trained universal model
        console.print("📂 Step 1: Loading pre-trained universal model...")
        model_path = "models/universal_generalization_model/EURUSD_GBPUSD_1h_v1"
        
        if not Path(model_path).exists():
            console.print(f"❌ [red]Model not found at: {model_path}[/red]")
            return {"success": False, "error": "Model not found"}
        
        # Load model files with safe globals
        import torch.serialization
        from ktrdr.neural.models.mlp import MultiSymbolMLP
        torch.serialization.add_safe_globals([MultiSymbolMLPTradingModel, MultiSymbolMLP])
        model_full = torch.load(f"{model_path}/model_full.pt", map_location='cpu', weights_only=False)
        console.print(f"✅ Loaded model with {sum(p.numel() for p in model_full.parameters())} parameters")
        
        # Step 2: Prepare USDJPY data (unseen symbol)
        console.print("📊 Step 2: Preparing USDJPY data (unseen symbol)...")
        usdjpy_data = await self._prepare_symbol_data("USDJPY", "1h", "2024-01-01", "2024-06-01")
        
        if usdjpy_data is None or len(usdjpy_data) < 200:
            console.print(f"❌ [red]Insufficient USDJPY data: {len(usdjpy_data) if usdjpy_data is not None else 0} bars[/red]")
            return {"success": False, "error": "Insufficient data"}
        
        console.print(f"✅ Loaded {len(usdjpy_data)} bars of USDJPY data")
        
        # Step 3: Test on seen symbols (EURUSD, GBPUSD) for comparison
        console.print("📊 Step 3: Testing on seen symbols (EURUSD, GBPUSD)...")
        seen_results = {}
        
        for symbol in ["EURUSD", "GBPUSD"]:
            console.print(f"   Testing {symbol}...")
            symbol_data = await self._prepare_symbol_data(symbol, "1h", "2024-01-01", "2024-06-01")
            if symbol_data is not None and len(symbol_data) >= 200:
                result = await self._evaluate_model_on_symbol(model_full, symbol_data, symbol, is_seen=True)
                seen_results[symbol] = result
                console.print(f"   ✅ {symbol}: {result['accuracy']:.1%} accuracy")
        
        # Step 4: Test on unseen symbol (USDJPY)
        console.print("🔍 Step 4: Testing on unseen symbol (USDJPY)...")
        unseen_result = await self._evaluate_model_on_symbol(model_full, usdjpy_data, "USDJPY", is_seen=False)
        console.print(f"   ✅ USDJPY: {unseen_result['accuracy']:.1%} accuracy")
        
        # Step 5: Analyze generalization performance
        console.print("📈 Step 5: Analyzing generalization performance...")
        analysis = self._analyze_generalization(seen_results, unseen_result)
        
        # Display results
        self._display_results(seen_results, unseen_result, analysis)
        
        return {
            "success": True,
            "seen_symbols": seen_results,
            "unseen_symbol": unseen_result,
            "analysis": analysis
        }
    
    async def _prepare_symbol_data(self, symbol: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Prepare data for a specific symbol."""
        try:
            data = self.data_manager.load_data(symbol, timeframe, mode="local")
            if data is None:
                return None
            
            # Filter date range
            data = data.loc[start_date:end_date]
            
            # Ensure we have sufficient data
            if len(data) < 200:
                logger.warning(f"Insufficient data for {symbol}: {len(data)} bars")
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {e}")
            return None
    
    async def _evaluate_model_on_symbol(self, model: torch.nn.Module, data: pd.DataFrame, symbol: str, is_seen: bool) -> Dict[str, Any]:
        """Evaluate model performance on a specific symbol."""
        try:
            # Load strategy configuration
            strategy_config, _ = strategy_loader.load_strategy_config("strategies/universal_generalization_model.yaml")
            
            # Use the training approach we know works
            from ktrdr.training.zigzag_labeler import ZigZagLabeler
            from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor
            from ktrdr.indicators.indicator_engine import IndicatorEngine
            from ktrdr.fuzzy.engine import FuzzyEngine
            
            # Process indicators
            indicator_engine = IndicatorEngine()
            indicators = {}
            for indicator_config in strategy_config.indicators:
                indicator_results = indicator_engine.calculate_indicator(
                    data, indicator_config.name, **indicator_config.model_dump(exclude={'name'})
                )
                indicators[indicator_config.name] = indicator_results
            
            # Create labels
            labeler = ZigZagLabeler()
            labels = labeler.create_labels(
                data, 
                threshold=strategy_config.training.labels.zigzag_threshold,
                lookahead=strategy_config.training.labels.label_lookahead
            )
            
            # Process fuzzy features
            fuzzy_engine = FuzzyEngine(strategy_config.fuzzy_sets)
            processor = FuzzyNeuralProcessor(
                feature_config=strategy_config.model.features,
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
            
            # Ensure we have valid data
            if len(features) == 0:
                raise ValueError("No valid features generated")
            
            # Create combined features
            if fuzzy_features is not None and len(fuzzy_features) > 0:
                combined_features = torch.cat([features, fuzzy_features], dim=1)
            else:
                combined_features = features
            
            # Create symbol indices (assign new index for unseen symbol)
            if is_seen:
                # EURUSD = 0, GBPUSD = 1 (same as training)
                symbol_idx = 0 if symbol == "EURUSD" else 1
            else:
                # USDJPY = 2 (new, unseen symbol)
                symbol_idx = 2
            
            symbol_indices = torch.full((len(combined_features),), symbol_idx, dtype=torch.long)
            
            # Make predictions
            model.eval()
            with torch.no_grad():
                predictions = model(combined_features, symbol_indices)
                predicted_classes = torch.argmax(predictions, dim=1)
            
            # Calculate metrics
            actual_labels = labels.numpy()
            predicted_labels = predicted_classes.numpy()
            
            accuracy = accuracy_score(actual_labels, predicted_labels)
            precision = precision_score(actual_labels, predicted_labels, average='weighted', zero_division=0)
            recall = recall_score(actual_labels, predicted_labels, average='weighted', zero_division=0)
            f1 = f1_score(actual_labels, predicted_labels, average='weighted', zero_division=0)
            
            # Calculate confidence statistics
            confidence_scores = torch.max(torch.softmax(predictions, dim=1), dim=1)[0]
            mean_confidence = float(confidence_scores.mean())
            
            return {
                "symbol": symbol,
                "is_seen": is_seen,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "mean_confidence": mean_confidence,
                "sample_count": len(actual_labels),
                "symbol_index": symbol_idx
            }
            
        except Exception as e:
            logger.error(f"Error evaluating {symbol}: {e}")
            return {
                "symbol": symbol,
                "is_seen": is_seen,
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
                "mean_confidence": 0.0,
                "sample_count": 0,
                "error": str(e)
            }
    
    def _analyze_generalization(self, seen_results: Dict[str, Dict], unseen_result: Dict) -> Dict[str, Any]:
        """Analyze generalization performance."""
        if not seen_results:
            return {"error": "No seen symbol results available"}
        
        # Calculate average performance on seen symbols
        seen_accuracies = [result["accuracy"] for result in seen_results.values() if "error" not in result]
        seen_confidences = [result["mean_confidence"] for result in seen_results.values() if "error" not in result]
        
        if not seen_accuracies:
            return {"error": "No valid seen symbol results"}
        
        avg_seen_accuracy = np.mean(seen_accuracies)
        avg_seen_confidence = np.mean(seen_confidences)
        
        # Calculate generalization metrics
        unseen_accuracy = unseen_result.get("accuracy", 0.0)
        unseen_confidence = unseen_result.get("mean_confidence", 0.0)
        
        # Generalization score: how well unseen symbol performs relative to seen symbols
        generalization_score = unseen_accuracy / avg_seen_accuracy if avg_seen_accuracy > 0 else 0.0
        
        # Confidence degradation: how much confidence drops on unseen symbol
        confidence_degradation = (avg_seen_confidence - unseen_confidence) / avg_seen_confidence if avg_seen_confidence > 0 else 0.0
        
        return {
            "avg_seen_accuracy": avg_seen_accuracy,
            "unseen_accuracy": unseen_accuracy,
            "generalization_score": generalization_score,
            "avg_seen_confidence": avg_seen_confidence,
            "unseen_confidence": unseen_confidence,
            "confidence_degradation": confidence_degradation,
            "interpretation": self._interpret_generalization(generalization_score, confidence_degradation)
        }
    
    def _interpret_generalization(self, gen_score: float, conf_degradation: float) -> str:
        """Interpret generalization results."""
        if gen_score >= 0.9:
            return "Excellent generalization - model performs nearly as well on unseen symbol"
        elif gen_score >= 0.7:
            return "Good generalization - model adapts well to unseen symbol with minor performance drop"
        elif gen_score >= 0.5:
            return "Moderate generalization - model shows some ability to handle unseen symbol"
        elif gen_score >= 0.3:
            return "Weak generalization - significant performance drop on unseen symbol"
        else:
            return "Poor generalization - model struggles with unseen symbol"
    
    def _display_results(self, seen_results: Dict, unseen_result: Dict, analysis: Dict):
        """Display formatted results."""
        console.print("\\n📊 [bold green]Generalization Test Results[/bold green]")
        
        # Results table
        table = Table(title="Model Performance Comparison")
        table.add_column("Symbol", style="cyan", width=10)
        table.add_column("Type", style="yellow", width=8)
        table.add_column("Accuracy", style="green", justify="right", width=10)
        table.add_column("Precision", style="blue", justify="right", width=10)
        table.add_column("Confidence", style="magenta", justify="right", width=10)
        table.add_column("Samples", style="white", justify="right", width=8)
        
        # Add seen symbols
        for symbol, result in seen_results.items():
            if "error" not in result:
                table.add_row(
                    symbol,
                    "Seen",
                    f"{result['accuracy']:.1%}",
                    f"{result['precision']:.1%}",
                    f"{result['mean_confidence']:.3f}",
                    f"{result['sample_count']:,}"
                )
        
        # Add unseen symbol
        if "error" not in unseen_result:
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
        if "error" not in analysis:
            console.print(f"\\n🎯 [bold]Generalization Analysis:[/bold]")
            console.print(f"   Average Seen Accuracy: {analysis['avg_seen_accuracy']:.1%}")
            console.print(f"   Unseen Symbol Accuracy: {analysis['unseen_accuracy']:.1%}")
            console.print(f"   Generalization Score: {analysis['generalization_score']:.3f}")
            console.print(f"   Confidence Degradation: {analysis['confidence_degradation']:.1%}")
            console.print(f"\\n💡 [bold]Interpretation:[/bold]")
            console.print(f"   {analysis['interpretation']}")
            
            # Determine if test passed
            if analysis['generalization_score'] >= 0.7:
                console.print(f"\\n✅ [bold green]GENERALIZATION TEST PASSED[/bold green]")
                console.print(f"   Model demonstrates strong cross-symbol generalization")
            elif analysis['generalization_score'] >= 0.5:
                console.print(f"\\n⚠️  [bold yellow]GENERALIZATION TEST PARTIAL[/bold yellow]")
                console.print(f"   Model shows moderate generalization capability")
            else:
                console.print(f"\\n❌ [bold red]GENERALIZATION TEST FAILED[/bold red]")
                console.print(f"   Model lacks sufficient generalization capability")

async def main():
    """Run the generalization test."""
    tester = GeneralizationTester()
    results = await tester.run_generalization_test()
    return results

if __name__ == "__main__":
    results = asyncio.run(main())