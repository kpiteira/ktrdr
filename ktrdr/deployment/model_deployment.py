"""Production deployment system for multi-timeframe neural network models.

This module provides a complete deployment pipeline including model serving,
real-time inference, monitoring, and failover capabilities for production
trading environments.
"""

import torch
import torch.nn as nn
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import pickle
import logging
import time
import threading
import queue
from datetime import datetime, timedelta
from enum import Enum
import warnings
from abc import ABC, abstractmethod

from ktrdr import get_logger
from ktrdr.neural.models.multi_timeframe_mlp import MultiTimeframeMLP
from ktrdr.training.multi_timeframe_trainer import MultiTimeframeTrainer
from ktrdr.evaluation.multi_timeframe_evaluator import MultiTimeframeEvaluator

logger = get_logger(__name__)


class ModelStatus(Enum):
    """Model deployment status."""
    LOADING = "loading"
    READY = "ready"
    PREDICTING = "predicting"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class PredictionConfidence(Enum):
    """Prediction confidence levels."""
    VERY_HIGH = "very_high"  # > 90%
    HIGH = "high"           # 80-90%
    MEDIUM = "medium"       # 60-80%
    LOW = "low"            # 40-60%
    VERY_LOW = "very_low"  # < 40%


@dataclass
class DeploymentConfig:
    """Configuration for model deployment."""
    # Model settings
    model_path: Path
    model_id: str
    version: str = "1.0.0"
    
    # Performance settings
    max_batch_size: int = 32
    prediction_timeout: float = 1.0  # seconds
    warmup_samples: int = 10
    
    # Monitoring settings
    enable_monitoring: bool = True
    performance_window: int = 1000  # predictions
    drift_detection_threshold: float = 0.1
    
    # Failover settings
    enable_failover: bool = True
    fallback_models: List[str] = None
    max_retry_attempts: int = 3
    
    # Caching settings
    enable_prediction_cache: bool = True
    cache_size: int = 1000
    cache_ttl: int = 300  # seconds
    
    # Safety settings
    min_confidence_threshold: float = 0.5
    max_prediction_age: int = 60  # seconds
    enable_circuit_breaker: bool = True


