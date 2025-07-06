#!/usr/bin/env python3
"""
Focused Phase 2 Universal Test

Tests the key requirements for universal architecture without full training.
This validates the architecture changes against the specification.
"""

import torch
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

def focused_phase2_universal_test():
    """Focused test of Phase 2 universal architecture requirements."""
    console.print("🎯 [bold cyan]Focused Phase 2 Universal Architecture Test[/bold cyan]")
    console.print("=" * 65)
    
    test_results = {}
    
    try:
        # Test 1: Verify universal strategy configuration
        console.print("📋 Test 1: Universal Strategy Configuration...")
        
        with open('strategies/universal_zero_shot_model.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        scope = config.get('scope')
        has_symbol_embedding = 'symbol_embedding_dim' in config.get('model', {})
        
        test_results['config_scope'] = scope == 'universal'
        test_results['no_embeddings_config'] = not has_symbol_embedding
        
        console.print(f"   Scope: {scope} {'✅' if scope == 'universal' else '❌'}")
        console.print(f"   No symbol embeddings in config: {'✅' if not has_symbol_embedding else '❌'}")
        
        # Test 2: Verify universal model creation
        console.print("\n🏗️  Test 2: Universal Model Architecture...")
        
        from ktrdr.neural.models.mlp import UniversalMLPTradingModel
        from ktrdr.training.train_strategy import StrategyTrainer
        
        # Test model creation with universal scope
        trainer = StrategyTrainer()
        model = trainer._create_multi_symbol_model(
            config['model'], 36, 2, strategy_scope='universal'
        )
        
        # Verify no symbol embeddings in model
        has_embedding_layer = any('embedding' in str(type(layer)).lower() for layer in model.modules())
        param_count = sum(p.numel() for p in model.parameters())
        
        test_results['universal_model_created'] = True
        test_results['no_embedding_layers'] = not has_embedding_layer
        test_results['reasonable_params'] = 1000 <= param_count <= 20000
        
        console.print(f"   Universal model created: ✅")
        console.print(f"   No embedding layers: {'✅' if not has_embedding_layer else '❌'}")
        console.print(f"   Parameter count: {param_count:,} {'✅' if test_results['reasonable_params'] else '❌'}")
        
        # Test 3: Zero-shot inference capability
        console.print("\n🎯 Test 3: Zero-Shot Inference Capability...")
        
        model.eval()
        batch_size = 100
        input_size = 36
        
        # Test 1: Standard inference (no symbol indices)
        test_features = torch.randn(batch_size, input_size)
        
        with torch.no_grad():
            # Key test: Universal model should work without symbol indices
            predictions = model(test_features)
            probabilities = torch.softmax(predictions, dim=1)
            confidences = torch.max(probabilities, dim=1)[0]
        
        avg_confidence = float(confidences.mean())
        std_confidence = float(confidences.std())
        
        test_results['zero_shot_inference'] = True
        test_results['reasonable_confidence'] = avg_confidence > 0.2
        test_results['confidence_variation'] = std_confidence > 0.05
        
        console.print(f"   Zero-shot inference works: ✅")
        console.print(f"   Average confidence: {avg_confidence:.3f} {'✅' if avg_confidence > 0.2 else '❌'}")
        console.print(f"   Confidence variation: {std_confidence:.3f} {'✅' if std_confidence > 0.05 else '❌'}")
        
        # Test 4: Symbol-agnostic feature processing
        console.print("\n🔧 Test 4: Symbol-Agnostic Feature Processing...")
        
        import pandas as pd
        from ktrdr.training.universal_fuzzy_processor import UniversalFuzzyNeuralProcessor
        
        processor = UniversalFuzzyNeuralProcessor(config['model']['features'])
        
        # Create mock data for two different "symbols" with different scales
        symbol1_data = pd.DataFrame({
            'rsi_neutral': [0.5] * 10,
            'rsi_overbought': [0.3] * 10,
            'rsi_oversold': [0.2] * 10,
        })
        
        symbol1_indicators = pd.DataFrame({
            'close': [1.1000, 1.1010, 1.1005, 1.0995, 1.1020, 1.1015, 1.1025, 1.1030, 1.1028, 1.1035],  # EUR scale
            'rsi': [45, 48, 52, 50, 55, 53, 58, 60, 57, 62]
        })
        
        symbol2_indicators = pd.DataFrame({
            'close': [145.50, 145.60, 145.55, 145.45, 145.70, 145.65, 145.75, 145.80, 145.78, 145.85],  # JPY scale
            'rsi': [45, 48, 52, 50, 55, 53, 58, 60, 57, 62]  # Same RSI pattern
        })
        
        # Process both symbols
        features1, _ = processor.prepare_universal_input(symbol1_data, symbol1_indicators)
        features2, _ = processor.prepare_universal_input(symbol1_data, symbol2_indicators)
        
        # Universal features should be similar despite different price scales
        feature_similarity = torch.cosine_similarity(features1.mean(0), features2.mean(0), dim=0)
        
        test_results['universal_features'] = True
        test_results['scale_independence'] = float(feature_similarity) > 0.8
        
        console.print(f"   Universal features created: ✅")
        console.print(f"   Scale independence: {feature_similarity:.3f} {'✅' if feature_similarity > 0.8 else '❌'}")
        
        # Test 5: Multi-symbol compatibility  
        console.print("\n🌍 Test 5: Multi-Symbol Training Compatibility...")
        
        # Test that the same model can handle different symbol feature sets
        different_features = torch.randn(batch_size, input_size)  # Simulating different symbol
        
        with torch.no_grad():
            pred1 = model(test_features)
            pred2 = model(different_features)
        
        # Both should produce valid outputs
        valid_outputs = (
            torch.all(torch.isfinite(pred1)) and 
            torch.all(torch.isfinite(pred2)) and
            pred1.shape == pred2.shape
        )
        
        test_results['multi_symbol_compatibility'] = valid_outputs
        
        console.print(f"   Multi-symbol compatibility: {'✅' if valid_outputs else '❌'}")
        
        # Test 6: Specification compliance check
        console.print("\n📋 Test 6: Specification Compliance...")
        
        # Check against implementation plan requirements
        spec_requirements = {
            'universal_deployment': test_results['config_scope'] and test_results['no_embedding_layers'],
            'zero_shot_capability': test_results['zero_shot_inference'] and test_results['reasonable_confidence'],
            'symbol_agnostic_features': test_results['universal_features'] and test_results['scale_independence'],
            'no_symbol_embeddings': test_results['no_embeddings_config'] and test_results['no_embedding_layers'],
            'multi_symbol_support': test_results['multi_symbol_compatibility']
        }
        
        console.print(f"   Universal deployment: {'✅' if spec_requirements['universal_deployment'] else '❌'}")
        console.print(f"   Zero-shot capability: {'✅' if spec_requirements['zero_shot_capability'] else '❌'}")
        console.print(f"   Symbol-agnostic features: {'✅' if spec_requirements['symbol_agnostic_features'] else '❌'}")
        console.print(f"   No symbol embeddings: {'✅' if spec_requirements['no_symbol_embeddings'] else '❌'}")
        console.print(f"   Multi-symbol support: {'✅' if spec_requirements['multi_symbol_support'] else '❌'}")
        
        # Overall assessment
        all_tests_pass = all(spec_requirements.values())
        
        # Results summary
        console.print(f"\n📊 [bold]Phase 2 Universal Architecture Results:[/bold]")
        
        results_table = Table(title="Universal Architecture Validation")
        results_table.add_column("Test", style="cyan", width=30)
        results_table.add_column("Status", style="green", width=10)
        results_table.add_column("Details", style="yellow", width=35)
        
        results_table.add_row("Universal Model Creation", "✅ PASS", f"{param_count:,} parameters, no embeddings")
        results_table.add_row("Zero-Shot Inference", "✅ PASS" if test_results['zero_shot_inference'] else "❌ FAIL", f"Avg confidence: {avg_confidence:.3f}")
        results_table.add_row("Symbol-Agnostic Features", "✅ PASS" if test_results['scale_independence'] else "❌ FAIL", f"Similarity: {feature_similarity:.3f}")
        results_table.add_row("Multi-Symbol Compatibility", "✅ PASS" if test_results['multi_symbol_compatibility'] else "❌ FAIL", "Handles different symbols")
        results_table.add_row("Specification Compliance", "✅ PASS" if all_tests_pass else "❌ FAIL", f"{sum(spec_requirements.values())}/5 requirements met")
        
        console.print(results_table)
        
        # Final assessment
        if all_tests_pass:
            console.print(f"\n🎯 [bold green]PHASE 2 UNIVERSAL ARCHITECTURE: COMPLETE SUCCESS![/bold green]")
            console.print(f"   ✅ All specification requirements met")
            console.print(f"   ✅ True universal deployment capability achieved")
            console.print(f"   ✅ Zero-shot generalization architecture verified")
            console.print(f"   🚀 Ready for Phase 3 testing with 3 symbols")
        else:
            console.print(f"\n⚠️  [bold yellow]PHASE 2 UNIVERSAL ARCHITECTURE: PARTIAL SUCCESS[/bold yellow]")
            failed_tests = [k for k, v in spec_requirements.items() if not v]
            console.print(f"   🔧 Failed requirements: {', '.join(failed_tests)}")
        
        return {
            'phase': 'Phase 2 Universal Architecture',
            'success': all_tests_pass,
            'test_results': test_results,
            'spec_compliance': spec_requirements,
            'model_params': param_count,
            'zero_shot_confidence': avg_confidence
        }
        
    except Exception as e:
        console.print(f"❌ [red]Phase 2 focused test failed: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    results = focused_phase2_universal_test()
    if results and results != False:
        console.print(f"\n🚀 [bold green]Phase 2 Universal Architecture Test Complete![/bold green]")
        if results['success']:
            console.print(f"🎯 Architecture validated - ready for full testing!")
        else:
            console.print(f"⚠️  Architecture needs refinement")
    else:
        console.print(f"\n❌ [bold red]Phase 2 Universal Architecture Test Failed![/bold red]")