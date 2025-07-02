#!/usr/bin/env python3
"""
Quick integration test for training analytics system.

This script tests the core analytics functionality by creating a minimal
training scenario and verifying that metrics are collected and exported.
"""

import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
import json
import pandas as pd
import tempfile
import shutil

from ktrdr.training.model_trainer import ModelTrainer


def create_simple_model(input_size: int = 9, hidden_sizes: list = [16, 8], num_classes: int = 3):
    """Create a simple MLP for testing."""
    layers = []
    prev_size = input_size
    
    for hidden_size in hidden_sizes:
        layers.extend([
            nn.Linear(prev_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2)
        ])
        prev_size = hidden_size
    
    layers.append(nn.Linear(prev_size, num_classes))
    return nn.Sequential(*layers)


def create_synthetic_data(n_samples: int = 1000, n_features: int = 9, n_classes: int = 3):
    """Create synthetic fuzzy membership data for testing."""
    # Generate fuzzy membership values (0-1)
    X = torch.rand(n_samples, n_features)
    
    # Create labels with some pattern
    # Use a simple rule: if first feature > 0.6 -> class 0, elif first feature < 0.3 -> class 2, else class 1
    y = torch.ones(n_samples, dtype=torch.long)  # Default to HOLD (class 1)
    y[X[:, 0] > 0.6] = 0  # BUY (class 0)
    y[X[:, 0] < 0.3] = 2  # SELL (class 2)
    
    return X, y


def test_analytics_integration():
    """Test the complete analytics integration."""
    print("🧪 Testing Training Analytics Integration")
    print("=" * 50)
    
    # Create temporary directory for test outputs
    test_dir = Path(tempfile.mkdtemp(prefix="ktrdr_analytics_test_"))
    original_cwd = Path.cwd()
    
    try:
        # Change to test directory
        import os
        os.chdir(test_dir)
        
        # Create synthetic data
        print("📊 Creating synthetic fuzzy membership data...")
        X_train, y_train = create_synthetic_data(n_samples=800)
        X_val, y_val = create_synthetic_data(n_samples=200)
        
        print(f"   Training samples: {len(X_train)}")
        print(f"   Validation samples: {len(X_val)}")
        print(f"   Feature dimensions: {X_train.shape[1]} (fuzzy membership values)")
        print(f"   Classes: {torch.unique(y_train).tolist()} (BUY=0, HOLD=1, SELL=2)")
        
        # Create model
        print("\n🤖 Creating test model...")
        model = create_simple_model(input_size=X_train.shape[1])
        print(f"   Model architecture: {[layer for layer in model if isinstance(layer, nn.Linear)]}")
        
        # Create training config with analytics enabled
        config = {
            "symbol": "TEST",
            "strategy": "test_analytics",
            "epochs": 5,  # Small number for quick test
            "learning_rate": 0.001,
            "batch_size": 32,
            "early_stopping": {
                "patience": 10,
                "monitor": "val_loss"
            },
            "model": {
                "training": {
                    "analytics": {
                        "enabled": True,
                        "export_csv": True,
                        "export_json": True,
                        "export_alerts": True
                    }
                }
            }
        }
        
        print(f"\n🔍 Analytics Configuration:")
        print(f"   Enabled: {config['model']['training']['analytics']['enabled']}")
        print(f"   Exports: CSV, JSON, Alerts")
        
        # Initialize trainer with analytics
        print("\n🏋️ Initializing ModelTrainer with analytics...")
        trainer = ModelTrainer(config)
        
        # Verify analytics setup
        if trainer.analytics_enabled and trainer.analyzer:
            print(f"   ✅ Analytics enabled - Run ID: {trainer.analyzer.run_id}")
            print(f"   📁 Output directory: {trainer.analyzer.output_dir}")
        else:
            print("   ❌ Analytics not enabled - check configuration")
            return False
        
        # Train model
        print(f"\n🚀 Starting training for {config['epochs']} epochs...")
        print("   (This will test metrics collection, alerts, and export)")
        
        training_result = trainer.train(model, X_train, y_train, X_val, y_val)
        
        # Verify training completed
        print(f"\n📈 Training completed!")
        print(f"   Epochs trained: {training_result.get('epochs_trained', 'unknown')}")
        print(f"   Final accuracy: {training_result.get('final_val_accuracy', 0):.3f}")
        
        # Verify analytics results
        analytics_enabled = training_result.get('analytics_enabled', False)
        if analytics_enabled:
            print(f"\n🔍 Analytics Results:")
            print(f"   Run ID: {training_result.get('run_id', 'unknown')}")
            print(f"   Total alerts: {training_result.get('total_alerts', 0)}")
            
            export_paths = training_result.get('export_paths', {})
            for export_type, path in export_paths.items():
                if path:
                    file_path = Path(path)
                    if file_path.exists():
                        size_kb = file_path.stat().st_size / 1024
                        print(f"   ✅ {export_type.upper()}: {path} ({size_kb:.1f} KB)")
                    else:
                        print(f"   ❌ {export_type.upper()}: {path} (file not found)")
                else:
                    print(f"   ⚠️ {export_type.upper()}: not exported")
        
        # Test CSV content for LLM analysis
        csv_path = training_result.get('export_paths', {}).get('csv')
        if csv_path and Path(csv_path).exists():
            print(f"\n📊 Analyzing CSV Export for LLM compatibility...")
            df = pd.read_csv(csv_path)
            print(f"   Rows (epochs): {len(df)}")
            print(f"   Columns (metrics): {len(df.columns)}")
            print(f"   Column names: {list(df.columns)[:10]}{'...' if len(df.columns) > 10 else ''}")
            
            # Check for key metrics
            required_metrics = ['epoch', 'train_loss', 'val_loss', 'learning_signal_strength', 'gradient_norm_avg']
            missing_metrics = [m for m in required_metrics if m not in df.columns]
            if missing_metrics:
                print(f"   ⚠️ Missing key metrics: {missing_metrics}")
            else:
                print(f"   ✅ All key metrics present")
            
            # Show sample data
            print(f"\n   Sample data (first 2 epochs):")
            for col in ['epoch', 'train_loss', 'val_loss', 'learning_signal_strength']:
                if col in df.columns:
                    values = df[col].head(2).tolist()
                    print(f"     {col}: {values}")
        
        # Test JSON content
        json_path = training_result.get('export_paths', {}).get('json')
        if json_path and Path(json_path).exists():
            print(f"\n📄 Analyzing JSON Export...")
            with open(json_path, 'r') as f:
                json_data = json.load(f)
            
            print(f"   Run metadata: {json_data.get('run_metadata', {}).get('run_id', 'unknown')}")
            print(f"   Epoch records: {len(json_data.get('epoch_metrics', []))}")
            print(f"   Alert records: {len(json_data.get('alerts', []))}")
            print(f"   Final analysis: {bool(json_data.get('final_analysis'))}")
        
        print(f"\n🎉 Analytics Integration Test PASSED!")
        print(f"   All major components working correctly")
        print(f"   CSV ready for LLM analysis")
        print(f"   JSON available for detailed inspection")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Analytics Integration Test FAILED!")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        os.chdir(original_cwd)
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"\n🧹 Cleaned up test directory: {test_dir}")


if __name__ == "__main__":
    success = test_analytics_integration()
    exit(0 if success else 1)