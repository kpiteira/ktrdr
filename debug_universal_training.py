#!/usr/bin/env python3
"""Debug universal training issues"""

import sys
from rich.console import Console

console = Console()

def debug_universal_training():
    """Debug step by step what's happening in universal training."""
    console.print("🔍 [bold cyan]Debugging Universal Training[/bold cyan]")
    
    try:
        # Step 1: Test basic imports
        console.print("Step 1: Testing imports...")
        from ktrdr.training.train_strategy import StrategyTrainer
        from ktrdr.neural.models.mlp import UniversalMLPTradingModel
        from ktrdr.training.universal_fuzzy_processor import UniversalFuzzyNeuralProcessor
        console.print("✅ All imports successful")
        
        # Step 2: Test config loading
        console.print("Step 2: Testing config loading...")
        import yaml
        with open('strategies/universal_zero_shot_model.yaml', 'r') as f:
            config = yaml.safe_load(f)
        console.print(f"✅ Config loaded: {config['name']}, scope: {config.get('scope')}")
        
        # Step 3: Test data loading (very minimal)
        console.print("Step 3: Testing data loading...")
        from ktrdr.data.data_manager import DataManager
        data_manager = DataManager()
        
        # Load just a tiny bit of data
        eurusd_data = data_manager.load_data("EURUSD", "1h", mode="local")
        if eurusd_data is not None:
            # Take just 100 rows for speed
            eurusd_data = eurusd_data.iloc[-100:]
            console.print(f"✅ Loaded {len(eurusd_data)} EURUSD bars")
        else:
            console.print("❌ Failed to load EURUSD data")
            return False
            
        # Step 4: Test indicator calculation
        console.print("Step 4: Testing indicator calculation...")
        from ktrdr.indicators.indicator_engine import IndicatorEngine
        
        indicator_engine = IndicatorEngine()
        indicator_engine.configure_indicators(config['indicators'])
        
        indicators = indicator_engine.calculate_indicators(eurusd_data)
        console.print(f"✅ Calculated {len(indicators.columns)} indicators")
        
        # Step 5: Test fuzzy processing
        console.print("Step 5: Testing fuzzy processing...")
        from ktrdr.fuzzy.engine import FuzzyEngine
        
        fuzzy_engine = FuzzyEngine(config['fuzzy_sets'])
        fuzzy_memberships = fuzzy_engine.generate_memberships(indicators, eurusd_data)
        console.print(f"✅ Generated {len(fuzzy_memberships.columns)} fuzzy features")
        
        # Step 6: Test universal feature processing
        console.print("Step 6: Testing universal feature processing...")
        processor = UniversalFuzzyNeuralProcessor(config['model']['features'])
        
        universal_features, fuzzy_features = processor.prepare_universal_input(
            fuzzy_memberships, indicators
        )
        console.print(f"✅ Created universal features: {universal_features.shape}")
        
        # Step 7: Test model creation
        console.print("Step 7: Testing universal model creation...")
        model = UniversalMLPTradingModel(config['model'])
        built_model = model.build_model(universal_features.shape[1])
        console.print(f"✅ Created universal model with {sum(p.numel() for p in built_model.parameters())} parameters")
        
        # Step 8: Test inference
        console.print("Step 8: Testing model inference...")
        import torch
        
        test_input = universal_features[:10]  # First 10 samples
        built_model.eval()
        with torch.no_grad():
            output = built_model(test_input)
        console.print(f"✅ Model inference successful: {output.shape}")
        
        console.print("\n🎯 [bold green]All components working correctly![/bold green]")
        console.print("The issue may be in the full training loop or data volume.")
        
        return True
        
    except Exception as e:
        console.print(f"❌ [red]Debug failed at: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_universal_training()
    if success:
        console.print("\n✅ Components are working - ready for full training")
    else:
        console.print("\n❌ Found issues in universal training components")