@dataclass
class PredictionRequest:
    """Request for model prediction."""
    request_id: str
    timestamp: pd.Timestamp
    features: Dict[str, Any]
    timeframes: List[str]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PredictionResponse:
    """Response from model prediction."""
    request_id: str
    prediction: int  # 0=BUY, 1=HOLD, 2=SELL
    confidence: float
    confidence_level: PredictionConfidence
    probabilities: Dict[str, float]
    processing_time_ms: float
    model_version: str
    timestamp: pd.Timestamp
    warnings: List[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelHealthStatus:
    """Health status of deployed model."""
    model_id: str
    status: ModelStatus
    uptime_seconds: float
    total_predictions: int
    avg_response_time_ms: float
    error_rate: float
    last_prediction_time: Optional[pd.Timestamp]
    memory_usage_mb: float
    cpu_usage_percent: float
    warnings: List[str]
    last_health_check: pd.Timestamp


class PredictionCache:
    """Thread-safe prediction cache."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = {}
        self.access_times = {}
        self._lock = threading.Lock()
    
    def _generate_key(self, features: Dict[str, Any]) -> str:
        """Generate cache key from features."""
        # Simple hash of feature values
        feature_str = json.dumps(features, sort_keys=True, default=str)
        return str(hash(feature_str))
    
    def get(self, features: Dict[str, Any]) -> Optional[PredictionResponse]:
        """Get cached prediction."""
        with self._lock:
            key = self._generate_key(features)
            
            if key in self.cache:
                # Check TTL
                if time.time() - self.access_times[key] < self.ttl_seconds:
                    return self.cache[key]
                else:
                    # Expired
                    del self.cache[key]
                    del self.access_times[key]
            
            return None
    
    def put(self, features: Dict[str, Any], prediction: PredictionResponse) -> None:
        """Cache prediction."""
        with self._lock:
            key = self._generate_key(features)
            
            # Evict oldest if cache is full
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.access_times.keys(), key=self.access_times.get)
                del self.cache[oldest_key]
                del self.access_times[oldest_key]
            
            self.cache[key] = prediction
            self.access_times[key] = time.time()
    
    def clear(self) -> None:
        """Clear cache."""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()


class PerformanceMonitor:
    """Monitor model performance and detect drift."""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.predictions = []
        self.response_times = []
        self.errors = []
        self._lock = threading.Lock()
    
    def record_prediction(
        self, 
        prediction: PredictionResponse, 
        response_time_ms: float,
        error: Optional[Exception] = None
    ) -> None:
        """Record prediction for monitoring."""
        with self._lock:
            # Record prediction
            self.predictions.append({
                'timestamp': prediction.timestamp,
                'confidence': prediction.confidence,
                'prediction': prediction.prediction,
                'processing_time': response_time_ms
            })
            
            # Record response time
            self.response_times.append(response_time_ms)
            
            # Record error if any
            if error:
                self.errors.append({
                    'timestamp': pd.Timestamp.now(tz='UTC'),
                    'error': str(error),
                    'type': type(error).__name__
                })
            
            # Maintain window size
            if len(self.predictions) > self.window_size:
                self.predictions.pop(0)
            if len(self.response_times) > self.window_size:
                self.response_times.pop(0)
            if len(self.errors) > self.window_size:
                self.errors.pop(0)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        with self._lock:
            if not self.predictions:
                return {}
            
            stats = {
                'total_predictions': len(self.predictions),
                'avg_response_time_ms': np.mean(self.response_times) if self.response_times else 0,
                'p95_response_time_ms': np.percentile(self.response_times, 95) if self.response_times else 0,
                'error_count': len(self.errors),
                'error_rate': len(self.errors) / len(self.predictions) if self.predictions else 0,
                'avg_confidence': np.mean([p['confidence'] for p in self.predictions]),
                'prediction_distribution': self._get_prediction_distribution()
            }
            
            return stats
    
    def _get_prediction_distribution(self) -> Dict[str, float]:
        """Get distribution of predictions."""
        if not self.predictions:
            return {}
        
        predictions = [p['prediction'] for p in self.predictions]
        total = len(predictions)
        
        return {
            'BUY': predictions.count(0) / total,
            'HOLD': predictions.count(1) / total,
            'SELL': predictions.count(2) / total
        }
    
    def detect_drift(self, baseline_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Detect performance drift compared to baseline."""
        current_stats = self.get_performance_stats()
        
        if not current_stats or not baseline_stats:
            return {}
        
        drift_results = {}
        
        # Check confidence drift
        baseline_confidence = baseline_stats.get('avg_confidence', 0)
        current_confidence = current_stats.get('avg_confidence', 0)
        confidence_drift = abs(current_confidence - baseline_confidence)
        
        # Check distribution drift
        baseline_dist = baseline_stats.get('prediction_distribution', {})
        current_dist = current_stats.get('prediction_distribution', {})
        
        distribution_drift = 0
        for class_name in ['BUY', 'HOLD', 'SELL']:
            baseline_prob = baseline_dist.get(class_name, 0)
            current_prob = current_dist.get(class_name, 0)
            distribution_drift += abs(current_prob - baseline_prob)
        
        drift_results = {
            'confidence_drift': confidence_drift,
            'distribution_drift': distribution_drift,
            'response_time_drift': abs(
                current_stats.get('avg_response_time_ms', 0) - 
                baseline_stats.get('avg_response_time_ms', 0)
            ),
            'drift_detected': (
                confidence_drift > 0.1 or 
                distribution_drift > 0.2 or
                current_stats.get('error_rate', 0) > baseline_stats.get('error_rate', 0) + 0.05
            )
        }
        
        return drift_results


class CircuitBreaker:
    """Circuit breaker for model protection."""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()
    
    def call(self, func: Callable) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == "OPEN":
                if (time.time() - self.last_failure_time) > self.timeout_seconds:
                    self.state = "HALF_OPEN"
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = func()
                
                if self.state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                
                return result
                
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                
                raise e


class MultiTimeframeModelDeployer:
    """Production deployment system for multi-timeframe models."""
    
    def __init__(self, config: DeploymentConfig):
        """
        Initialize model deployer.
        
        Args:
            config: Deployment configuration
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # Model state
        self.model: Optional[MultiTimeframeMLP] = None
        self.model_metadata: Dict[str, Any] = {}
        self.status = ModelStatus.LOADING
        self.start_time = time.time()
        
        # Performance tracking
        self.total_predictions = 0
        self.total_errors = 0
        self.last_prediction_time: Optional[pd.Timestamp] = None
        
        # Components
        self.cache = PredictionCache(
            max_size=config.cache_size,
            ttl_seconds=config.cache_ttl
        ) if config.enable_prediction_cache else None
        
        self.monitor = PerformanceMonitor(
            window_size=config.performance_window
        ) if config.enable_monitoring else None
        
        self.circuit_breaker = CircuitBreaker() if config.enable_circuit_breaker else None
        
        # Thread safety
        self._prediction_lock = threading.Lock()
        
        self.logger.info(f"Initialized ModelDeployer for {config.model_id}")
    
    def load_model(self) -> None:
        """Load model from configured path."""
        try:
            self.status = ModelStatus.LOADING
            self.logger.info(f"Loading model from {self.config.model_path}")
            
            # Load model checkpoint
            checkpoint = torch.load(self.config.model_path, map_location='cpu')
            
            # Extract model configuration
            model_config = checkpoint['model_config']
            self.model = MultiTimeframeMLP(model_config)
            
            # Determine input size from checkpoint
            first_layer_key = next(k for k in checkpoint['model_state_dict'].keys() if 'weight' in k)
            input_size = checkpoint['model_state_dict'][first_layer_key].shape[1]
            
            # Build and load model
            self.model.build_model(input_size)
            self.model.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.model.eval()
            
            # Load metadata
            self.model_metadata = {
                'model_config': model_config,
                'input_size': input_size,
                'feature_scaler': checkpoint.get('feature_scaler'),
                'feature_order': checkpoint.get('feature_order', []),
                'training_config': checkpoint.get('training_config'),
                'load_time': pd.Timestamp.now(tz='UTC')
            }
            
            # Warmup model
            self._warmup_model()
            
            self.status = ModelStatus.READY
            self.logger.info("Model loaded successfully")
            
        except Exception as e:
            self.status = ModelStatus.ERROR
            self.logger.error(f"Failed to load model: {e}")
            raise
    
    def _warmup_model(self) -> None:
        """Warmup model with sample predictions."""
        try:
            input_size = self.model_metadata['input_size']
            
            for _ in range(self.config.warmup_samples):
                # Generate random input
                dummy_input = torch.randn(1, input_size)
                
                with torch.no_grad():
                    _ = self.model.model(dummy_input)
            
            self.logger.info("Model warmup completed")
            
        except Exception as e:
            self.logger.warning(f"Model warmup failed: {e}")
    
    def predict(self, request: PredictionRequest) -> PredictionResponse:
        """Make prediction with the deployed model."""
        
        if self.status != ModelStatus.READY:
            raise RuntimeError(f"Model not ready: {self.status}")
        
        start_time = time.time()
        
        try:
            # Check cache first
            if self.cache:
                cached_response = self.cache.get(request.features)
                if cached_response:
                    cached_response.request_id = request.request_id
                    return cached_response
            
            # Make prediction
            with self._prediction_lock:
                self.status = ModelStatus.PREDICTING
                
                if self.circuit_breaker:
                    response = self.circuit_breaker.call(
                        lambda: self._make_prediction(request, start_time)
                    )
                else:
                    response = self._make_prediction(request, start_time)
                
                self.status = ModelStatus.READY
            
            # Cache result
            if self.cache:
                self.cache.put(request.features, response)
            
            # Record performance
            processing_time = (time.time() - start_time) * 1000
            if self.monitor:
                self.monitor.record_prediction(response, processing_time)
            
            self.total_predictions += 1
            self.last_prediction_time = pd.Timestamp.now(tz='UTC')
            
            return response
            
        except Exception as e:
            self.total_errors += 1
            self.status = ModelStatus.READY
            
            # Record error
            if self.monitor:
                processing_time = (time.time() - start_time) * 1000
                self.monitor.record_prediction(None, processing_time, e)
            
            self.logger.error(f"Prediction failed: {e}")
            raise
    
    def _make_prediction(
        self, 
        request: PredictionRequest, 
        start_time: float
    ) -> PredictionResponse:
        """Internal prediction logic."""
        
        # Prepare features
        features = self._prepare_features(request.features)
        
        # Model inference
        with torch.no_grad():
            outputs = self.model.model(features)
            probabilities = torch.softmax(outputs, dim=1)
            predicted_class = torch.argmax(outputs, dim=1).item()
            max_confidence = torch.max(probabilities).item()
        
        # Convert probabilities to dict
        prob_dict = {
            'BUY': float(probabilities[0][0]),
            'HOLD': float(probabilities[0][1]),
            'SELL': float(probabilities[0][2])
        }
        
        # Determine confidence level
        confidence_level = self._get_confidence_level(max_confidence)
        
        # Check confidence threshold
        warnings_list = []
        if max_confidence < self.config.min_confidence_threshold:
            warnings_list.append(f"Low confidence prediction: {max_confidence:.3f}")
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Check timeout
        if processing_time_ms > self.config.prediction_timeout * 1000:
            warnings_list.append(f"Prediction timeout exceeded: {processing_time_ms:.1f}ms")
        
        return PredictionResponse(
            request_id=request.request_id,
            prediction=predicted_class,
            confidence=max_confidence,
            confidence_level=confidence_level,
            probabilities=prob_dict,
            processing_time_ms=processing_time_ms,
            model_version=self.config.version,
            timestamp=pd.Timestamp.now(tz='UTC'),
            warnings=warnings_list if warnings_list else None,
            metadata={
                'timeframes': request.timeframes,
                'model_id': self.config.model_id
            }
        )
    
    def _prepare_features(self, features: Dict[str, Any]) -> torch.Tensor:
        """Prepare features for model input."""
        
        feature_order = self.model_metadata.get('feature_order', [])
        feature_scaler = self.model_metadata.get('feature_scaler')
        
        # Extract features in correct order
        if feature_order:
            feature_values = []
            for feature_name in feature_order:
                value = features.get(feature_name, 0.0)
                if pd.isna(value):
                    value = 0.0
                feature_values.append(float(value))
        else:
            # Use all available features
            feature_values = [
                float(features.get(k, 0.0)) for k in sorted(features.keys())
            ]
        
        # Convert to tensor
        features_tensor = torch.FloatTensor([feature_values])
        
        # Apply scaling if available
        if feature_scaler:
            try:
                scaled_features = feature_scaler.transform([feature_values])
                features_tensor = torch.FloatTensor(scaled_features)
            except Exception as e:
                self.logger.warning(f"Feature scaling failed: {e}")
        
        return features_tensor
    
    def _get_confidence_level(self, confidence: float) -> PredictionConfidence:
        """Get confidence level enum from confidence score."""
        if confidence >= 0.9:
            return PredictionConfidence.VERY_HIGH
        elif confidence >= 0.8:
            return PredictionConfidence.HIGH
        elif confidence >= 0.6:
            return PredictionConfidence.MEDIUM
        elif confidence >= 0.4:
            return PredictionConfidence.LOW
        else:
            return PredictionConfidence.VERY_LOW
    
    def get_health_status(self) -> ModelHealthStatus:
        """Get current health status."""
        
        uptime = time.time() - self.start_time
        
        # Get performance stats
        performance_stats = self.monitor.get_performance_stats() if self.monitor else {}
        
        avg_response_time = performance_stats.get('avg_response_time_ms', 0)
        error_rate = self.total_errors / max(self.total_predictions, 1)
        
        # Get system metrics (placeholder)
        memory_usage_mb = 0.0  # Would implement actual memory monitoring
        cpu_usage_percent = 0.0  # Would implement actual CPU monitoring
        
        # Collect warnings
        warnings_list = []
        if error_rate > 0.05:
            warnings_list.append(f"High error rate: {error_rate:.2%}")
        if avg_response_time > self.config.prediction_timeout * 1000:
            warnings_list.append(f"High response time: {avg_response_time:.1f}ms")
        if self.status == ModelStatus.ERROR:
            warnings_list.append("Model in error state")
        
        return ModelHealthStatus(
            model_id=self.config.model_id,
            status=self.status,
            uptime_seconds=uptime,
            total_predictions=self.total_predictions,
            avg_response_time_ms=avg_response_time,
            error_rate=error_rate,
            last_prediction_time=self.last_prediction_time,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
            warnings=warnings_list,
            last_health_check=pd.Timestamp.now(tz='UTC')
        )
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update deployment configuration."""
        
        # Update relevant configuration parameters
        for key, value in new_config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                self.logger.info(f"Updated config {key} = {value}")
        
        # Clear cache if cache settings changed
        if 'cache_size' in new_config or 'cache_ttl' in new_config:
            if self.cache:
                self.cache.clear()
    
    def shutdown(self) -> None:
        """Gracefully shutdown the deployment."""
        self.logger.info("Shutting down model deployment")
        
        self.status = ModelStatus.MAINTENANCE
        
        if self.cache:
            self.cache.clear()
        
        # Clear model from memory
        self.model = None
        self.model_metadata.clear()
        
        self.logger.info("Deployment shutdown complete")


class ModelOrchestrator:
    """Orchestrate multiple model deployments with load balancing and failover."""
    
    def __init__(self):
        self.deployers: Dict[str, MultiTimeframeModelDeployer] = {}
        self.primary_model: Optional[str] = None
        self.logger = get_logger(__name__)
        self._lock = threading.Lock()
    
    def register_model(
        self, 
        model_id: str, 
        config: DeploymentConfig,
        is_primary: bool = False
    ) -> None:
        """Register a new model deployment."""
        
        with self._lock:
            deployer = MultiTimeframeModelDeployer(config)
            deployer.load_model()
            
            self.deployers[model_id] = deployer
            
            if is_primary or self.primary_model is None:
                self.primary_model = model_id
            
            self.logger.info(f"Registered model {model_id}, primary: {is_primary}")
    
    def predict(self, request: PredictionRequest) -> PredictionResponse:
        """Make prediction using primary model with failover."""
        
        if not self.primary_model or self.primary_model not in self.deployers:
            raise RuntimeError("No primary model available")
        
        # Try primary model first
        try:
            return self.deployers[self.primary_model].predict(request)
        
        except Exception as e:
            self.logger.warning(f"Primary model {self.primary_model} failed: {e}")
            
            # Try failover models
            for model_id, deployer in self.deployers.items():
                if model_id != self.primary_model:
                    try:
                        response = deployer.predict(request)
                        self.logger.info(f"Failover to model {model_id} successful")
                        return response
                    except Exception as failover_error:
                        self.logger.warning(f"Failover model {model_id} failed: {failover_error}")
            
            # All models failed
            raise RuntimeError("All models failed to make prediction")
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get status of all deployed models."""
        
        status = {
            'primary_model': self.primary_model,
            'total_models': len(self.deployers),
            'models': {}
        }
        
        for model_id, deployer in self.deployers.items():
            health = deployer.get_health_status()
            status['models'][model_id] = asdict(health)
        
        return status


def create_deployment_config(
    model_path: Path,
    model_id: str,
    **kwargs
) -> DeploymentConfig:
    """Create deployment configuration with defaults."""
    
    config_dict = {
        'model_path': model_path,
        'model_id': model_id,
        'version': '1.0.0',
        'max_batch_size': 32,
        'prediction_timeout': 1.0,
        'warmup_samples': 10,
        'enable_monitoring': True,
        'performance_window': 1000,
        'drift_detection_threshold': 0.1,
        'enable_failover': True,
        'max_retry_attempts': 3,
        'enable_prediction_cache': True,
        'cache_size': 1000,
        'cache_ttl': 300,
        'min_confidence_threshold': 0.5,
        'max_prediction_age': 60,
        'enable_circuit_breaker': True
    }
    
    # Update with provided kwargs
    config_dict.update(kwargs)
    
    return DeploymentConfig(**config_dict)


def deploy_model_for_production(
    model_path: Path,
    model_id: str,
    enable_monitoring: bool = True,
    enable_caching: bool = True
) -> MultiTimeframeModelDeployer:
    """
    Deploy model for production with standard settings.
    
    Args:
        model_path: Path to trained model
        model_id: Unique model identifier
        enable_monitoring: Enable performance monitoring
        enable_caching: Enable prediction caching
        
    Returns:
        Deployed model instance
    """
    
    config = create_deployment_config(
        model_path=model_path,
        model_id=model_id,
        enable_monitoring=enable_monitoring,
        enable_prediction_cache=enable_caching
    )
    
    deployer = MultiTimeframeModelDeployer(config)
    deployer.load_model()
    
    return deployer