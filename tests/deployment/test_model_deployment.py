"""Tests for multi-timeframe model deployment system."""

import pytest
import torch
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json
import threading
import time

from ktrdr.deployment.model_deployment import (
    MultiTimeframeModelDeployer,
    ModelOrchestrator,
    DeploymentConfig,
    PredictionRequest,
    PredictionResponse,
    ModelHealthStatus,
    ModelStatus,
    PredictionConfidence,
    PredictionCache,
    PerformanceMonitor,
    CircuitBreaker,
    create_deployment_config,
    deploy_model_for_production
)


class TestDeploymentConfig:
    """Test deployment configuration."""
    
    def test_deployment_config_creation(self):
        """Test deployment configuration creation."""
        model_path = Path("/tmp/test_model.pth")
        
        config = DeploymentConfig(
            model_path=model_path,
            model_id="test_model",
            version="1.0.0",
            max_batch_size=16,
            prediction_timeout=2.0,
            enable_monitoring=True
        )
        
        assert config.model_path == model_path
        assert config.model_id == "test_model"
        assert config.version == "1.0.0"
        assert config.max_batch_size == 16
        assert config.prediction_timeout == 2.0
        assert config.enable_monitoring is True
    
    def test_create_deployment_config_utility(self):
        """Test deployment config utility function."""
        model_path = Path("/tmp/model.pth")
        
        config = create_deployment_config(
            model_path=model_path,
            model_id="utility_test",
            prediction_timeout=1.5,
            enable_caching=False
        )
        
        assert isinstance(config, DeploymentConfig)
        assert config.model_path == model_path
        assert config.model_id == "utility_test"
        assert config.prediction_timeout == 1.5
        assert config.enable_prediction_cache is False


class TestPredictionCache:
    """Test prediction caching system."""
    
    @pytest.fixture
    def cache(self):
        """Create prediction cache."""
        return PredictionCache(max_size=5, ttl_seconds=1)
    
    @pytest.fixture
    def sample_features(self):
        """Create sample features."""
        return {
            'rsi_14': 0.65,
            'sma_20': 100.5,
            'trend_strength': 0.8
        }
    
    @pytest.fixture
    def sample_prediction(self):
        """Create sample prediction response."""
        return PredictionResponse(
            request_id="test_123",
            prediction=0,
            confidence=0.85,
            confidence_level=PredictionConfidence.HIGH,
            probabilities={'BUY': 0.85, 'HOLD': 0.10, 'SELL': 0.05},
            processing_time_ms=25.0,
            model_version="1.0.0",
            timestamp=pd.Timestamp.now(tz='UTC')
        )
    
    def test_cache_put_and_get(self, cache, sample_features, sample_prediction):
        """Test cache put and get operations."""
        # Initially empty
        result = cache.get(sample_features)
        assert result is None
        
        # Put prediction
        cache.put(sample_features, sample_prediction)
        
        # Should retrieve cached prediction
        result = cache.get(sample_features)
        assert result is not None
        assert result.prediction == sample_prediction.prediction
        assert result.confidence == sample_prediction.confidence
    
    def test_cache_ttl_expiration(self, cache, sample_features, sample_prediction):
        """Test cache TTL expiration."""
        cache.put(sample_features, sample_prediction)
        
        # Should be available immediately
        result = cache.get(sample_features)
        assert result is not None
        
        # Wait for TTL expiration
        time.sleep(1.1)
        
        # Should be expired
        result = cache.get(sample_features)
        assert result is None
    
    def test_cache_size_limit(self, cache, sample_prediction):
        """Test cache size limitation."""
        # Fill cache beyond capacity
        for i in range(10):
            features = {'feature': i}
            cache.put(features, sample_prediction)
        
        # Should not exceed max size
        assert len(cache.cache) <= cache.max_size
    
    def test_cache_key_generation(self, cache):
        """Test cache key generation."""
        features1 = {'rsi': 0.5, 'sma': 100.0}
        features2 = {'sma': 100.0, 'rsi': 0.5}  # Different order
        features3 = {'rsi': 0.6, 'sma': 100.0}  # Different values
        
        key1 = cache._generate_key(features1)
        key2 = cache._generate_key(features2)
        key3 = cache._generate_key(features3)
        
        # Same features, different order should produce same key
        assert key1 == key2
        
        # Different values should produce different key
        assert key1 != key3
    
    def test_cache_thread_safety(self, cache, sample_prediction):
        """Test cache thread safety."""
        results = []
        
        def cache_worker(worker_id):
            for i in range(10):
                features = {'worker': worker_id, 'iteration': i}
                cache.put(features, sample_prediction)
                result = cache.get(features)
                results.append(result is not None)
        
        # Run multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=cache_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should not crash and should have some successful operations
        assert len(results) > 0
        assert any(results)


