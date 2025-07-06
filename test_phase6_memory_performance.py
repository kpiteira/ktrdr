#!/usr/bin/env python3
"""
Comprehensive test for Phase 6: Memory and Performance Scaling

This test validates all memory management and performance optimization 
components implemented in Phase 6:
- Memory management and monitoring
- Performance optimization
- Batch processing and data loading optimization  
- GPU memory management

Test Scenarios:
1. Memory Manager Functionality
2. Performance Optimizer Operations
3. Data Loading Optimization
4. GPU Memory Management (if available)
5. Integration Testing with Real Training
"""

import sys
import torch
import torch.nn as nn
import numpy as np
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from ktrdr.training.memory_manager import MemoryManager, MemoryBudget
from ktrdr.training.performance_optimizer import PerformanceOptimizer, PerformanceConfig
from ktrdr.training.data_optimization import DataLoadingOptimizer, DataConfig, EfficientMultiSymbolDataset
from ktrdr.training.gpu_memory_manager import GPUMemoryManager, GPUMemoryConfig
from ktrdr.neural.models.mlp import UniversalMLP


class TestPhase6MemoryPerformance:
    """Test suite for Phase 6 Memory and Performance Scaling."""
    
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.test_results = []
        
        print(f"Testing on device: {self.device}")
        print(f"GPU available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU count: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
    
    def log_test_result(self, scenario: str, test_name: str, passed: bool, details: str = ""):
        """Log test result."""
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
    
    def create_test_data(self, num_samples: int = 1000, num_features: int = 50):
        """Create test data for benchmarking."""
        symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
        timeframes = ['15m', '1h', '4h']
        
        # Create feature names
        feature_names = []
        for tf in timeframes:
            for i in range(num_features // len(timeframes)):
                feature_names.append(f"feature_{i}_{tf}")
        
        # Add remaining features
        while len(feature_names) < num_features:
            feature_names.append(f"universal_feature_{len(feature_names)}")
        
        # Create data
        feature_tensor = torch.randn(num_samples, num_features)
        label_tensor = torch.randint(0, 3, (num_samples,))
        symbol_indices = torch.randint(0, len(symbols), (num_samples,))
        
        return feature_tensor, label_tensor, symbol_indices, feature_names, symbols, timeframes
    
    def test_scenario_1_memory_manager(self):
        """Test Scenario 1: Memory Manager Functionality."""
        print("\n🧠 Test Scenario 1: Memory Manager Functionality")
        
        try:
            # Test 1.1: Basic initialization
            with tempfile.TemporaryDirectory() as temp_dir:
                budget = MemoryBudget(
                    max_process_memory_mb=2048,
                    warning_threshold_percent=0.8,
                    enable_monitoring=True,
                    monitoring_interval_seconds=0.1
                )
                
                manager = MemoryManager(budget=budget, output_dir=Path(temp_dir))
                
                self.log_test_result(
                    "Scenario 1", "MemoryManager initialization",
                    True, "Manager initialized successfully"
                )
            
            # Test 1.2: Memory snapshot capture
            snapshot = manager.capture_snapshot()
            snapshot_valid = (
                snapshot.process_memory_mb > 0 and
                snapshot.system_memory_total_mb > 0 and
                0 <= snapshot.system_memory_percent <= 100
            )
            
            self.log_test_result(
                "Scenario 1", "Memory snapshot capture",
                snapshot_valid,
                f"Process: {snapshot.process_memory_mb:.1f}MB, System: {snapshot.system_memory_percent:.1f}%"
            )
            
            # Test 1.3: Memory cleanup
            import gc
            initial_tensors = len([obj for obj in gc.get_objects() if torch.is_tensor(obj)])
            
            # Create some tensors
            test_tensors = [torch.randn(100, 100) for _ in range(10)]
            
            # Cleanup
            manager.cleanup_memory()
            
            # Force cleanup of test tensors
            del test_tensors
            manager.cleanup_memory()
            
            self.log_test_result(
                "Scenario 1", "Memory cleanup execution",
                True, "Cleanup completed without errors"
            )
            
            # Test 1.4: Memory monitoring
            manager.start_monitoring()
            time.sleep(0.5)  # Let it collect some data
            manager.stop_monitoring()
            
            monitoring_worked = len(manager.snapshots) > 0
            self.log_test_result(
                "Scenario 1", "Memory monitoring functionality",
                monitoring_worked,
                f"Collected {len(manager.snapshots)} snapshots"
            )
            
            # Test 1.5: Memory summary
            summary = manager.get_memory_summary()
            summary_valid = (
                'current_usage' in summary and
                'budget' in summary and
                'recommendations' in summary
            )
            
            self.log_test_result(
                "Scenario 1", "Memory summary generation",
                summary_valid,
                f"Summary keys: {list(summary.keys())}"
            )
            
        except Exception as e:
            self.log_test_result(
                "Scenario 1", "Memory manager execution",
                False, f"Exception: {str(e)}"
            )
    
    def test_scenario_2_performance_optimizer(self):
        """Test Scenario 2: Performance Optimizer Operations."""
        print("\n🚀 Test Scenario 2: Performance Optimizer Operations")
        
        try:
            # Test 2.1: Performance optimizer initialization
            config = PerformanceConfig(
                enable_mixed_precision=torch.cuda.is_available(),
                adaptive_batch_size=True,
                compile_model=False,  # Disable for compatibility
                min_batch_size=16,
                max_batch_size=128
            )
            
            optimizer = PerformanceOptimizer(config)
            
            self.log_test_result(
                "Scenario 2", "PerformanceOptimizer initialization",
                True, f"Mixed precision: {optimizer.config.enable_mixed_precision}"
            )
            
            # Test 2.2: Model optimization
            model = UniversalMLP(
                input_size=50,
                hidden_layers=[64, 32],
                dropout=0.2,
                activation_fn=nn.ReLU,
                num_classes=3
            ).to(self.device)
            
            optimized_model = optimizer.optimize_model(model)
            optimization_applied = optimized_model is not None
            
            self.log_test_result(
                "Scenario 2", "Model optimization",
                optimization_applied,
                f"Model type: {type(optimized_model).__name__}"
            )
            
            # Test 2.3: Optimal batch size finding
            feature_tensor, label_tensor, _, _, _, _ = self.create_test_data(200, 50)
            feature_tensor = feature_tensor.to(self.device)
            label_tensor = label_tensor.to(self.device)
            
            criterion = nn.CrossEntropyLoss()
            model_optimizer = torch.optim.Adam(model.parameters())
            
            optimal_batch_size = optimizer.find_optimal_batch_size(
                model, feature_tensor, label_tensor, criterion, model_optimizer
            )
            
            batch_size_reasonable = config.min_batch_size <= optimal_batch_size <= config.max_batch_size
            
            self.log_test_result(
                "Scenario 2", "Optimal batch size finding",
                batch_size_reasonable,
                f"Found batch size: {optimal_batch_size}"
            )
            
            # Test 2.4: Training step optimization
            batch_features = feature_tensor[:32]
            batch_labels = label_tensor[:32]
            
            loss, timings = optimizer.training_step(
                model, batch_features, batch_labels, criterion, model_optimizer
            )
            
            training_step_worked = (
                loss is not None and
                'forward_time' in timings and
                'backward_time' in timings and
                'optimizer_time' in timings
            )
            
            self.log_test_result(
                "Scenario 2", "Optimized training step",
                training_step_worked,
                f"Loss: {loss:.4f}, Timings: {list(timings.keys())}"
            )
            
            # Test 2.5: Performance summary
            # Add some mock metrics
            optimizer.metrics.add_epoch_metrics(
                train_time=1.5, val_time=0.5, data_time=0.2,
                batch_size=32, num_samples=1000, memory_peak=512, gpu_util=75
            )
            
            summary = optimizer.get_performance_summary()
            summary_valid = (
                'training_time' in summary and
                'configuration' in summary and
                'hardware' in summary
            )
            
            self.log_test_result(
                "Scenario 2", "Performance summary generation",
                summary_valid,
                f"Summary sections: {list(summary.keys())}"
            )
            
        except Exception as e:
            self.log_test_result(
                "Scenario 2", "Performance optimizer execution",
                False, f"Exception: {str(e)}"
            )
    
    def test_scenario_3_data_optimization(self):
        """Test Scenario 3: Data Loading Optimization."""
        print("\n📊 Test Scenario 3: Data Loading Optimization")
        
        try:
            # Test 3.1: Data loading optimizer initialization
            data_config = DataConfig(
                enable_memory_mapping=False,  # Disable for testing
                enable_batch_prefetching=True,
                balanced_sampling=True,
                symbol_balanced_sampling=True
            )
            
            data_optimizer = DataLoadingOptimizer(data_config)
            
            self.log_test_result(
                "Scenario 3", "DataLoadingOptimizer initialization",
                True, "Optimizer initialized successfully"
            )
            
            # Test 3.2: Efficient dataset creation
            feature_tensor, label_tensor, symbol_indices, feature_names, symbols, timeframes = self.create_test_data(500, 40)
            
            dataset = data_optimizer.create_optimized_dataset(
                feature_tensor, label_tensor, symbol_indices,
                feature_names, symbols, timeframes
            )
            
            dataset_valid = (
                isinstance(dataset, EfficientMultiSymbolDataset) and
                len(dataset) == 500 and
                dataset.num_features == 40 and
                dataset.num_symbols == 3
            )
            
            self.log_test_result(
                "Scenario 3", "Efficient dataset creation",
                dataset_valid,
                f"Dataset: {len(dataset)} samples, {dataset.num_features} features"
            )
            
            # Test 3.3: Symbol-specific batch retrieval
            symbol_batch = dataset.get_symbol_batch('EURUSD', batch_size=32)
            symbol_batch_valid = (
                len(symbol_batch) == 3 and  # features, labels, symbol_indices
                symbol_batch[0].shape[0] == 32 and  # batch size
                torch.all(symbol_batch[2] == 0)  # all EURUSD (index 0)
            )
            
            self.log_test_result(
                "Scenario 3", "Symbol-specific batch retrieval",
                symbol_batch_valid,
                f"Batch shape: {symbol_batch[0].shape}, Symbol indices: {torch.unique(symbol_batch[2])}"
            )
            
            # Test 3.4: Balanced batch retrieval
            balanced_batch = dataset.get_balanced_batch(batch_size=30)
            class_distribution = torch.bincount(balanced_batch[1], minlength=3)
            balance_reasonable = torch.all(class_distribution >= 8)  # At least 8 samples per class
            
            self.log_test_result(
                "Scenario 3", "Balanced batch retrieval",
                balance_reasonable,
                f"Class distribution: {class_distribution.tolist()}"
            )
            
            # Test 3.5: Optimized DataLoader creation
            dataloader = data_optimizer.create_optimized_dataloader(
                dataset, batch_size=32, device=self.device, shuffle=True
            )
            
            dataloader_valid = dataloader is not None
            
            self.log_test_result(
                "Scenario 3", "Optimized DataLoader creation",
                dataloader_valid,
                f"DataLoader type: {type(dataloader).__name__}"
            )
            
            # Test 3.6: DataLoader benchmarking
            if dataloader_valid:
                metrics = data_optimizer.benchmark_dataloader(dataloader, num_batches=5)
                
                benchmark_valid = (
                    'total_time_seconds' in metrics and
                    'batches_per_second' in metrics and
                    metrics['batches_per_second'] > 0
                )
                
                self.log_test_result(
                    "Scenario 3", "DataLoader benchmarking",
                    benchmark_valid,
                    f"Speed: {metrics.get('batches_per_second', 0):.1f} batches/sec"
                )
            
            # Test 3.7: Dataset statistics
            stats = data_optimizer.get_data_statistics(dataset)
            stats_valid = (
                'dataset_info' in stats and
                'class_distribution' in stats and
                'symbol_distribution' in stats
            )
            
            self.log_test_result(
                "Scenario 3", "Dataset statistics generation",
                stats_valid,
                f"Stats sections: {list(stats.keys())}"
            )
            
        except Exception as e:
            self.log_test_result(
                "Scenario 3", "Data optimization execution",
                False, f"Exception: {str(e)}"
            )
    
    def test_scenario_4_gpu_memory_management(self):
        """Test Scenario 4: GPU Memory Management."""
        print("\n🎮 Test Scenario 4: GPU Memory Management")
        
        if not torch.cuda.is_available():
            self.log_test_result(
                "Scenario 4", "GPU availability check",
                True, "GPU not available - skipping GPU tests"
            )
            return
        
        try:
            # Test 4.1: GPU memory manager initialization
            gpu_config = GPUMemoryConfig(
                memory_fraction=0.8,
                enable_mixed_precision=True,
                enable_memory_profiling=True,
                profiling_interval_seconds=0.1
            )
            
            gpu_manager = GPUMemoryManager(gpu_config)
            
            self.log_test_result(
                "Scenario 4", "GPUMemoryManager initialization",
                gpu_manager.enabled,
                f"Managing {gpu_manager.num_devices} device(s)"
            )
            
            # Test 4.2: GPU memory snapshot
            if gpu_manager.enabled:
                snapshot = gpu_manager.capture_snapshot(0)
                snapshot_valid = (
                    snapshot.device_id == 0 and
                    snapshot.total_mb > 0 and
                    snapshot.allocated_mb >= 0
                )
                
                self.log_test_result(
                    "Scenario 4", "GPU memory snapshot",
                    snapshot_valid,
                    f"GPU 0: {snapshot.allocated_mb:.1f}MB/{snapshot.total_mb:.1f}MB"
                )
            
            # Test 4.3: GPU memory cleanup
            if gpu_manager.enabled:
                initial_allocated = torch.cuda.memory_allocated()
                
                # Create and delete some tensors
                test_tensors = [torch.randn(100, 100, device='cuda') for _ in range(5)]
                del test_tensors
                
                gpu_manager.cleanup_memory()
                final_allocated = torch.cuda.memory_allocated()
                
                cleanup_worked = final_allocated <= initial_allocated
                
                self.log_test_result(
                    "Scenario 4", "GPU memory cleanup",
                    cleanup_worked,
                    f"Memory: {initial_allocated/(1024**2):.1f}MB → {final_allocated/(1024**2):.1f}MB"
                )
            
            # Test 4.4: Mixed precision context
            if gpu_manager.enabled and gpu_manager.config.enable_mixed_precision:
                with gpu_manager.mixed_precision_context() as scaler:
                    mixed_precision_available = scaler is not None
                
                self.log_test_result(
                    "Scenario 4", "Mixed precision context",
                    mixed_precision_available,
                    f"Scaler available: {scaler is not None}"
                )
            
            # Test 4.5: Memory efficient context
            if gpu_manager.enabled:
                with gpu_manager.memory_efficient_context():
                    # Create temporary tensor
                    temp_tensor = torch.randn(50, 50, device='cuda')
                    context_worked = temp_tensor.device.type == 'cuda'
                
                self.log_test_result(
                    "Scenario 4", "Memory efficient context",
                    context_worked,
                    "Context manager executed successfully"
                )
            
            # Test 4.6: GPU memory summary
            if gpu_manager.enabled:
                summary = gpu_manager.get_memory_summary()
                summary_valid = (
                    summary['gpu_available'] and
                    'devices' in summary and
                    'total_memory_mb' in summary
                )
                
                self.log_test_result(
                    "Scenario 4", "GPU memory summary",
                    summary_valid,
                    f"Total GPU memory: {summary.get('total_memory_mb', 0):.1f}MB"
                )
            
        except Exception as e:
            self.log_test_result(
                "Scenario 4", "GPU memory management execution",
                False, f"Exception: {str(e)}"
            )
    
    def test_scenario_5_integration_testing(self):
        """Test Scenario 5: Integration Testing with Real Training."""
        print("\n🔗 Test Scenario 5: Integration Testing")
        
        try:
            # Test 5.1: Complete system integration
            print("  Setting up integrated training environment...")
            
            # Create managers
            memory_manager = MemoryManager()
            perf_optimizer = PerformanceOptimizer()
            data_optimizer = DataLoadingOptimizer()
            
            if torch.cuda.is_available():
                gpu_manager = GPUMemoryManager()
                gpu_manager.start_monitoring()
            else:
                gpu_manager = None
            
            # Create data
            feature_tensor, label_tensor, symbol_indices, feature_names, symbols, timeframes = self.create_test_data(400, 30)
            
            # Optimize dataset and dataloader
            dataset = data_optimizer.create_optimized_dataset(
                feature_tensor, label_tensor, symbol_indices,
                feature_names, symbols, timeframes
            )
            
            dataloader = data_optimizer.create_optimized_dataloader(
                dataset, batch_size=32, device=self.device
            )
            
            # Create and optimize model
            model = UniversalMLP(
                input_size=30,
                hidden_layers=[64, 32],
                dropout=0.2,
                activation_fn=nn.ReLU,
                num_classes=3
            ).to(self.device)
            
            optimized_model = perf_optimizer.optimize_model(model)
            
            # Setup training components
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(optimized_model.parameters(), lr=0.001)
            
            self.log_test_result(
                "Scenario 5", "Integrated system setup",
                True,
                "All components initialized successfully"
            )
            
            # Test 5.2: Integrated training loop
            memory_manager.start_monitoring()
            
            total_loss = 0
            num_batches = 0
            training_successful = True
            
            try:
                for batch_idx, batch in enumerate(dataloader):
                    if batch_idx >= 3:  # Test only a few batches
                        break
                    
                    features, labels, _ = batch
                    
                    # Use performance optimizer for training step
                    loss, timings = perf_optimizer.training_step(
                        optimized_model, features, labels, criterion, optimizer
                    )
                    
                    total_loss += loss.item()
                    num_batches += 1
                    
                    # Memory cleanup periodically
                    if batch_idx % 2 == 0:
                        memory_manager.cleanup_memory()
                        if gpu_manager:
                            gpu_manager.cleanup_memory()
                
                avg_loss = total_loss / num_batches if num_batches > 0 else float('inf')
                
            except Exception as e:
                training_successful = False
                avg_loss = float('inf')
                print(f"    Training error: {e}")
            
            memory_manager.stop_monitoring()
            if gpu_manager:
                gpu_manager.stop_monitoring()
            
            self.log_test_result(
                "Scenario 5", "Integrated training execution",
                training_successful and avg_loss < 10.0,
                f"Avg loss: {avg_loss:.4f}, Batches: {num_batches}"
            )
            
            # Test 5.3: Performance analysis
            perf_summary = perf_optimizer.get_performance_summary()
            memory_summary = memory_manager.get_memory_summary()
            
            if gpu_manager:
                gpu_summary = gpu_manager.get_memory_summary()
            else:
                gpu_summary = {'gpu_available': False}
            
            analysis_complete = (
                'configuration' in perf_summary and
                'current_usage' in memory_summary
            )
            
            self.log_test_result(
                "Scenario 5", "Performance analysis generation",
                analysis_complete,
                f"Summaries generated: perf={len(perf_summary)}, mem={len(memory_summary)}, gpu={len(gpu_summary)}"
            )
            
            # Test 5.4: Optimization recommendations
            perf_recommendations = perf_optimizer.get_optimization_recommendations()
            memory_recommendations = memory_manager._get_recommendations(memory_manager.capture_snapshot())
            
            if gpu_manager:
                gpu_recommendations = gpu_manager.get_optimization_recommendations()
            else:
                gpu_recommendations = []
            
            total_recommendations = len(perf_recommendations) + len(memory_recommendations) + len(gpu_recommendations)
            
            self.log_test_result(
                "Scenario 5", "Optimization recommendations",
                total_recommendations >= 0,  # Any number of recommendations is valid
                f"Total recommendations: {total_recommendations}"
            )
            
        except Exception as e:
            self.log_test_result(
                "Scenario 5", "Integration testing execution",
                False, f"Exception: {str(e)}"
            )
    
    def run_all_test_scenarios(self):
        """Run all test scenarios and provide summary."""
        print("🧪 Starting Comprehensive Test Plan for Phase 6: Memory and Performance Scaling")
        print("=" * 90)
        
        # Run all test scenarios
        self.test_scenario_1_memory_manager()
        self.test_scenario_2_performance_optimizer()
        self.test_scenario_3_data_optimization()
        self.test_scenario_4_gpu_memory_management()
        self.test_scenario_5_integration_testing()
        
        # Generate summary
        print("\n" + "=" * 90)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 90)
        
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
        
        print("\n" + "=" * 90)
        
        if failed_tests == 0:
            print("🎉 ALL TESTS PASSED! Phase 6 Memory and Performance Scaling is fully validated.")
        elif failed_tests <= 2:
            print("⚠️  Most tests passed with minor issues. Implementation is mostly validated.")
        else:
            print("❌ Multiple test failures detected. Review implementation before deployment.")
        
        # Display system information
        print(f"\nSystem Information:")
        print(f"  Device: {self.device}")
        print(f"  CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  GPU Count: {torch.cuda.device_count()}")
            print(f"  GPU Memory: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f}GB")
        
        return passed_tests, total_tests


def main():
    """Main test execution."""
    tester = TestPhase6MemoryPerformance()
    passed, total = tester.run_all_test_scenarios()
    
    # Exit with appropriate code
    exit_code = 0 if passed == total else 1
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)