#!/usr/bin/env python3
"""Debug script to examine neural network prediction pipeline."""

import torch
import torch.nn.functional as F
import pandas as pd
import numpy as np
import json
import pickle
from pathlib import Path

from ktrdr.neural.models.mlp import MLPTradingModel
from ktrdr.decision.engine import DecisionEngine
from ktrdr.training.feature_engineering import FeatureEngineer
from ktrdr.training.model_storage import ModelStorage


def debug_neural_predictions():
    """Debug the neural network prediction pipeline."""
    
    # Load the latest model using ModelStorage
    model_storage = ModelStorage()
    
    print(f"🔍 Loading model for neuro_mean_reversion/MSFT/1h")
    
    try:
        model_data = model_storage.load_model("neuro_mean_reversion", "MSFT", "1h", "v6")
        
        print(f"📊 Model loaded successfully:")
        print(f"  - Model type: {model_data['metadata']['model_type']}")
        print(f"  - Input size: {model_data['metadata']['input_size']}")
        print(f"  - Training accuracy: {model_data['metadata']['training_summary']['final_accuracy']:.4f}")
        print(f"  - Validation accuracy: {model_data['metadata']['training_summary']['best_val_accuracy']:.4f}")
        print(f"  - Confidence threshold: {model_data['config']['decisions']['confidence_threshold']}")
        
        # Get the actual PyTorch model
        pytorch_model = model_data['model']
        
        # Check if model is a state dict - if so, we need to load the full model
        if isinstance(pytorch_model, dict):
            print(f"⚠️ Model is a state dict, loading full model...")
            model_path = model_data['model_path']
            pytorch_model = torch.load(f"{model_path}/model_full.pt", map_location='cpu', weights_only=False)
        config = model_data['config']
        scaler = model_data['scaler']
        features_data = model_data['features']
        
        print(f"✅ Model loaded. PyTorch model type: {type(pytorch_model)}")
        
    except Exception as e:
        print(f"❌ Error loading with ModelStorage: {e}")
        print("Falling back to manual loading...")
        
        # Manual loading fallback
        model_path = "/Users/karl/Documents/dev/ktrdr2/models/neuro_mean_reversion/MSFT_1h_v6"
        
        # Load model config
        with open(f"{model_path}/config.json", "r") as f:
            config = json.load(f)
        
        # Load features.json 
        with open(f"{model_path}/features.json", "r") as f:
            features_data = json.load(f)
        
        # Load scaler
        try:
            with open(f"{model_path}/scaler.pkl", "rb") as f:
                scaler = pickle.load(f)
            print(f"📏 Scaler loaded from pickle file")
        except:
            scaler = None
            print(f"⚠️ No scaler file found")
        
        # Load the full PyTorch model directly
        pytorch_model = torch.load(f"{model_path}/model_full.pt", map_location='cpu', weights_only=False)
        
        print(f"📊 Model config loaded:")
        print(f"  - Model type: {config['model']['type']}")
        print(f"  - Input size: {config['model']['input_size']}")
        print(f"  - Hidden layers: {config['model']['architecture']['hidden_layers']}")
        print(f"  - Confidence threshold: {config['decisions']['confidence_threshold']}")
        print(f"✅ PyTorch model loaded. Type: {type(pytorch_model)}")
    
    # Create some test data to see what the model outputs
    # Let's create varied test inputs to see if model outputs vary
    test_cases = [
        # Test case 1: Oversold RSI, negative MACD
        {
            "fuzzy": {"rsi_oversold": 0.8, "rsi_neutral": 0.2, "rsi_overbought": 0.0,
                     "macd_negative": 0.9, "macd_neutral": 0.1, "macd_positive": 0.0,
                     "sma_below": 0.7, "sma_near": 0.3, "sma_above": 0.0},
            "indicators": {"rsi": 25, "macd": -0.8, "macd_signal": -0.5, "macd_histogram": -0.3, "sma": 150},
            "price": {"open": 150, "high": 155, "low": 148, "close": 152, "volume": 1000000},
            "description": "Oversold conditions - should favor BUY"
        },
        # Test case 2: Overbought RSI, positive MACD  
        {
            "fuzzy": {"rsi_oversold": 0.0, "rsi_neutral": 0.1, "rsi_overbought": 0.9,
                     "macd_negative": 0.0, "macd_neutral": 0.1, "macd_positive": 0.9,
                     "sma_below": 0.0, "sma_near": 0.2, "sma_above": 0.8},
            "indicators": {"rsi": 85, "macd": 1.2, "macd_signal": 0.8, "macd_histogram": 0.4, "sma": 148},
            "price": {"open": 150, "high": 155, "low": 148, "close": 152, "volume": 1000000},
            "description": "Overbought conditions - should favor SELL"
        },
        # Test case 3: Neutral conditions
        {
            "fuzzy": {"rsi_oversold": 0.1, "rsi_neutral": 0.8, "rsi_overbought": 0.1,
                     "macd_negative": 0.2, "macd_neutral": 0.6, "macd_positive": 0.2,
                     "sma_below": 0.1, "sma_near": 0.8, "sma_above": 0.1},
            "indicators": {"rsi": 50, "macd": 0.1, "macd_signal": 0.05, "macd_histogram": 0.05, "sma": 151},
            "price": {"open": 150, "high": 155, "low": 148, "close": 152, "volume": 1000000},
            "description": "Neutral conditions - should favor HOLD"
        }
    ]
    
    print(f"\n🧪 Testing {len(test_cases)} different input scenarios:")
    
    # Create feature engineer if scaler is available
    feature_config = config['model'].get('features', {})
    engineer = None
    if scaler is not None:
        engineer = FeatureEngineer(feature_config)
        engineer.scaler = scaler
        print(f"📏 Scaler loaded successfully")
    else:
        print(f"⚠️ No scaler available - will test without feature scaling")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['description']} ---")
        
        # Create DataFrames from test data
        fuzzy_df = pd.DataFrame([test_case['fuzzy']])
        
        # Combine indicators and price data
        indicators_data = {**test_case['indicators'], **test_case['price']}
        indicators_df = pd.DataFrame([indicators_data])
        
        print(f"📥 Input fuzzy memberships: {test_case['fuzzy']}")
        print(f"📈 Input indicators: {test_case['indicators']}")
        
        try:
            # Prepare features using FeatureEngineer if available
            if engineer:
                features_tensor, feature_names = engineer.prepare_features(
                    fuzzy_data=fuzzy_df,
                    indicators=indicators_df, 
                    price_data=indicators_df[['open', 'high', 'low', 'close', 'volume']]
                )
                features = features_tensor
            else:
                # Fallback: create simple feature vector
                fuzzy_values = list(test_case['fuzzy'].values())
                indicator_values = list(test_case['indicators'].values())
                price_values = list(test_case['price'].values())
                all_values = fuzzy_values + indicator_values + price_values
                features = torch.tensor([all_values], dtype=torch.float32)
            
            print(f"🔧 Features tensor shape: {features.shape}")
            print(f"🔧 Features tensor: {features.numpy().flatten()[:10]}... (first 10)")
            
            # Get raw model outputs directly from PyTorch model
            pytorch_model.eval()
            with torch.no_grad():
                # Get outputs from all layers to debug
                x = features
                layer_outputs = []
                
                # Manually iterate through layers
                for i, layer in enumerate(pytorch_model):
                    x = layer(x)
                    layer_outputs.append(x.clone())
                    print(f"     Layer {i} ({layer.__class__.__name__}): output shape {x.shape}, sample values {x.flatten()[:3].numpy()}")
                    if isinstance(layer, torch.nn.Softmax):
                        break
                
                # Get the final outputs
                outputs = pytorch_model(features)
                
                # Find pre-softmax logits
                pre_softmax_logits = None
                for i in range(len(layer_outputs) - 1, -1, -1):
                    layer = pytorch_model[i]
                    if not isinstance(layer, torch.nn.Softmax):
                        pre_softmax_logits = layer_outputs[i]
                        break
                
                if pre_softmax_logits is not None:
                    print(f"🎯 Raw logits (pre-softmax): {pre_softmax_logits.numpy().flatten()}")
                print(f"🎯 Final softmax probabilities: {outputs.numpy().flatten()}")
                
                # Manual calculation to verify
                probs = outputs[0].numpy()
                signal_idx = np.argmax(probs)
                confidence = float(probs[signal_idx])
                signal_map = {0: "BUY", 1: "HOLD", 2: "SELL"}
                manual_signal = signal_map[signal_idx]
                
                print(f"🔍 Manual verification:")
                print(f"   - Raw probabilities: BUY={probs[0]:.6f}, HOLD={probs[1]:.6f}, SELL={probs[2]:.6f}")
                print(f"   - Argmax index: {signal_idx} -> {manual_signal}")
                print(f"   - Confidence: {confidence:.6f}")
                
                # Check if probabilities sum to 1 (they should after softmax)
                prob_sum = np.sum(probs)
                print(f"   - Probability sum: {prob_sum:.6f} (should be ~1.0)")
                
        except Exception as e:
            print(f"❌ Error processing test case: {e}")
            import traceback
            traceback.print_exc()
    
    # Additional analysis: Check if model weights look reasonable
    print(f"\n🔍 Analyzing model weights:")
    
    for name, param in pytorch_model.named_parameters():
        if param.requires_grad:
            weight_stats = {
                'mean': param.data.mean().item(),
                'std': param.data.std().item(),
                'min': param.data.min().item(),
                'max': param.data.max().item()
            }
            print(f"   {name}: shape={list(param.shape)}, mean={weight_stats['mean']:.6f}, std={weight_stats['std']:.6f}")
    
    # Test with completely different feature vectors to see if the model is truly "stuck"
    print(f"\n🧪 Testing with extreme/random inputs to check model responsiveness:")
    
    extreme_tests = [
        {
            "name": "All zeros",
            "features": torch.zeros(1, 17)
        },
        {
            "name": "All ones", 
            "features": torch.ones(1, 17)
        },
        {
            "name": "Random normal",
            "features": torch.randn(1, 17)
        },
        {
            "name": "Large positive values",
            "features": torch.ones(1, 17) * 10
        },
        {
            "name": "Large negative values", 
            "features": torch.ones(1, 17) * -10
        }
    ]
    
    for test in extreme_tests:
        print(f"\n--- {test['name']} ---")
        print(f"Input: {test['features'].flatten()[:5].numpy()}...")
        
        pytorch_model.eval()
        with torch.no_grad():
            outputs = pytorch_model(test['features'])
            probs = outputs[0].numpy()
            signal_idx = np.argmax(probs)
            signal_map = {0: "BUY", 1: "HOLD", 2: "SELL"}
            
            print(f"Output: BUY={probs[0]:.6f}, HOLD={probs[1]:.6f}, SELL={probs[2]:.6f}")
            print(f"Signal: {signal_map[signal_idx]} (confidence: {probs[signal_idx]:.6f})")
    
    print(f"\n📊 Summary:")
    print(f"If all outputs are nearly identical (especially all HOLD with ~0.999 confidence),")
    print(f"then the model has likely collapsed to a trivial solution where it always predicts HOLD.")
    print(f"This could happen if:")
    print(f"  1. Training data was imbalanced (too many HOLD labels)")
    print(f"  2. Learning rate was too high, causing the model to converge to a poor local minimum")
    print(f"  3. The model architecture is too simple/complex for the problem")
    print(f"  4. Features are not informative or are poorly scaled")
    print(f"  5. The loss function or training procedure had issues")


if __name__ == "__main__":
    debug_neural_predictions()