class TestPerformanceMonitor:
    """Test performance monitoring system."""
    
    @pytest.fixture
    def monitor(self):
        """Create performance monitor."""
        return PerformanceMonitor(window_size=10)
    
    @pytest.fixture
    def sample_prediction(self):
        """Create sample prediction."""
        return PredictionResponse(
            request_id="monitor_test",
            prediction=1,
            confidence=0.75,
            confidence_level=PredictionConfidence.MEDIUM,
            probabilities={'BUY': 0.20, 'HOLD': 0.75, 'SELL': 0.05},
            processing_time_ms=30.0,
            model_version="1.0.0",
            timestamp=pd.Timestamp.now(tz='UTC')
        )
    
    def test_record_prediction(self, monitor, sample_prediction):
        """Test prediction recording."""
        monitor.record_prediction(sample_prediction, 30.0)
        
        assert len(monitor.predictions) == 1
        assert len(monitor.response_times) == 1
        assert len(monitor.errors) == 0
        
        # Verify recorded data
        assert monitor.predictions[0]['confidence'] == 0.75
        assert monitor.predictions[0]['prediction'] == 1
        assert monitor.response_times[0] == 30.0
    
    def test_record_prediction_with_error(self, monitor, sample_prediction):
        """Test prediction recording with error."""
        error = ValueError("Test error")
        
        monitor.record_prediction(sample_prediction, 50.0, error)
        
        assert len(monitor.predictions) == 1
        assert len(monitor.response_times) == 1
        assert len(monitor.errors) == 1
        
        # Verify error recorded
        error_record = monitor.errors[0]
        assert error_record['error'] == "Test error"
        assert error_record['type'] == "ValueError"
    
    def test_performance_stats(self, monitor, sample_prediction):
        """Test performance statistics calculation."""
        # Record multiple predictions
        for i in range(5):
            prediction = sample_prediction
            prediction.prediction = i % 3  # Vary predictions
            prediction.confidence = 0.6 + (i * 0.05)  # Vary confidence
            
            monitor.record_prediction(prediction, 20.0 + i * 5)
        
        stats = monitor.get_performance_stats()
        
        # Verify stats structure
        assert 'total_predictions' in stats
        assert 'avg_response_time_ms' in stats
        assert 'p95_response_time_ms' in stats
        assert 'error_count' in stats
        assert 'error_rate' in stats
        assert 'avg_confidence' in stats
        assert 'prediction_distribution' in stats
        
        # Verify values
        assert stats['total_predictions'] == 5
        assert stats['error_count'] == 0
        assert stats['error_rate'] == 0.0
        assert 0.6 <= stats['avg_confidence'] <= 0.8
    
    def test_window_size_maintenance(self, monitor, sample_prediction):
        """Test window size maintenance."""
        # Record more predictions than window size
        for i in range(15):
            monitor.record_prediction(sample_prediction, 20.0)
        
        # Should maintain window size
        assert len(monitor.predictions) == monitor.window_size
        assert len(monitor.response_times) == monitor.window_size
    
    def test_prediction_distribution(self, monitor, sample_prediction):
        """Test prediction distribution calculation."""
        # Record predictions with known distribution
        predictions = [0, 0, 1, 1, 1, 2]  # 2 BUY, 3 HOLD, 1 SELL
        
        for pred in predictions:
            prediction = sample_prediction
            prediction.prediction = pred
            monitor.record_prediction(prediction, 20.0)
        
        stats = monitor.get_performance_stats()
        distribution = stats['prediction_distribution']
        
        assert abs(distribution['BUY'] - 2/6) < 0.01
        assert abs(distribution['HOLD'] - 3/6) < 0.01
        assert abs(distribution['SELL'] - 1/6) < 0.01


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker."""
        return CircuitBreaker(failure_threshold=3, timeout_seconds=1)
    
    def test_circuit_breaker_closed_state(self, circuit_breaker):
        """Test circuit breaker in closed state."""
        def successful_function():
            return "success"
        
        # Should execute successfully
        result = circuit_breaker.call(successful_function)
        assert result == "success"
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failure_count == 0
    
    def test_circuit_breaker_failure_counting(self, circuit_breaker):
        """Test failure counting."""
        def failing_function():
            raise ValueError("Test failure")
        
        # First two failures should still allow calls
        for i in range(2):
            with pytest.raises(ValueError):
                circuit_breaker.call(failing_function)
            assert circuit_breaker.state == "CLOSED"
            assert circuit_breaker.failure_count == i + 1
        
        # Third failure should open circuit
        with pytest.raises(ValueError):
            circuit_breaker.call(failing_function)
        assert circuit_breaker.state == "OPEN"
        assert circuit_breaker.failure_count == 3
    
    def test_circuit_breaker_open_state(self, circuit_breaker):
        """Test circuit breaker in open state."""
        def failing_function():
            raise ValueError("Test failure")
        
        # Trigger circuit opening
        for _ in range(3):
            with pytest.raises(ValueError):
                circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == "OPEN"
        
        # Should reject calls while open
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            circuit_breaker.call(failing_function)
    
    def test_circuit_breaker_half_open_transition(self, circuit_breaker):
        """Test transition to half-open state."""
        def failing_function():
            raise ValueError("Test failure")
        
        def successful_function():
            return "success"
        
        # Open circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                circuit_breaker.call(failing_function)
        
        # Wait for timeout
        time.sleep(1.1)
        
        # Next call should transition to half-open
        result = circuit_breaker.call(successful_function)
        assert result == "success"
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failure_count == 0


class TestMultiTimeframeModelDeployer:
    """Test model deployment system."""
    
    @pytest.fixture
    def sample_config(self):
        """Create sample deployment config."""
        return DeploymentConfig(
            model_path=Path("/tmp/test_model.pth"),
            model_id="test_deployer",
            version="1.0.0",
            enable_prediction_cache=True,
            enable_monitoring=True,
            enable_circuit_breaker=True
        )
    
    @pytest.fixture
    def deployer(self, sample_config):
        """Create model deployer."""
        deployer = MultiTimeframeModelDeployer(sample_config)
        # Mock successful model loading
        deployer.status = ModelStatus.READY
        deployer.model = Mock()
        deployer.model.model = Mock()
        deployer.model_metadata = {
            'input_size': 50,
            'feature_order': ['rsi_14', 'sma_20', 'trend'],
            'feature_scaler': None
        }
        return deployer
    
    @pytest.fixture
    def sample_request(self):
        """Create sample prediction request."""
        return PredictionRequest(
            request_id="test_request_123",
            timestamp=pd.Timestamp.now(tz='UTC'),
            features={
                'rsi_14': 0.65,
                'sma_20': 100.5,
                'trend': 0.8
            },
            timeframes=['1h', '4h']
        )
    
    def test_deployer_initialization(self, deployer, sample_config):
        """Test deployer initialization."""
        assert deployer.config == sample_config
        assert deployer.cache is not None
        assert deployer.monitor is not None
        assert deployer.circuit_breaker is not None
        assert deployer.total_predictions == 0
        assert deployer.total_errors == 0
    
    @patch('torch.load')
    def test_load_model_success(self, mock_torch_load, sample_config):
        """Test successful model loading."""
        # Mock model checkpoint
        mock_checkpoint = {
            'model_state_dict': {'layer.weight': torch.randn(10, 50)},
            'model_config': {'hidden_layers': [64, 32]},
            'feature_order': ['rsi_14', 'sma_20'],
            'feature_scaler': None
        }
        mock_torch_load.return_value = mock_checkpoint
        
        deployer = MultiTimeframeModelDeployer(sample_config)
        
        with patch('ktrdr.neural.models.multi_timeframe_mlp.MultiTimeframeMLP') as mock_mlp:
            mock_model = Mock()
            mock_model.build_model = Mock()
            mock_model.model = Mock()
            mock_mlp.return_value = mock_model
            
            deployer.load_model()
            
            assert deployer.status == ModelStatus.READY
            assert deployer.model == mock_model
            assert 'input_size' in deployer.model_metadata
            assert 'feature_order' in deployer.model_metadata
    
    @patch('torch.load')
    def test_load_model_failure(self, mock_torch_load, sample_config):
        """Test model loading failure."""
        mock_torch_load.side_effect = FileNotFoundError("Model file not found")
        
        deployer = MultiTimeframeModelDeployer(sample_config)
        
        with pytest.raises(FileNotFoundError):
            deployer.load_model()
        
        assert deployer.status == ModelStatus.ERROR
    
    def test_prepare_features(self, deployer):
        """Test feature preparation."""
        features = {
            'rsi_14': 0.65,
            'sma_20': 100.5,
            'trend': 0.8,
            'extra_feature': 999.0  # Should be ignored if not in feature_order
        }
        
        features_tensor = deployer._prepare_features(features)
        
        assert isinstance(features_tensor, torch.Tensor)
        assert features_tensor.shape == (1, 3)  # 1 sample, 3 features
        
        # Should follow feature_order
        expected_values = [0.65, 100.5, 0.8]
        actual_values = features_tensor[0].tolist()
        
        for expected, actual in zip(expected_values, actual_values):
            assert abs(expected - actual) < 0.001
    
    def test_prepare_features_missing_values(self, deployer):
        """Test feature preparation with missing values."""
        features = {
            'rsi_14': 0.65,
            # 'sma_20' missing
            'trend': 0.8
        }
        
        features_tensor = deployer._prepare_features(features)
        
        assert isinstance(features_tensor, torch.Tensor)
        assert features_tensor.shape == (1, 3)
        
        # Missing value should be filled with 0.0
        values = features_tensor[0].tolist()
        assert values[0] == 0.65  # rsi_14
        assert values[1] == 0.0   # sma_20 (missing)
        assert values[2] == 0.8   # trend
    
    def test_get_confidence_level(self, deployer):
        """Test confidence level classification."""
        assert deployer._get_confidence_level(0.95) == PredictionConfidence.VERY_HIGH
        assert deployer._get_confidence_level(0.85) == PredictionConfidence.HIGH
        assert deployer._get_confidence_level(0.70) == PredictionConfidence.MEDIUM
        assert deployer._get_confidence_level(0.50) == PredictionConfidence.LOW
        assert deployer._get_confidence_level(0.30) == PredictionConfidence.VERY_LOW
    
    @patch('torch.no_grad')
    def test_make_prediction_success(self, mock_no_grad, deployer, sample_request):
        """Test successful prediction."""
        # Mock model outputs
        mock_outputs = torch.tensor([[2.0, 1.0, 0.5]])
        mock_probabilities = torch.tensor([[0.8, 0.15, 0.05]])
        mock_predicted_class = torch.tensor([0])
        mock_max_confidence = torch.tensor(0.8)
        
        deployer.model.model.return_value = mock_outputs
        
        with patch('torch.softmax', return_value=mock_probabilities):
            with patch('torch.argmax', return_value=mock_predicted_class):
                with patch('torch.max', return_value=mock_max_confidence):
                    
                    response = deployer.predict(sample_request)
        
        # Verify response
        assert isinstance(response, PredictionResponse)
        assert response.request_id == sample_request.request_id
        assert response.prediction == 0  # BUY
        assert response.confidence == 0.8
        assert response.confidence_level == PredictionConfidence.HIGH
        assert response.model_version == deployer.config.version
        assert 'BUY' in response.probabilities
        assert 'HOLD' in response.probabilities
        assert 'SELL' in response.probabilities
    
    @patch('torch.no_grad')
    def test_make_prediction_low_confidence(self, mock_no_grad, deployer, sample_request):
        """Test prediction with low confidence warning."""
        # Set low confidence threshold
        deployer.config.min_confidence_threshold = 0.7
        
        # Mock low confidence outputs
        mock_outputs = torch.tensor([[1.2, 1.1, 1.0]])
        mock_probabilities = torch.tensor([[0.5, 0.3, 0.2]])  # Below threshold
        mock_predicted_class = torch.tensor([0])
        mock_max_confidence = torch.tensor(0.5)
        
        deployer.model.model.return_value = mock_outputs
        
        with patch('torch.softmax', return_value=mock_probabilities):
            with patch('torch.argmax', return_value=mock_predicted_class):
                with patch('torch.max', return_value=mock_max_confidence):
                    
                    response = deployer.predict(sample_request)
        
        # Should have warning about low confidence
        assert response.warnings is not None
        assert any('Low confidence' in warning for warning in response.warnings)
    
    def test_predict_model_not_ready(self, deployer, sample_request):
        """Test prediction when model is not ready."""
        deployer.status = ModelStatus.LOADING
        
        with pytest.raises(RuntimeError, match="Model not ready"):
            deployer.predict(sample_request)
    
    def test_get_health_status(self, deployer):
        """Test health status reporting."""
        # Set some test values
        deployer.total_predictions = 100
        deployer.total_errors = 5
        deployer.last_prediction_time = pd.Timestamp.now(tz='UTC')
        
        health = deployer.get_health_status()
        
        assert isinstance(health, ModelHealthStatus)
        assert health.model_id == deployer.config.model_id
        assert health.status == deployer.status
        assert health.uptime_seconds > 0
        assert health.total_predictions == 100
        assert health.error_rate == 0.05
        assert health.last_prediction_time is not None
        assert isinstance(health.warnings, list)
    
    def test_update_config(self, deployer):
        """Test configuration updates."""
        new_config = {
            'prediction_timeout': 2.0,
            'min_confidence_threshold': 0.8,
            'cache_size': 2000
        }
        
        deployer.update_config(new_config)
        
        assert deployer.config.prediction_timeout == 2.0
        assert deployer.config.min_confidence_threshold == 0.8
        assert deployer.config.cache_size == 2000
    
    def test_shutdown(self, deployer):
        """Test graceful shutdown."""
        deployer.shutdown()
        
        assert deployer.status == ModelStatus.MAINTENANCE
        assert deployer.model is None
        assert len(deployer.model_metadata) == 0


class TestModelOrchestrator:
    """Test model orchestration system."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create model orchestrator."""
        return ModelOrchestrator()
    
    @pytest.fixture
    def mock_deployer(self):
        """Create mock deployer."""
        deployer = Mock()
        deployer.load_model = Mock()
        deployer.predict = Mock()
        deployer.get_health_status = Mock()
        return deployer
    
    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initialization."""
        assert len(orchestrator.deployers) == 0
        assert orchestrator.primary_model is None
    
    @patch('ktrdr.deployment.model_deployment.MultiTimeframeModelDeployer')
    def test_register_model(self, mock_deployer_class, orchestrator):
        """Test model registration."""
        mock_deployer = Mock()
        mock_deployer_class.return_value = mock_deployer
        
        config = Mock()
        
        orchestrator.register_model("model_1", config, is_primary=True)
        
        assert "model_1" in orchestrator.deployers
        assert orchestrator.primary_model == "model_1"
        mock_deployer.load_model.assert_called_once()
    
    def test_predict_with_primary_model(self, orchestrator, mock_deployer):
        """Test prediction with primary model."""
        # Register primary model
        orchestrator.deployers["primary"] = mock_deployer
        orchestrator.primary_model = "primary"
        
        # Mock successful prediction
        mock_response = Mock()
        mock_deployer.predict.return_value = mock_response
        
        request = Mock()
        response = orchestrator.predict(request)
        
        assert response == mock_response
        mock_deployer.predict.assert_called_once_with(request)
    
    def test_predict_with_failover(self, orchestrator):
        """Test prediction with failover to backup model."""
        # Setup primary and backup models
        primary_deployer = Mock()
        backup_deployer = Mock()
        
        orchestrator.deployers["primary"] = primary_deployer
        orchestrator.deployers["backup"] = backup_deployer
        orchestrator.primary_model = "primary"
        
        # Primary model fails
        primary_deployer.predict.side_effect = Exception("Primary failed")
        
        # Backup model succeeds
        mock_response = Mock()
        backup_deployer.predict.return_value = mock_response
        
        request = Mock()
        response = orchestrator.predict(request)
        
        assert response == mock_response
        backup_deployer.predict.assert_called_once_with(request)
    
    def test_predict_all_models_fail(self, orchestrator):
        """Test prediction when all models fail."""
        # Setup models that all fail
        deployer1 = Mock()
        deployer2 = Mock()
        
        deployer1.predict.side_effect = Exception("Model 1 failed")
        deployer2.predict.side_effect = Exception("Model 2 failed")
        
        orchestrator.deployers["model1"] = deployer1
        orchestrator.deployers["model2"] = deployer2
        orchestrator.primary_model = "model1"
        
        request = Mock()
        
        with pytest.raises(RuntimeError, match="All models failed"):
            orchestrator.predict(request)
    
    def test_predict_no_primary_model(self, orchestrator):
        """Test prediction with no primary model."""
        request = Mock()
        
        with pytest.raises(RuntimeError, match="No primary model available"):
            orchestrator.predict(request)
    
    def test_get_orchestrator_status(self, orchestrator):
        """Test orchestrator status reporting."""
        # Add mock deployers
        deployer1 = Mock()
        deployer2 = Mock()
        
        health1 = Mock()
        health2 = Mock()
        
        deployer1.get_health_status.return_value = health1
        deployer2.get_health_status.return_value = health2
        
        orchestrator.deployers["model1"] = deployer1
        orchestrator.deployers["model2"] = deployer2
        orchestrator.primary_model = "model1"
        
        with patch('dataclasses.asdict') as mock_asdict:
            mock_asdict.return_value = {'status': 'ready'}
            
            status = orchestrator.get_orchestrator_status()
        
        assert status['primary_model'] == "model1"
        assert status['total_models'] == 2
        assert 'models' in status
        assert 'model1' in status['models']
        assert 'model2' in status['models']


class TestUtilityFunctions:
    """Test utility functions."""
    
    @patch('ktrdr.deployment.model_deployment.MultiTimeframeModelDeployer')
    def test_deploy_model_for_production(self, mock_deployer_class):
        """Test production deployment utility."""
        mock_deployer = Mock()
        mock_deployer_class.return_value = mock_deployer
        
        model_path = Path("/tmp/production_model.pth")
        
        deployer = deploy_model_for_production(
            model_path=model_path,
            model_id="production_test",
            enable_monitoring=True,
            enable_caching=True
        )
        
        # Verify deployer was created and loaded
        mock_deployer_class.assert_called_once()
        mock_deployer.load_model.assert_called_once()
        
        # Verify config was created correctly
        call_args = mock_deployer_class.call_args[0]
        config = call_args[0]
        
        assert config.model_path == model_path
        assert config.model_id == "production_test"
        assert config.enable_monitoring is True
        assert config.enable_prediction_cache is True


class TestThreadSafety:
    """Test thread safety of deployment components."""
    
    def test_cache_thread_safety(self):
        """Test cache thread safety under concurrent access."""
        cache = PredictionCache(max_size=100, ttl_seconds=10)
        results = []
        errors = []
        
        def cache_worker(worker_id):
            try:
                for i in range(50):
                    features = {'worker': worker_id, 'iteration': i}
                    prediction = Mock()
                    
                    # Concurrent put/get operations
                    cache.put(features, prediction)
                    result = cache.get(features)
                    results.append(result is not None)
                    
                    # Clear occasionally to test eviction
                    if i % 10 == 0:
                        cache.clear()
                        
            except Exception as e:
                errors.append(e)
        
        # Run multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=cache_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should not have errors
        assert len(errors) == 0
        assert len(results) > 0
    
    def test_monitor_thread_safety(self):
        """Test monitor thread safety under concurrent access."""
        monitor = PerformanceMonitor(window_size=100)
        errors = []
        
        def monitor_worker(worker_id):
            try:
                for i in range(50):
                    prediction = Mock()
                    prediction.confidence = 0.5 + (worker_id * 0.1)
                    prediction.prediction = worker_id % 3
                    prediction.timestamp = pd.Timestamp.now(tz='UTC')
                    
                    # Concurrent operations
                    monitor.record_prediction(prediction, 20.0 + i)
                    stats = monitor.get_performance_stats()
                    
                    # Verify basic structure
                    assert 'total_predictions' in stats
                    
            except Exception as e:
                errors.append(e)
        
        # Run multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=monitor_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should not have errors
        assert len(errors) == 0
        
        # Final stats should be consistent
        final_stats = monitor.get_performance_stats()
        assert final_stats['total_predictions'] > 0


class TestErrorHandling:
    """Test error handling in deployment system."""
    
    def test_model_loading_error_recovery(self):
        """Test error recovery during model loading."""
        config = DeploymentConfig(
            model_path=Path("/nonexistent/model.pth"),
            model_id="error_test"
        )
        
        deployer = MultiTimeframeModelDeployer(config)
        
        # Should handle file not found gracefully
        with pytest.raises(FileNotFoundError):
            deployer.load_model()
        
        assert deployer.status == ModelStatus.ERROR
    
    def test_prediction_error_handling(self):
        """Test prediction error handling."""
        config = DeploymentConfig(
            model_path=Path("/tmp/test.pth"),
            model_id="error_test",
            enable_circuit_breaker=True
        )
        
        deployer = MultiTimeframeModelDeployer(config)
        deployer.status = ModelStatus.READY
        deployer.model = Mock()
        deployer.model.model = Mock()
        
        # Mock model that raises error
        deployer.model.model.side_effect = RuntimeError("Model inference failed")
        
        request = PredictionRequest(
            request_id="error_test",
            timestamp=pd.Timestamp.now(tz='UTC'),
            features={'test': 1.0},
            timeframes=['1h']
        )
        
        # Should handle prediction error
        with pytest.raises(RuntimeError):
            deployer.predict(request)
        
        # Should increment error count
        assert deployer.total_errors > 0
    
    def test_orchestrator_error_handling(self):
        """Test orchestrator error handling."""
        orchestrator = ModelOrchestrator()
        
        # No models registered
        request = Mock()
        
        with pytest.raises(RuntimeError, match="No primary model available"):
            orchestrator.predict(request)


if __name__ == "__main__":
    pytest.main([__file__])