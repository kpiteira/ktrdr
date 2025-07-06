#!/usr/bin/env python3
"""
Comprehensive Test Plan for Phase 3 Enhanced Analytics Implementation

This test plan validates all the new analytics capabilities added in Phase 3:
- Multi-timeframe analytics (feature importance, correlations, contributions)
- Multi-symbol analytics (per-symbol performance, cross-symbol patterns)
- Enhanced CSV/JSON export schemas
- Integration with existing training pipeline

Test Scenarios (NOT implementation phases):
1. Multi-Timeframe Analytics Validation
2. Multi-Symbol Analytics Validation  
3. Enhanced Export Schema Validation
4. Integration with Training Pipeline
5. Error Handling and Edge Cases
"""

import sys
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
import tempfile
import json
import csv

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from ktrdr.training.analytics.metrics_collector import MetricsCollector
from ktrdr.training.analytics.detailed_metrics import DetailedTrainingMetrics
from ktrdr.training.analytics.training_analyzer import TrainingAnalyzer


class TestPhase3EnhancedAnalytics:
    """Test suite for Phase 3 Enhanced Analytics implementation."""
    
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.test_results = []
        
    def log_test_result(self, scenario: str, test_name: str, passed: bool, details: str = ""):
        """Log test result with scenario context."""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {
            'scenario': scenario,
            'test_name': test_name,
            'status': status,
            'passed': passed,
            'details': details
        }
        self.test_results.append(result)
        print(f"  {status}: {test_name}")
        if details and not passed:
            print(f"    Details: {details}")
    
    def create_mock_model(self, input_size: int = 50, hidden_size: int = 32, num_classes: int = 3):
        """Create a simple mock model for testing."""
        class MockModel(nn.Module):
            def __init__(self, input_size, hidden_size, num_classes):
                super().__init__()
                self.layer1 = nn.Linear(input_size, hidden_size)
                self.layer2 = nn.Linear(hidden_size, hidden_size)
                self.layer3 = nn.Linear(hidden_size, num_classes)
                self.relu = nn.ReLU()
                self.dropout = nn.Dropout(0.2)
                
            def forward(self, x):
                x = self.relu(self.layer1(x))
                x = self.dropout(x)
                x = self.relu(self.layer2(x))
                x = self.dropout(x)
                x = self.layer3(x)
                return x
        
        model = MockModel(input_size, hidden_size, num_classes).to(self.device)
        return model
    
    def create_mock_multi_timeframe_data(self, batch_size: int = 100, num_features: int = 50):
        """Create mock data with multi-timeframe features."""
        # Create feature names with timeframe indicators
        timeframes = ['15m', '1h', '4h', '1d']
        feature_names = []
        features_per_timeframe = num_features // len(timeframes)
        
        for tf in timeframes:
            for i in range(features_per_timeframe):
                if i % 3 == 0:
                    feature_names.append(f"rsi_{tf}_{i}")
                elif i % 3 == 1:
                    feature_names.append(f"macd_{tf}_{i}")
                else:
                    feature_names.append(f"bb_{tf}_{i}")
        
        # Add a few features without timeframe to test edge cases
        remaining = num_features - len(feature_names)
        for i in range(remaining):
            feature_names.append(f"universal_feature_{i}")
        
        # Create feature tensor with different patterns per timeframe
        feature_tensor = torch.randn(batch_size, num_features).to(self.device)
        
        # Make timeframes have distinct patterns
        for i, tf in enumerate(timeframes):
            start_idx = i * features_per_timeframe
            end_idx = (i + 1) * features_per_timeframe
            if end_idx <= num_features:
                # Add timeframe-specific bias
                feature_tensor[:, start_idx:end_idx] += (i + 1) * 0.5
        
        # Create labels
        labels = torch.randint(0, 3, (batch_size,)).to(self.device)
        
        return feature_tensor, feature_names, timeframes, labels
    
    def create_mock_multi_symbol_data(self, batch_size: int = 150, num_features: int = 30):
        """Create mock data with multi-symbol structure."""
        symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
        samples_per_symbol = batch_size // len(symbols)
        
        feature_tensor = torch.randn(batch_size, num_features).to(self.device)
        symbol_indices = torch.zeros(batch_size, dtype=torch.long).to(self.device)
        labels = torch.randint(0, 3, (batch_size,)).to(self.device)
        
        # Create symbol-specific patterns
        for i, symbol in enumerate(symbols):
            start_idx = i * samples_per_symbol
            end_idx = (i + 1) * samples_per_symbol
            if end_idx <= batch_size:
                symbol_indices[start_idx:end_idx] = i
                # Add symbol-specific bias to features
                feature_tensor[start_idx:end_idx] += (i + 1) * 0.3
                # Make some symbols perform better
                if i == 1:  # GBPUSD performs better
                    labels[start_idx:end_idx] = 1  # More HOLD predictions
        
        return feature_tensor, symbol_indices, symbols, labels
    
    def test_scenario_1_multi_timeframe_analytics(self):
        """Test Scenario 1: Multi-Timeframe Analytics Validation."""
        print("\n🔍 Test Scenario 1: Multi-Timeframe Analytics Validation")
        
        collector = MetricsCollector()
        model = self.create_mock_model()
        feature_tensor, feature_names, timeframes, labels = self.create_mock_multi_timeframe_data()
        
        try:
            # Test timeframe analytics collection
            analytics = collector.collect_timeframe_analytics(
                model, feature_tensor, feature_names, timeframes
            )
            
            # Test 1.1: Basic structure validation
            required_keys = ['timeframe_feature_importance', 'timeframe_contributions', 
                           'dominant_timeframe', 'timeframe_correlation_matrix']
            has_all_keys = all(key in analytics for key in required_keys)
            self.log_test_result(
                "Scenario 1", "Analytics structure contains all required keys", 
                has_all_keys, f"Missing keys: {[k for k in required_keys if k not in analytics]}"
            )
            
            # Test 1.2: Timeframe feature importance validation
            importance = analytics['timeframe_feature_importance']
            has_all_timeframes = all(tf in importance for tf in timeframes)
            importance_valid = all(isinstance(v, (int, float)) and v >= 0 for v in importance.values())
            self.log_test_result(
                "Scenario 1", "Feature importance includes all timeframes with valid values",
                has_all_timeframes and importance_valid,
                f"Timeframes: {list(importance.keys())}, Values: {list(importance.values())}"
            )
            
            # Test 1.3: Timeframe contributions validation
            contributions = analytics['timeframe_contributions']
            contributions_sum = sum(contributions.values())
            contributions_normalized = abs(contributions_sum - 1.0) < 0.1  # Allow small rounding error
            self.log_test_result(
                "Scenario 1", "Timeframe contributions sum to ~1.0 (normalized)",
                contributions_normalized,
                f"Sum: {contributions_sum}, Contributions: {contributions}"
            )
            
            # Test 1.4: Dominant timeframe validation
            dominant = analytics['dominant_timeframe']
            dominant_valid = dominant in timeframes if dominant else True
            self.log_test_result(
                "Scenario 1", "Dominant timeframe is valid",
                dominant_valid,
                f"Dominant: {dominant}, Valid timeframes: {timeframes}"
            )
            
            # Test 1.5: Correlation matrix validation
            corr_matrix = analytics['timeframe_correlation_matrix']
            matrix_valid = (
                len(corr_matrix) == len(timeframes) and
                all(tf in corr_matrix for tf in timeframes) and
                all(len(corr_matrix[tf]) == len(timeframes) for tf in timeframes)
            )
            self.log_test_result(
                "Scenario 1", "Correlation matrix has correct structure",
                matrix_valid,
                f"Matrix size: {len(corr_matrix)}x{len(corr_matrix.get(timeframes[0], {})) if corr_matrix else 0}"
            )
            
            # Test 1.6: Diagonal correlations are 1.0
            diagonal_correct = all(
                abs(corr_matrix[tf][tf] - 1.0) < 0.01 
                for tf in timeframes if tf in corr_matrix and tf in corr_matrix[tf]
            )
            self.log_test_result(
                "Scenario 1", "Correlation matrix diagonal elements are ~1.0",
                diagonal_correct
            )
            
        except Exception as e:
            self.log_test_result(
                "Scenario 1", "Multi-timeframe analytics execution", 
                False, f"Exception: {str(e)}"
            )
    
    def test_scenario_2_multi_symbol_analytics(self):
        """Test Scenario 2: Multi-Symbol Analytics Validation."""
        print("\n🔍 Test Scenario 2: Multi-Symbol Analytics Validation")
        
        collector = MetricsCollector()
        feature_tensor, symbol_indices, symbols, labels = self.create_mock_multi_symbol_data()
        model = self.create_mock_model(input_size=feature_tensor.shape[1])  # Match feature tensor size
        
        try:
            # Test symbol analytics collection
            analytics = collector.collect_symbol_analytics(
                model, feature_tensor, labels, symbol_indices, symbols
            )
            
            # Test 2.1: Basic structure validation
            required_keys = ['per_symbol_performance', 'cross_symbol_patterns',
                           'universal_feature_stability', 'zero_shot_confidence']
            has_all_keys = all(key in analytics for key in required_keys)
            self.log_test_result(
                "Scenario 2", "Analytics structure contains all required keys",
                has_all_keys, f"Missing keys: {[k for k in required_keys if k not in analytics]}"
            )
            
            # Test 2.2: Per-symbol performance validation
            per_symbol = analytics['per_symbol_performance']
            has_all_symbols = all(symbol in per_symbol for symbol in symbols)
            performance_metrics = ['accuracy', 'precision', 'recall', 'f1', 'sample_count']
            metrics_valid = all(
                all(metric in per_symbol[symbol] for metric in performance_metrics)
                for symbol in symbols if symbol in per_symbol
            )
            self.log_test_result(
                "Scenario 2", "Per-symbol performance includes all symbols and metrics",
                has_all_symbols and metrics_valid,
                f"Symbols: {list(per_symbol.keys())}, Expected: {symbols}"
            )
            
            # Test 2.3: Cross-symbol patterns validation
            patterns = analytics['cross_symbol_patterns']
            patterns_valid = (
                'cross_symbol_similarity' in patterns and
                'universal_patterns' in patterns and
                isinstance(patterns['cross_symbol_similarity'], (int, float)) and
                isinstance(patterns['universal_patterns'], list)
            )
            self.log_test_result(
                "Scenario 2", "Cross-symbol patterns have correct structure",
                patterns_valid,
                f"Patterns keys: {list(patterns.keys()) if patterns else 'None'}"
            )
            
            # Test 2.4: Universal feature stability validation
            stability = analytics['universal_feature_stability']
            stability_valid = isinstance(stability, (int, float)) and 0 <= stability <= 1
            self.log_test_result(
                "Scenario 2", "Universal feature stability is valid (0-1 range)",
                stability_valid,
                f"Stability: {stability}"
            )
            
            # Test 2.5: Zero-shot confidence validation
            confidence = analytics['zero_shot_confidence']
            confidence_valid = isinstance(confidence, (int, float)) and 0 <= confidence <= 1
            self.log_test_result(
                "Scenario 2", "Zero-shot confidence is valid (0-1 range)",
                confidence_valid,
                f"Confidence: {confidence}"
            )
            
            # Test 2.6: Sample counts are reasonable
            total_samples = sum(
                per_symbol[symbol]['sample_count'] 
                for symbol in symbols if symbol in per_symbol
            )
            sample_count_valid = total_samples == len(labels)
            self.log_test_result(
                "Scenario 2", "Per-symbol sample counts sum to total samples",
                sample_count_valid,
                f"Total from symbols: {total_samples}, Expected: {len(labels)}"
            )
            
        except Exception as e:
            self.log_test_result(
                "Scenario 2", "Multi-symbol analytics execution",
                False, f"Exception: {str(e)}"
            )
    
    def test_scenario_3_enhanced_export_schemas(self):
        """Test Scenario 3: Enhanced Export Schema Validation."""
        print("\n🔍 Test Scenario 3: Enhanced Export Schema Validation")
        
        try:
            # Create mock detailed metrics with Phase 3 data
            timeframes = ['15m', '1h', '4h']
            symbols = ['EURUSD', 'GBPUSD']
            
            metrics = DetailedTrainingMetrics(
                epoch=5,
                train_loss=0.25,
                train_accuracy=0.85,
                val_loss=0.30,
                val_accuracy=0.82,
                
                # Phase 3 Enhanced Analytics data
                timeframe_feature_importance={'15m': 0.4, '1h': 0.35, '4h': 0.25},
                timeframe_contributions={'15m': 0.3, '1h': 0.45, '4h': 0.25},
                dominant_timeframe='1h',
                timeframe_correlation_matrix={
                    '15m': {'15m': 1.0, '1h': 0.7, '4h': 0.5},
                    '1h': {'15m': 0.7, '1h': 1.0, '4h': 0.8},
                    '4h': {'15m': 0.5, '1h': 0.8, '4h': 1.0}
                },
                per_symbol_performance={
                    'EURUSD': {'accuracy': 0.85, 'f1': 0.83, 'sample_count': 50},
                    'GBPUSD': {'accuracy': 0.78, 'f1': 0.76, 'sample_count': 45}
                },
                universal_feature_stability=0.72,
                zero_shot_confidence=0.68
            )
            
            # Test 3.1: CSV export schema validation
            csv_row = metrics.to_csv_row()
            
            # Check basic fields are present
            basic_fields = ['epoch', 'train_loss', 'val_loss', 'train_acc', 'val_acc']
            has_basic = all(field in csv_row for field in basic_fields)
            self.log_test_result(
                "Scenario 3", "CSV export includes basic training fields",
                has_basic, f"Missing: {[f for f in basic_fields if f not in csv_row]}"
            )
            
            # Check Phase 3 fields are present
            phase3_fields = ['dominant_timeframe', 'universal_feature_stability', 'zero_shot_confidence']
            has_phase3 = all(field in csv_row for field in phase3_fields)
            self.log_test_result(
                "Scenario 3", "CSV export includes Phase 3 enhanced fields",
                has_phase3, f"Missing: {[f for f in phase3_fields if f not in csv_row]}"
            )
            
            # Check dynamic timeframe columns
            timeframe_columns = [f'timeframe_{tf}_importance' for tf in timeframes] + \
                              [f'timeframe_{tf}_contribution' for tf in timeframes]
            has_timeframe_cols = all(col in csv_row for col in timeframe_columns)
            self.log_test_result(
                "Scenario 3", "CSV export includes dynamic timeframe columns",
                has_timeframe_cols, f"Missing: {[c for c in timeframe_columns if c not in csv_row]}"
            )
            
            # Check dynamic symbol columns
            symbol_columns = []
            for symbol in symbols:
                symbol_columns.extend([
                    f'symbol_{symbol}_accuracy',
                    f'symbol_{symbol}_f1',
                    f'symbol_{symbol}_sample_count'
                ])
            has_symbol_cols = all(col in csv_row for col in symbol_columns)
            self.log_test_result(
                "Scenario 3", "CSV export includes dynamic symbol columns",
                has_symbol_cols, f"Missing: {[c for c in symbol_columns if c not in csv_row]}"
            )
            
            # Test 3.2: JSON export schema validation
            json_dict = metrics.to_json_dict()
            
            # Check Phase 3 sections are present
            phase3_sections = ['timeframe_analytics', 'symbol_analytics']
            has_phase3_sections = all(section in json_dict for section in phase3_sections)
            self.log_test_result(
                "Scenario 3", "JSON export includes Phase 3 analytics sections",
                has_phase3_sections, f"Missing: {[s for s in phase3_sections if s not in json_dict]}"
            )
            
            # Check timeframe analytics structure
            tf_analytics = json_dict.get('timeframe_analytics', {})
            tf_fields = ['feature_importance', 'contributions', 'dominant_timeframe', 'correlation_matrix']
            has_tf_fields = all(field in tf_analytics for field in tf_fields)
            self.log_test_result(
                "Scenario 3", "JSON timeframe analytics section has correct structure",
                has_tf_fields, f"Missing: {[f for f in tf_fields if f not in tf_analytics]}"
            )
            
            # Check symbol analytics structure
            sym_analytics = json_dict.get('symbol_analytics', {})
            sym_fields = ['per_symbol_performance', 'cross_symbol_patterns', 
                         'universal_feature_stability', 'zero_shot_confidence']
            has_sym_fields = all(field in sym_analytics for field in sym_fields)
            self.log_test_result(
                "Scenario 3", "JSON symbol analytics section has correct structure",
                has_sym_fields, f"Missing: {[f for f in sym_fields if f not in sym_analytics]}"
            )
            
        except Exception as e:
            self.log_test_result(
                "Scenario 3", "Enhanced export schemas execution",
                False, f"Exception: {str(e)}"
            )
    
    def test_scenario_4_training_integration(self):
        """Test Scenario 4: Integration with Training Pipeline."""
        print("\n🔍 Test Scenario 4: Integration with Training Pipeline")
        
        try:
            # Create temporary directory for test outputs
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create training analyzer
                config = {
                    "model": {
                        "training": {
                            "analytics": {
                                "export_csv": True,
                                "export_json": True,
                                "export_alerts": True
                            }
                        }
                    }
                }
                
                analyzer = TrainingAnalyzer(
                    run_id="test_phase3_integration",
                    output_dir=temp_path,
                    config=config
                )
                
                # Create mock training data
                model = self.create_mock_model()
                feature_tensor, feature_names, timeframes, labels = self.create_mock_multi_timeframe_data()
                symbol_tensor, symbol_indices, symbols, _ = self.create_mock_multi_symbol_data(
                    batch_size=100, num_features=50
                )
                
                # Simulate model training step
                optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
                model.train()
                outputs = model(feature_tensor)
                loss = nn.CrossEntropyLoss()(outputs, labels)
                loss.backward()
                
                predictions = torch.argmax(outputs, dim=1)
                accuracy = (predictions == labels).float().mean().item()
                
                train_metrics = {'loss': loss.item(), 'accuracy': accuracy}
                val_metrics = {'loss': loss.item() * 1.1, 'accuracy': accuracy * 0.95}
                
                # Test 4.1: Collect epoch metrics with Phase 3 analytics
                detailed_metrics = analyzer.collect_epoch_metrics(
                    epoch=1,
                    model=model,
                    train_metrics=train_metrics,
                    val_metrics=val_metrics,
                    optimizer=optimizer,
                    y_pred=predictions,
                    y_true=labels,
                    model_outputs=outputs,
                    batch_count=10,
                    total_samples=100,
                    early_stopping_triggered=False,
                    feature_tensor=feature_tensor,
                    feature_names=feature_names,
                    timeframes=timeframes,
                    symbol_indices=symbol_indices,
                    symbols=symbols
                )
                
                # Validate that Phase 3 analytics were collected
                has_timeframe_analytics = (
                    len(detailed_metrics.timeframe_feature_importance) > 0 or
                    detailed_metrics.dominant_timeframe is not None
                )
                self.log_test_result(
                    "Scenario 4", "Training pipeline collects timeframe analytics",
                    has_timeframe_analytics,
                    f"Timeframe importance: {detailed_metrics.timeframe_feature_importance}"
                )
                
                has_symbol_analytics = (
                    len(detailed_metrics.per_symbol_performance) > 0 or
                    detailed_metrics.universal_feature_stability > 0
                )
                self.log_test_result(
                    "Scenario 4", "Training pipeline collects symbol analytics",
                    has_symbol_analytics,
                    f"Symbol performance: {detailed_metrics.per_symbol_performance}"
                )
                
                # Test 4.2: Export functionality
                analyzer.finalize_training(final_epoch=1, stopping_reason="test_completed")
                export_paths = analyzer.export_all()
                
                # Check that files were created
                csv_created = export_paths.get('csv') and export_paths['csv'].exists()
                json_created = export_paths.get('json') and export_paths['json'].exists()
                
                self.log_test_result(
                    "Scenario 4", "Training analyzer creates CSV export file",
                    csv_created, f"CSV path: {export_paths.get('csv')}"
                )
                
                self.log_test_result(
                    "Scenario 4", "Training analyzer creates JSON export file", 
                    json_created, f"JSON path: {export_paths.get('json')}"
                )
                
                # Test 4.3: Validate exported CSV contains Phase 3 data
                if csv_created:
                    df = pd.read_csv(export_paths['csv'])
                    
                    # Check for Phase 3 columns
                    phase3_cols = ['dominant_timeframe', 'universal_feature_stability', 'zero_shot_confidence']
                    has_phase3_cols = all(col in df.columns for col in phase3_cols)
                    self.log_test_result(
                        "Scenario 4", "Exported CSV contains Phase 3 enhanced columns",
                        has_phase3_cols, f"Columns: {list(df.columns)}"
                    )
                    
                    # Check for dynamic timeframe columns
                    timeframe_cols = [col for col in df.columns if 'timeframe_' in col and '_importance' in col]
                    has_timeframe_cols = len(timeframe_cols) > 0
                    self.log_test_result(
                        "Scenario 4", "Exported CSV contains dynamic timeframe columns",
                        has_timeframe_cols, f"Timeframe columns: {timeframe_cols}"
                    )
                
                # Test 4.4: Validate exported JSON contains Phase 3 data
                if json_created:
                    with open(export_paths['json'], 'r') as f:
                        json_data = json.load(f)
                    
                    epoch_data = json_data.get('epoch_metrics', [])
                    if epoch_data:
                        first_epoch = epoch_data[0]
                        has_timeframe_section = 'timeframe_analytics' in first_epoch
                        has_symbol_section = 'symbol_analytics' in first_epoch
                        
                        self.log_test_result(
                            "Scenario 4", "Exported JSON contains timeframe analytics section",
                            has_timeframe_section
                        )
                        
                        self.log_test_result(
                            "Scenario 4", "Exported JSON contains symbol analytics section",
                            has_symbol_section
                        )
                
        except Exception as e:
            self.log_test_result(
                "Scenario 4", "Training pipeline integration execution",
                False, f"Exception: {str(e)}"
            )
    
    def test_scenario_5_error_handling_edge_cases(self):
        """Test Scenario 5: Error Handling and Edge Cases."""
        print("\n🔍 Test Scenario 5: Error Handling and Edge Cases")
        
        collector = MetricsCollector()
        
        try:
            # Test 5.1: Empty timeframes list
            model = self.create_mock_model()
            feature_tensor, feature_names, _, labels = self.create_mock_multi_timeframe_data()
            
            analytics = collector.collect_timeframe_analytics(
                model, feature_tensor, feature_names, []
            )
            
            empty_timeframes_handled = (
                analytics['timeframe_feature_importance'] == {} and
                analytics['dominant_timeframe'] is None
            )
            self.log_test_result(
                "Scenario 5", "Empty timeframes list handled gracefully",
                empty_timeframes_handled
            )
            
            # Test 5.2: Single timeframe (no correlations possible)
            analytics = collector.collect_timeframe_analytics(
                model, feature_tensor, feature_names, ['1h']
            )
            
            single_timeframe_handled = len(analytics['timeframe_correlation_matrix']) <= 1
            self.log_test_result(
                "Scenario 5", "Single timeframe handled gracefully",
                single_timeframe_handled
            )
            
            # Test 5.3: Empty symbols list
            analytics = collector.collect_symbol_analytics(
                model, feature_tensor, labels, None, []
            )
            
            empty_symbols_handled = (
                analytics['per_symbol_performance'] == {} and
                analytics['universal_feature_stability'] == 0.0
            )
            self.log_test_result(
                "Scenario 5", "Empty symbols list handled gracefully",
                empty_symbols_handled
            )
            
            # Test 5.4: Mismatched feature names and tensor size
            short_feature_names = feature_names[:10]  # Only 10 names for 50 features
            
            analytics = collector.collect_timeframe_analytics(
                model, feature_tensor, short_feature_names, ['15m', '1h']
            )
            
            mismatch_handled = isinstance(analytics, dict)  # Should not crash
            self.log_test_result(
                "Scenario 5", "Feature name/tensor size mismatch handled",
                mismatch_handled
            )
            
            # Test 5.5: No timeframe indicators in feature names
            generic_names = [f"feature_{i}" for i in range(len(feature_names))]
            
            analytics = collector.collect_timeframe_analytics(
                model, feature_tensor, generic_names, ['15m', '1h']
            )
            
            no_indicators_handled = all(
                importance == 0.0 for importance in analytics['timeframe_feature_importance'].values()
            )
            self.log_test_result(
                "Scenario 5", "Missing timeframe indicators handled",
                no_indicators_handled
            )
            
            # Test 5.6: Very small batch size
            small_tensor = feature_tensor[:5]  # Only 5 samples
            small_labels = labels[:5]
            small_indices = torch.zeros(5, dtype=torch.long).to(self.device)
            
            analytics = collector.collect_symbol_analytics(
                model, small_tensor, small_labels, small_indices, ['EURUSD']
            )
            
            small_batch_handled = isinstance(analytics, dict) and 'per_symbol_performance' in analytics
            self.log_test_result(
                "Scenario 5", "Very small batch size handled",
                small_batch_handled
            )
            
            # Test 5.7: Model with no gradients (eval mode)
            model.eval()
            with torch.no_grad():
                outputs = model(feature_tensor)
            
            # This should handle the case where gradients are not available
            analytics = collector.collect_timeframe_analytics(
                model, feature_tensor, feature_names, ['15m', '1h']
            )
            
            no_gradients_handled = isinstance(analytics, dict)
            self.log_test_result(
                "Scenario 5", "Model without gradients handled",
                no_gradients_handled
            )
            
        except Exception as e:
            self.log_test_result(
                "Scenario 5", "Error handling and edge cases execution",
                False, f"Exception: {str(e)}"
            )
    
    def run_all_test_scenarios(self):
        """Run all test scenarios and provide summary."""
        print("🧪 Starting Comprehensive Test Plan for Phase 3 Enhanced Analytics")
        print("=" * 80)
        
        # Run all test scenarios
        self.test_scenario_1_multi_timeframe_analytics()
        self.test_scenario_2_multi_symbol_analytics()
        self.test_scenario_3_enhanced_export_schemas()
        self.test_scenario_4_training_integration()
        self.test_scenario_5_error_handling_edge_cases()
        
        # Generate summary
        print("\n" + "=" * 80)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        # Group by scenario
        scenarios = {}
        for result in self.test_results:
            scenario = result['scenario']
            if scenario not in scenarios:
                scenarios[scenario] = {'passed': 0, 'total': 0, 'failed_tests': []}
            scenarios[scenario]['total'] += 1
            if result['passed']:
                scenarios[scenario]['passed'] += 1
            else:
                scenarios[scenario]['failed_tests'].append(result['test_name'])
        
        print("\nResults by Test Scenario:")
        for scenario, stats in scenarios.items():
            success_rate = (stats['passed'] / stats['total']) * 100
            status = "✅" if success_rate == 100 else "⚠️" if success_rate >= 80 else "❌"
            print(f"  {status} {scenario}: {stats['passed']}/{stats['total']} ({success_rate:.1f}%)")
            
            if stats['failed_tests']:
                print(f"    Failed tests: {', '.join(stats['failed_tests'])}")
        
        print("\n" + "=" * 80)
        
        if failed_tests == 0:
            print("🎉 ALL TESTS PASSED! Phase 3 Enhanced Analytics implementation is validated.")
        elif failed_tests <= 2:
            print("⚠️  Most tests passed with minor issues. Implementation is mostly validated.")
        else:
            print("❌ Multiple test failures detected. Review implementation before deployment.")
        
        return passed_tests, total_tests


def main():
    """Main test execution."""
    tester = TestPhase3EnhancedAnalytics()
    passed, total = tester.run_all_test_scenarios()
    
    # Exit with appropriate code
    exit_code = 0 if passed == total else 1
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)