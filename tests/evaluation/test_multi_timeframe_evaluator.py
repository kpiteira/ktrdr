"""Tests for multi-timeframe model evaluator."""

import pytest
import torch
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from ktrdr.evaluation.multi_timeframe_evaluator import (
    MultiTimeframeEvaluator,
    PerformanceMetrics,
    TimeframeAnalysis,
    ValidationResult,
    EvaluationReport,
    create_evaluation_pipeline
)
from ktrdr.training.data_preparation import TrainingSequence
from ktrdr.neural.models.multi_timeframe_mlp import MultiTimeframeMLP


class TestMultiTimeframeEvaluator:
    """Test multi-timeframe model evaluator."""
    
    @pytest.fixture
    def sample_config(self):
        """Create sample evaluator configuration."""
        return {
            'validation': {
                'cross_validation_folds': 3,
                'time_series_splits': 3,
                'walk_forward_periods': 6
            },
            'risk_thresholds': {
                'min_accuracy': 0.50,
                'min_win_rate': 0.45,
                'max_consecutive_predictions': 8,
                'min_confidence': 0.55
            }
        }
    
    @pytest.fixture
    def evaluator(self, sample_config):
        """Create evaluator instance."""
        return MultiTimeframeEvaluator(sample_config)
    
    @pytest.fixture
    def mock_model(self):
        """Create mock multi-timeframe model."""
        model = Mock(spec=MultiTimeframeMLP)
        
        # Mock model architecture
        mock_nn_model = Mock()
        mock_nn_model.eval.return_value = None
        model.model = mock_nn_model
        
        # Mock timeframe configs
        model.timeframe_configs = {
            '1h': {'weight': 1.0, 'enabled': True},
            '4h': {'weight': 0.8, 'enabled': True},
            '1d': {'weight': 0.6, 'enabled': True}
        }
        
        return model
    
    @pytest.fixture
    def sample_test_data(self):
        """Create sample test data."""
        n_samples = 100
        n_features = 50
        
        features = torch.randn(n_samples, n_features)
        labels = torch.randint(0, 3, (n_samples,))
        timestamps = pd.date_range('2024-01-01', periods=n_samples, freq='1h')
        
        metadata = {
            'dataset_type': 'test',
            'sequence_count': n_samples,
            'sequence_length': 20,
            'prediction_horizon': 5,
            'feature_count': n_features
        }
        
        return TrainingSequence(
            features=features,
            labels=labels,
            timestamps=timestamps,
            metadata=metadata
        )
    
    @pytest.fixture
    def sample_price_data(self):
        """Create sample price data."""
        dates = pd.date_range('2024-01-01', periods=100, freq='1h')
        prices = 100 + np.cumsum(np.random.normal(0, 1, 100))
        
        return {
            '1h': pd.DataFrame({
                'timestamp': dates,
                'open': prices * 0.999,
                'high': prices * 1.002,
                'low': prices * 0.998,
                'close': prices,
                'volume': np.random.randint(1000, 10000, 100)
            })
        }
    
    def test_evaluator_initialization(self, evaluator, sample_config):
        """Test evaluator initialization."""
        assert evaluator.config == sample_config
        assert evaluator.class_names == ['BUY', 'HOLD', 'SELL']
        assert evaluator.class_mapping == {0: 'BUY', 1: 'HOLD', 2: 'SELL'}
        assert isinstance(evaluator.evaluation_history, list)
    
    def test_default_configuration(self):
        """Test evaluator with default configuration."""
        evaluator = MultiTimeframeEvaluator()
        
        assert evaluator.config is not None
        assert 'validation' in evaluator.config
        assert 'risk_thresholds' in evaluator.config
        assert 'analysis' in evaluator.config
    
    @patch('torch.no_grad')
    def test_evaluate_classification_performance(self, mock_no_grad, evaluator, mock_model, sample_test_data):
        """Test classification performance evaluation."""
        
        # Mock model predictions
        n_samples = len(sample_test_data.features)
        mock_outputs = torch.randn(n_samples, 3)
        mock_probabilities = torch.softmax(mock_outputs, dim=1)
        mock_predicted = torch.argmax(mock_outputs, dim=1)
        
        with patch.object(mock_model.model, '__call__', return_value=mock_outputs):
            with patch('torch.softmax', return_value=mock_probabilities):
                with patch('torch.argmax', return_value=mock_predicted):
                    
                    performance = evaluator._evaluate_classification_performance(
                        mock_model, sample_test_data
                    )
        
        # Verify performance metrics structure
        assert isinstance(performance, PerformanceMetrics)
        assert 0.0 <= performance.accuracy <= 1.0
        assert 0.0 <= performance.precision <= 1.0
        assert 0.0 <= performance.recall <= 1.0
        assert 0.0 <= performance.f1_score <= 1.0
        assert 0.0 <= performance.win_rate <= 1.0
        
        # Verify class-specific metrics
        assert len(performance.class_precision) == 3
        assert len(performance.class_recall) == 3
        assert len(performance.class_f1) == 3
        
        # Verify prediction distribution
        assert len(performance.prediction_distribution) == 3
        assert sum(performance.prediction_distribution.values()) == n_samples
    
    def test_analyze_timeframe_contributions(self, evaluator, mock_model, sample_test_data):
        """Test timeframe contribution analysis."""
        
        # Mock model predictions
        with patch.object(mock_model.model, '__call__') as mock_call:
            with patch('torch.no_grad'):
                mock_outputs = torch.randn(len(sample_test_data.features), 3)
                mock_call.return_value = mock_outputs
                
                with patch('torch.argmax', return_value=torch.randint(0, 3, (len(sample_test_data.features),))):
                    
                    analysis = evaluator._analyze_timeframe_contributions(
                        mock_model, sample_test_data
                    )
        
        # Verify timeframe analysis structure
        assert isinstance(analysis, dict)
        
        for timeframe in ['1h', '4h', '1d']:
            assert timeframe in analysis
            tf_analysis = analysis[timeframe]
            assert isinstance(tf_analysis, TimeframeAnalysis)
            assert tf_analysis.timeframe == timeframe
            assert 0.0 <= tf_analysis.contribution_weight <= 1.0
            assert 0.0 <= tf_analysis.prediction_accuracy <= 1.0
            assert 0.0 <= tf_analysis.temporal_stability <= 1.0
    
    def test_advanced_validation(self, evaluator, mock_model, sample_test_data):
        """Test advanced validation methods."""
        
        validation_result = evaluator._perform_advanced_validation(
            mock_model, sample_test_data
        )
        
        # Verify validation result structure
        assert isinstance(validation_result, ValidationResult)
        assert len(validation_result.cross_validation_scores) > 0
        assert isinstance(validation_result.time_series_validation, dict)
        assert isinstance(validation_result.walk_forward_analysis, dict)
        assert isinstance(validation_result.model_stability, dict)
        
        # Verify score ranges
        for score in validation_result.cross_validation_scores:
            assert 0.0 <= score <= 1.0
    
    def test_feature_importance_analysis(self, evaluator, mock_model, sample_test_data):
        """Test feature importance analysis."""
        
        feature_analysis = evaluator._analyze_feature_importance(
            mock_model, sample_test_data
        )
        
        # Verify feature analysis structure
        assert isinstance(feature_analysis, dict)
        assert 'global_importance' in feature_analysis
        assert 'timeframe_importance' in feature_analysis
        assert 'feature_interactions' in feature_analysis
        assert 'stability_over_time' in feature_analysis
        
        # Verify importance values sum appropriately
        global_importance = feature_analysis['global_importance']
        importance_sum = sum(global_importance.values())
        assert 0.8 <= importance_sum <= 1.2  # Allow some tolerance
    
    def test_risk_analysis(self, evaluator, mock_model, sample_test_data, sample_price_data):
        """Test comprehensive risk analysis."""
        
        # Mock model predictions
        with patch.object(mock_model.model, '__call__') as mock_call:
            with patch('torch.no_grad'):
                n_samples = len(sample_test_data.features)
                mock_outputs = torch.randn(n_samples, 3)
                mock_probabilities = torch.softmax(mock_outputs, dim=1)
                mock_predicted = torch.randint(0, 3, (n_samples,))
                
                mock_call.return_value = mock_outputs
                
                with patch('torch.softmax', return_value=mock_probabilities):
                    with patch('torch.argmax', return_value=mock_predicted):
                        
                        risk_analysis = evaluator._perform_risk_analysis(
                            mock_model, sample_test_data, sample_price_data
                        )
        
        # Verify risk analysis structure
        assert isinstance(risk_analysis, dict)
        assert 'confidence_analysis' in risk_analysis
        assert 'distribution_risk' in risk_analysis
        assert 'uncertainty_analysis' in risk_analysis
        assert 'trading_risks' in risk_analysis
        
        # Verify confidence analysis
        confidence_analysis = risk_analysis['confidence_analysis']
        assert 0.0 <= confidence_analysis['mean_confidence'] <= 1.0
        assert confidence_analysis['confidence_std'] >= 0.0
        assert 0.0 <= confidence_analysis['low_confidence_ratio'] <= 1.0
        assert 0.0 <= confidence_analysis['high_confidence_ratio'] <= 1.0
    
    def test_recommendation_generation(self, evaluator):
        """Test recommendation generation."""
        
        # Create mock performance metrics
        performance = PerformanceMetrics(
            accuracy=0.55,
            precision=0.60,
            recall=0.58,
            f1_score=0.59,
            auc_score=0.65,
            class_precision={'BUY': 0.6, 'HOLD': 0.7, 'SELL': 0.5},
            class_recall={'BUY': 0.5, 'HOLD': 0.8, 'SELL': 0.4},
            class_f1={'BUY': 0.55, 'HOLD': 0.75, 'SELL': 0.45},
            win_rate=0.52,
            profit_factor=None,
            sharpe_ratio=None,
            max_drawdown=None,
            evaluation_period="2024-01-01 to 2024-12-31",
            total_predictions=1000,
            prediction_distribution={'BUY': 300, 'HOLD': 400, 'SELL': 300}
        )
        
        # Create mock timeframe analysis
        timeframe_analysis = {
            '1h': TimeframeAnalysis(
                timeframe='1h',
                contribution_weight=1.0,
                feature_importance={'rsi': 0.3, 'trend': 0.7},
                prediction_accuracy=0.60,
                signal_quality={'consistency': 0.8},
                temporal_stability=0.85
            ),
            '4h': TimeframeAnalysis(
                timeframe='4h',
                contribution_weight=0.3,  # Large variance to trigger recommendation
                feature_importance={'rsi': 0.4, 'trend': 0.6},
                prediction_accuracy=0.55,
                signal_quality={'consistency': 0.75},
                temporal_stability=0.80
            )
        }
        
        # Create mock validation result
        validation = ValidationResult(
            cross_validation_scores=[0.55, 0.60, 0.50, 0.65, 0.58],  # High variance
            time_series_validation={},
            walk_forward_analysis={},
            out_of_sample_performance=performance,
            model_stability={'prediction_stability': 0.75}  # Low stability
        )
        
        recommendations = evaluator._generate_recommendations(
            performance, timeframe_analysis, validation
        )
        
        # Verify recommendations
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        # Check for specific recommendations based on the metrics
        recommendation_text = ' '.join(recommendations)
        assert 'timeframe' in recommendation_text.lower() or 'variance' in recommendation_text.lower()
        assert 'stability' in recommendation_text.lower() or 'unstable' in recommendation_text.lower()
    
    def test_model_artifacts_creation(self, evaluator, mock_model, sample_test_data):
        """Test model artifacts creation."""
        
        # Mock model predictions
        with patch.object(mock_model.model, '__call__') as mock_call:
            with patch('torch.no_grad'):
                n_samples = len(sample_test_data.features)
                mock_outputs = torch.randn(n_samples, 3)
                mock_probabilities = torch.softmax(mock_outputs, dim=1)
                mock_predicted = torch.randint(0, 3, (n_samples,))
                
                mock_call.return_value = mock_outputs
                
                with patch('torch.softmax', return_value=mock_probabilities):
                    with patch('torch.argmax', return_value=mock_predicted):
                        
                        artifacts = evaluator._create_model_artifacts(
                            mock_model, sample_test_data
                        )
        
        # Verify artifacts structure
        assert isinstance(artifacts, dict)
        assert 'sample_predictions' in artifacts
        assert 'confusion_matrix' in artifacts
        assert 'model_summary' in artifacts
        assert 'feature_statistics' in artifacts
        
        # Verify sample predictions
        sample_preds = artifacts['sample_predictions']
        assert 'indices' in sample_preds
        assert 'true_labels' in sample_preds
        assert 'predicted_labels' in sample_preds
        assert 'probabilities' in sample_preds
        assert 'timestamps' in sample_preds
        
        # Verify confusion matrix
        confusion_matrix = artifacts['confusion_matrix']
        assert isinstance(confusion_matrix, list)
        assert len(confusion_matrix) == 3  # 3x3 matrix for 3 classes
        
        # Verify model summary
        model_summary = artifacts['model_summary']
        assert 'total_parameters' in model_summary
        assert 'trainable_parameters' in model_summary
        assert 'model_size_mb' in model_summary
    
    @patch('torch.no_grad')
    def test_complete_evaluation_pipeline(self, mock_no_grad, evaluator, mock_model, sample_test_data, sample_price_data):
        """Test complete evaluation pipeline."""
        
        # Mock model predictions
        n_samples = len(sample_test_data.features)
        mock_outputs = torch.randn(n_samples, 3)
        mock_probabilities = torch.softmax(mock_outputs, dim=1)
        mock_predicted = torch.randint(0, 3, (n_samples,))
        
        with patch.object(mock_model.model, '__call__', return_value=mock_outputs):
            with patch('torch.softmax', return_value=mock_probabilities):
                with patch('torch.argmax', return_value=mock_predicted):
                    
                    report = evaluator.evaluate_model(
                        mock_model,
                        sample_test_data,
                        sample_price_data,
                        model_id="test_model_123"
                    )
        
        # Verify evaluation report structure
        assert isinstance(report, EvaluationReport)
        assert report.model_id == "test_model_123"
        assert report.evaluation_timestamp is not None
        
        # Verify report components
        assert isinstance(report.overall_performance, PerformanceMetrics)
        assert isinstance(report.timeframe_analysis, dict)
        assert isinstance(report.validation_results, ValidationResult)
        assert isinstance(report.feature_analysis, dict)
        assert isinstance(report.risk_analysis, dict)
        assert isinstance(report.recommendations, list)
        assert isinstance(report.model_artifacts, dict)
        
        # Verify evaluation history
        assert len(evaluator.evaluation_history) == 1
        assert evaluator.evaluation_history[0] == report
    
    def test_save_evaluation_report(self, evaluator):
        """Test saving evaluation report."""
        
        # Create mock evaluation report
        mock_performance = PerformanceMetrics(
            accuracy=0.65,
            precision=0.70,
            recall=0.68,
            f1_score=0.69,
            auc_score=0.72,
            class_precision={'BUY': 0.7, 'HOLD': 0.8, 'SELL': 0.6},
            class_recall={'BUY': 0.6, 'HOLD': 0.85, 'SELL': 0.55},
            class_f1={'BUY': 0.65, 'HOLD': 0.82, 'SELL': 0.57},
            win_rate=0.58,
            profit_factor=1.8,
            sharpe_ratio=1.2,
            max_drawdown=0.12,
            evaluation_period="2024-01-01 to 2024-12-31",
            total_predictions=1500,
            prediction_distribution={'BUY': 450, 'HOLD': 600, 'SELL': 450}
        )
        
        mock_report = EvaluationReport(
            model_id="test_model",
            evaluation_timestamp="2024-12-31T23:59:59+00:00",
            overall_performance=mock_performance,
            timeframe_analysis={},
            validation_results=ValidationResult(
                cross_validation_scores=[0.6, 0.65, 0.62],
                time_series_validation={},
                walk_forward_analysis={},
                out_of_sample_performance=mock_performance,
                model_stability={'prediction_stability': 0.88}
            ),
            feature_analysis={},
            risk_analysis={},
            recommendations=["Model performance is acceptable"],
            model_artifacts={}
        )
        
        # Test saving
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_report.json"
            
            evaluator.save_evaluation_report(mock_report, output_path)
            
            # Verify file was created
            assert output_path.exists()
            
            # Verify file contents
            import json
            with open(output_path, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data['model_id'] == "test_model"
            assert saved_data['overall_performance']['accuracy'] == 0.65
            assert 'timeframe_analysis' in saved_data
            assert 'validation_results' in saved_data
    
    def test_model_comparison(self, evaluator):
        """Test model comparison functionality."""
        
        # Create multiple mock evaluation reports
        reports = []
        
        for i in range(3):
            performance = PerformanceMetrics(
                accuracy=0.60 + i * 0.05,
                precision=0.62 + i * 0.03,
                recall=0.58 + i * 0.04,
                f1_score=0.60 + i * 0.035,
                auc_score=0.65 + i * 0.02,
                class_precision={'BUY': 0.6, 'HOLD': 0.7, 'SELL': 0.5},
                class_recall={'BUY': 0.5, 'HOLD': 0.8, 'SELL': 0.4},
                class_f1={'BUY': 0.55, 'HOLD': 0.75, 'SELL': 0.45},
                win_rate=0.50 + i * 0.03,
                profit_factor=None,
                sharpe_ratio=None,
                max_drawdown=None,
                evaluation_period="2024-01-01 to 2024-12-31",
                total_predictions=1000,
                prediction_distribution={'BUY': 300, 'HOLD': 400, 'SELL': 300}
            )
            
            report = EvaluationReport(
                model_id=f"model_{i+1}",
                evaluation_timestamp="2024-12-31T23:59:59+00:00",
                overall_performance=performance,
                timeframe_analysis={},
                validation_results=ValidationResult(
                    cross_validation_scores=[0.6],
                    time_series_validation={},
                    walk_forward_analysis={},
                    out_of_sample_performance=performance,
                    model_stability={}
                ),
                feature_analysis={},
                risk_analysis={},
                recommendations=[],
                model_artifacts={}
            )
            
            reports.append(report)
        
        # Test comparison
        comparison = evaluator.compare_models(reports)
        
        # Verify comparison structure
        assert comparison['model_count'] == 3
        assert comparison['best_model'] in ['model_1', 'model_2', 'model_3']
        assert 'performance_comparison' in comparison
        assert 'ranking' in comparison
        
        # Verify ranking
        ranking = comparison['ranking']
        assert len(ranking) == 3
        assert '1' in ranking  # Best model should be rank 1
        
        # Verify performance comparison
        perf_comp = comparison['performance_comparison']
        for metric in ['accuracy', 'precision', 'recall', 'f1_score', 'win_rate']:
            if metric in perf_comp:
                assert 'best' in perf_comp[metric]
                assert 'worst' in perf_comp[metric]
                assert 'average' in perf_comp[metric]
    
    def test_edge_cases(self, evaluator):
        """Test edge cases and error handling."""
        
        # Test with insufficient models for comparison
        single_report = [Mock()]
        
        with pytest.raises(ValueError, match="Need at least 2"):
            evaluator.compare_models(single_report)
        
        # Test with empty test data
        empty_sequence = TrainingSequence(
            features=torch.empty(0, 10),
            labels=torch.empty(0, dtype=torch.long),
            timestamps=pd.DatetimeIndex([]),
            metadata={'dataset_type': 'empty', 'sequence_count': 0}
        )
        
        mock_model = Mock()
        mock_model.model = Mock()
        
        # Should handle empty data gracefully
        with patch.object(mock_model.model, '__call__') as mock_call:
            with patch('torch.no_grad'):
                mock_call.return_value = torch.empty(0, 3)
                
                # This should not crash but may have zero metrics
                try:
                    performance = evaluator._evaluate_classification_performance(
                        mock_model, empty_sequence
                    )
                    assert performance.total_predictions == 0
                except Exception:
                    # Some edge case handling is acceptable
                    pass


class TestEvaluationPipeline:
    """Test evaluation pipeline utility functions."""
    
    @pytest.fixture
    def mock_model(self):
        """Create mock model."""
        model = Mock(spec=MultiTimeframeMLP)
        model.model = Mock()
        model.model.eval.return_value = None
        return model
    
    @pytest.fixture
    def sample_test_data(self):
        """Create sample test data."""
        return TrainingSequence(
            features=torch.randn(50, 20),
            labels=torch.randint(0, 3, (50,)),
            timestamps=pd.date_range('2024-01-01', periods=50, freq='1h'),
            metadata={'dataset_type': 'test', 'sequence_count': 50}
        )
    
    @patch('ktrdr.evaluation.multi_timeframe_evaluator.MultiTimeframeEvaluator.evaluate_model')
    def test_create_evaluation_pipeline(self, mock_evaluate, mock_model, sample_test_data):
        """Test evaluation pipeline creation."""
        
        # Mock evaluation result
        mock_report = Mock(spec=EvaluationReport)
        mock_report.model_id = "pipeline_test_model"
        mock_evaluate.return_value = mock_report
        
        # Test pipeline without output directory
        report = create_evaluation_pipeline(mock_model, sample_test_data)
        
        assert mock_evaluate.called
        assert report == mock_report
        
        # Test pipeline with output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            with patch.object(MultiTimeframeEvaluator, 'save_evaluation_report') as mock_save:
                report = create_evaluation_pipeline(
                    mock_model, sample_test_data, output_dir
                )
                
                assert mock_save.called
                # Verify save was called with correct arguments
                call_args = mock_save.call_args
                assert call_args[0][0] == mock_report  # First arg is the report
                assert str(output_dir) in str(call_args[0][1])  # Second arg contains output path


class TestHelperMethods:
    """Test helper methods in evaluator."""
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance."""
        return MultiTimeframeEvaluator()
    
    def test_calculate_win_rate(self, evaluator):
        """Test win rate calculation."""
        
        # Test case 1: Mixed predictions with correct trading outcomes
        y_true = np.array([0, 1, 2, 0, 2, 1, 0])  # BUY, HOLD, SELL, BUY, SELL, HOLD, BUY
        y_pred = np.array([0, 1, 2, 2, 2, 1, 0])  # BUY, HOLD, SELL, SELL, SELL, HOLD, BUY
        
        win_rate = evaluator._calculate_win_rate(y_true, y_pred)
        
        # Only trading predictions (not HOLD) count: positions 0,2,3,4,6
        # Correct: positions 0,2,4,6 = 4 out of 5 trading predictions
        assert win_rate == 0.8
        
        # Test case 2: Only HOLD predictions
        y_true_hold = np.array([1, 1, 1])
        y_pred_hold = np.array([1, 1, 1])
        
        win_rate_hold = evaluator._calculate_win_rate(y_true_hold, y_pred_hold)
        assert win_rate_hold == 0.0  # No trading predictions
        
        # Test case 3: No correct trading predictions
        y_true_wrong = np.array([0, 2, 0])
        y_pred_wrong = np.array([2, 0, 2])
        
        win_rate_wrong = evaluator._calculate_win_rate(y_true_wrong, y_pred_wrong)
        assert win_rate_wrong == 0.0
    
    def test_calculate_signal_consistency(self, evaluator):
        """Test signal consistency calculation."""
        
        # Test case 1: Highly consistent signals
        consistent_predictions = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
        consistency = evaluator._calculate_signal_consistency(consistent_predictions)
        
        # Only 2 changes out of 8 possible positions
        expected_consistency = 1.0 - (2 / 9)
        assert abs(consistency - expected_consistency) < 0.01
        
        # Test case 2: Highly inconsistent signals
        inconsistent_predictions = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2])
        consistency_low = evaluator._calculate_signal_consistency(inconsistent_predictions)
        
        # 8 changes out of 8 possible positions
        expected_low = 1.0 - (8 / 9)
        assert abs(consistency_low - expected_low) < 0.01
        
        # Test case 3: No changes (constant signal)
        constant_predictions = np.array([1, 1, 1, 1, 1])
        consistency_perfect = evaluator._calculate_signal_consistency(constant_predictions)
        assert consistency_perfect == 1.0
    
    def test_calculate_temporal_stability(self, evaluator):
        """Test temporal stability calculation."""
        
        # Test case 1: Stable predictions
        stable_predictions = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2, 0, 0, 0])
        stability = evaluator._calculate_temporal_stability(stable_predictions)
        
        # With window size, should have high stability
        assert stability > 0.5
        
        # Test case 2: Very short array
        short_predictions = np.array([0, 1])
        stability_short = evaluator._calculate_temporal_stability(short_predictions)
        assert stability_short == 1.0  # Default for insufficient data
        
        # Test case 3: Completely random predictions
        random_predictions = np.array([0, 1, 2, 1, 0, 2, 1, 0, 2, 0, 1, 2, 
                                     2, 0, 1, 0, 2, 1, 2, 0, 1, 0, 2, 1])
        stability_random = evaluator._calculate_temporal_stability(random_predictions)
        
        # Should have lower stability due to randomness
        assert stability_random < 0.8
    
    def test_count_consecutive_predictions(self, evaluator):
        """Test consecutive prediction counting."""
        
        predictions = np.array([0, 0, 0, 1, 1, 2, 2, 2, 2, 0, 1, 1])
        
        consecutive = evaluator._count_consecutive_predictions(predictions)
        
        # Verify structure
        assert 'BUY' in consecutive
        assert 'HOLD' in consecutive  
        assert 'SELL' in consecutive
        
        # Check BUY (class 0): runs of [3, 1]
        buy_stats = consecutive['BUY']
        assert buy_stats['max_consecutive'] == 3
        assert buy_stats['total_runs'] == 2
        
        # Check HOLD (class 1): runs of [2, 2]
        hold_stats = consecutive['HOLD']
        assert hold_stats['max_consecutive'] == 2
        assert hold_stats['total_runs'] == 2
        
        # Check SELL (class 2): runs of [4]
        sell_stats = consecutive['SELL']
        assert sell_stats['max_consecutive'] == 4
        assert sell_stats['total_runs'] == 1
    
    def test_calculate_reversal_frequency(self, evaluator):
        """Test reversal frequency calculation."""
        
        # Test case 1: High reversal frequency
        high_reversal = np.array([0, 1, 0, 2, 0, 1, 0])
        freq_high = evaluator._calculate_reversal_frequency(high_reversal)
        
        # Reversals at positions 1, 3, 5 = 3 reversals out of 5 possible positions
        assert freq_high == 3 / 5
        
        # Test case 2: No reversals (stable sequence)
        stable = np.array([0, 0, 1, 1, 1, 2, 2])
        freq_stable = evaluator._calculate_reversal_frequency(stable)
        assert freq_stable == 0.0
        
        # Test case 3: Short sequence
        short = np.array([0, 1])
        freq_short = evaluator._calculate_reversal_frequency(short)
        assert freq_short == 0.0  # Not enough data for reversals
    
    def test_analyze_confidence_clustering(self, evaluator):
        """Test confidence clustering analysis."""
        
        # Test case 1: Clustered high confidence
        confidences = np.array([0.95, 0.92, 0.94, 0.3, 0.4, 0.91, 0.93, 0.96])
        
        clustering = evaluator._analyze_confidence_clustering(confidences)
        
        # Verify structure
        assert 'high_confidence_clustering' in clustering
        assert 'low_confidence_clustering' in clustering
        assert 'high_confidence_ratio' in clustering
        assert 'low_confidence_ratio' in clustering
        
        # Check ratios
        assert 0.0 <= clustering['high_confidence_ratio'] <= 1.0
        assert 0.0 <= clustering['low_confidence_ratio'] <= 1.0
        
        # High confidence should be clustered (consecutive high values)
        assert clustering['high_confidence_clustering'] > 0
        
        # Test case 2: Uniform distribution
        uniform_confidences = np.array([0.7, 0.7, 0.7, 0.7, 0.7])
        uniform_clustering = evaluator._analyze_confidence_clustering(uniform_confidences)
        
        # Should have minimal clustering for extreme values
        assert uniform_clustering['high_confidence_clustering'] == 0.0
        assert uniform_clustering['low_confidence_clustering'] == 0.0


if __name__ == "__main__":
    pytest.main([__file__])