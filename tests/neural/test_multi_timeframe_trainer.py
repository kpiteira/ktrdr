"""
Tests for multi-timeframe neural network trainer.
"""

import pytest
import numpy as np
import torch
from unittest.mock import Mock, patch

from ktrdr.neural.training.multi_timeframe_trainer import (
    MultiTimeframeTrainer,
    MultiTimeframeTrainingConfig,
    CrossTimeframeValidationConfig,
    EarlyStoppingConfig,
    TrainingMetrics,
    EnhancedEarlyStopping,
    create_multi_timeframe_trainer
)


class TestMultiTimeframeTrainer:
    """Tests for MultiTimeframeTrainer."""
    
    @pytest.fixture
    def sample_multi_timeframe_data(self):
        """Sample multi-timeframe data."""
        np.random.seed(42)
        return {
            "1h": {
                "fuzzy_features": np.random.randn(100, 8),
                "indicator_features": np.random.randn(100, 5)
            },
            "4h": {
                "fuzzy_features": np.random.randn(100, 6),
                "indicator_features": np.random.randn(100, 4)
            },
            "1d": {
                "fuzzy_features": np.random.randn(100, 4),
                "indicator_features": np.random.randn(100, 3)
            }
        }
    
    @pytest.fixture
    def sample_labels(self):
        """Sample labels."""
        np.random.seed(42)
        return np.random.choice([0, 1, 2], size=100, p=[0.3, 0.4, 0.3])
    
    @pytest.fixture
    def basic_training_config(self):
        """Basic training configuration."""
        return MultiTimeframeTrainingConfig(
            model_config={
                "timeframe_configs": {
                    "1h": {"expected_features": ["rsi", "macd"], "weight": 0.5},
                    "4h": {"expected_features": ["ema", "bb"], "weight": 0.3},
                    "1d": {"expected_features": ["sma"], "weight": 0.2}
                },
                "architecture": {"hidden_layers": [20, 10], "dropout": 0.2},
                "training": {"epochs": 50, "learning_rate": 0.01}
            },
            feature_engineering_config={
                "scaling": {"method": "standard"},
                "selection": {"method": "none"},
                "dimensionality_reduction": {"method": "none"}
            },
            validation_config=CrossTimeframeValidationConfig(
                method="temporal_split",
                test_size=0.2
            ),
            early_stopping_config=EarlyStoppingConfig(
                patience=10,
                monitor="val_loss"
            ),
            training_params={"epochs": 50},
            save_checkpoints=False
        )
    
    def test_trainer_initialization(self, basic_training_config):
        """Test trainer initialization."""
        trainer = MultiTimeframeTrainer(basic_training_config)
        
        assert trainer.config == basic_training_config
        assert trainer.model is None
        assert trainer.feature_engineer is None
        assert not trainer.is_trained
        assert len(trainer.training_history) == 0
    
    @patch('ktrdr.neural.training.multi_timeframe_trainer.MultiTimeframeMLP')
    @patch('ktrdr.neural.training.multi_timeframe_trainer.MultiTimeframeFeatureEngineer')
    def test_basic_training(self, mock_feature_engineer, mock_mlp, 
                          basic_training_config, sample_multi_timeframe_data, sample_labels):
        """Test basic training workflow."""
        # Mock feature engineer
        mock_fe_instance = Mock()
        mock_feature_engineer.return_value = mock_fe_instance
        
        # Mock feature engineering result
        feature_result = Mock()
        feature_result.transformed_features = np.random.randn(80, 15)  # 80% for training
        feature_result.feature_importance = {"feature_0": 0.5, "feature_1": 0.3}
        mock_fe_instance.fit_transform.return_value = feature_result
        mock_fe_instance.transform.return_value = np.random.randn(20, 15)  # 20% for validation
        
        # Mock model
        mock_model_instance = Mock()
        mock_mlp.return_value = mock_model_instance
        mock_model_instance.is_trained = True
        
        # Mock training result
        from ktrdr.neural.models.multi_timeframe_mlp import MultiTimeframeTrainingResult
        mock_training_result = MultiTimeframeTrainingResult(
            training_history={"train_loss": [0.5, 0.3], "val_loss": [0.6, 0.4]},
            feature_importance={"feature_0": 0.5},
            timeframe_contributions={"1h": 0.5, "4h": 0.3, "1d": 0.2},
            model_performance={"train_accuracy": 0.8, "val_accuracy": 0.7},
            convergence_metrics={"converged": True, "final_epoch": 30}
        )
        mock_model_instance.train.return_value = mock_training_result
        
        # Mock model for metrics calculation
        mock_model_instance.model = Mock()
        mock_model_instance.model.eval = Mock()
        
        # Mock model outputs
        mock_outputs = torch.tensor([[0.1, 0.8, 0.1], [0.2, 0.3, 0.5]])
        mock_model_instance.model.return_value = mock_outputs
        
        # Create trainer and train
        trainer = MultiTimeframeTrainer(basic_training_config)
        result = trainer.train(sample_multi_timeframe_data, sample_labels)
        
        # Verify results
        assert isinstance(result, MultiTimeframeTrainingResult)
        assert trainer.is_trained
        assert trainer.model is not None
        assert trainer.feature_engineer is not None
    
    def test_validation_split_temporal(self, basic_training_config):
        """Test temporal validation split."""
        trainer = MultiTimeframeTrainer(basic_training_config)
        
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1, 2], size=100)
        
        X_train, X_val, y_train, y_val = trainer._create_validation_split(X, y)
        
        # Check sizes
        assert len(X_train) == 80  # 80% for training
        assert len(X_val) == 20    # 20% for validation
        assert len(y_train) == 80
        assert len(y_val) == 20
        
        # Check temporal ordering (training data should come before validation)
        # This is implicit in temporal split
    
    def test_validation_split_stratified(self, basic_training_config):
        """Test stratified validation split."""
        # Modify config for stratified split
        basic_training_config.validation_config.method = "stratified_split"
        basic_training_config.validation_config.shuffle = True
        
        trainer = MultiTimeframeTrainer(basic_training_config)
        
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1, 2], size=100)
        
        X_train, X_val, y_train, y_val = trainer._create_validation_split(X, y)
        
        # Check sizes
        assert len(X_train) == 80
        assert len(X_val) == 20
        
        # Check that all classes are represented in both splits
        assert len(np.unique(y_train)) > 1
        assert len(np.unique(y_val)) > 1
    
    def test_prepare_timeframe_features(self, basic_training_config, sample_multi_timeframe_data):
        """Test timeframe feature preparation."""
        trainer = MultiTimeframeTrainer(basic_training_config)
        
        features_by_timeframe = trainer._prepare_timeframe_features(sample_multi_timeframe_data)
        
        assert "1h" in features_by_timeframe
        assert "4h" in features_by_timeframe
        assert "1d" in features_by_timeframe
        
        # Check that features were combined correctly
        assert features_by_timeframe["1h"].shape[1] == 8 + 5  # fuzzy + indicator features
        assert features_by_timeframe["4h"].shape[1] == 6 + 4
        assert features_by_timeframe["1d"].shape[1] == 4 + 3
    
    def test_cross_timeframe_consistency_calculation(self, basic_training_config):
        """Test cross-timeframe consistency calculation."""
        trainer = MultiTimeframeTrainer(basic_training_config)
        
        # Create correlated features for consistency test
        base_signal = np.random.randn(100)
        features_by_timeframe = {
            "1h": np.column_stack([base_signal + 0.1 * np.random.randn(100) for _ in range(5)]),
            "4h": np.column_stack([base_signal + 0.2 * np.random.randn(100) for _ in range(3)]),
            "1d": np.column_stack([base_signal + 0.3 * np.random.randn(100) for _ in range(2)])
        }
        
        consistency = trainer._calculate_cross_timeframe_consistency(features_by_timeframe)
        
        assert isinstance(consistency, float)
        assert 0.0 <= consistency <= 1.0
        # Should be reasonably high due to correlation
        assert consistency > 0.3
    
    def test_single_timeframe_consistency(self, basic_training_config):
        """Test consistency calculation with single timeframe."""
        trainer = MultiTimeframeTrainer(basic_training_config)
        
        features_by_timeframe = {
            "1h": np.random.randn(100, 5)
        }
        
        consistency = trainer._calculate_cross_timeframe_consistency(features_by_timeframe)
        
        # Should return 1.0 for perfect consistency with single timeframe
        assert consistency == 1.0
    
    def test_factory_function(self):
        """Test factory function for creating trainer."""
        config_dict = {
            "model_config": {"timeframe_configs": {}},
            "feature_engineering_config": {"scaling": {"method": "standard"}},
            "validation_config": {"method": "temporal_split"},
            "early_stopping_config": {"patience": 10},
            "training_params": {"epochs": 100}
        }
        
        trainer = create_multi_timeframe_trainer(config_dict)
        
        assert isinstance(trainer, MultiTimeframeTrainer)
        assert isinstance(trainer.config, MultiTimeframeTrainingConfig)


class TestCrossTimeframeValidationConfig:
    """Tests for CrossTimeframeValidationConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CrossTimeframeValidationConfig()
        
        assert config.method == "temporal_split"
        assert config.n_splits == 5
        assert config.test_size == 0.2
        assert config.validation_size == 0.15
        assert config.holdout_timeframe is None
        assert config.temporal_gap == 0
        assert config.shuffle is False
        assert config.random_state == 42
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = CrossTimeframeValidationConfig(
            method="stratified_kfold",
            n_splits=10,
            test_size=0.3,
            shuffle=True,
            random_state=123
        )
        
        assert config.method == "stratified_kfold"
        assert config.n_splits == 10
        assert config.test_size == 0.3
        assert config.shuffle is True
        assert config.random_state == 123


class TestEarlyStoppingConfig:
    """Tests for EarlyStoppingConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = EarlyStoppingConfig()
        
        assert config.monitor == "val_loss"
        assert config.patience == 20
        assert config.min_delta == 0.001
        assert config.mode == "min"
        assert config.restore_best_weights is True
        assert config.baseline is None
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = EarlyStoppingConfig(
            monitor="val_accuracy",
            patience=15,
            min_delta=0.01,
            mode="max",
            restore_best_weights=False,
            baseline=0.8
        )
        
        assert config.monitor == "val_accuracy"
        assert config.patience == 15
        assert config.min_delta == 0.01
        assert config.mode == "max"
        assert config.restore_best_weights is False
        assert config.baseline == 0.8


class TestEnhancedEarlyStopping:
    """Tests for EnhancedEarlyStopping."""
    
    def test_early_stopping_min_mode(self):
        """Test early stopping in min mode (for loss)."""
        config = EarlyStoppingConfig(monitor="val_loss", patience=3, mode="min")
        early_stopping = EnhancedEarlyStopping(config)
        
        # Mock model
        model = Mock()
        model.state_dict.return_value = {"param": torch.tensor([1.0])}
        model.load_state_dict = Mock()
        
        # Test improving scores
        assert not early_stopping(1.0, model)  # First score
        assert not early_stopping(0.8, model)  # Improvement
        assert not early_stopping(0.6, model)  # Improvement
        assert not early_stopping(0.7, model)  # Worse (1st patience)
        assert not early_stopping(0.8, model)  # Worse (2nd patience)
        assert early_stopping(0.9, model)      # Worse (3rd patience) - should stop
    
    def test_early_stopping_max_mode(self):
        """Test early stopping in max mode (for accuracy)."""
        config = EarlyStoppingConfig(monitor="val_accuracy", patience=2, mode="max")
        early_stopping = EnhancedEarlyStopping(config)
        
        # Mock model
        model = Mock()
        model.state_dict.return_value = {"param": torch.tensor([1.0])}
        
        # Test improving scores
        assert not early_stopping(0.6, model)  # First score
        assert not early_stopping(0.8, model)  # Improvement
        assert not early_stopping(0.7, model)  # Worse (1st patience)
        assert early_stopping(0.6, model)      # Worse (2nd patience) - should stop
    
    def test_min_delta_threshold(self):
        """Test min_delta threshold."""
        config = EarlyStoppingConfig(patience=2, mode="min", min_delta=0.1)
        early_stopping = EnhancedEarlyStopping(config)
        
        model = Mock()
        model.state_dict.return_value = {"param": torch.tensor([1.0])}
        
        # Small improvement below min_delta should not reset patience
        assert not early_stopping(1.0, model)   # First score
        assert not early_stopping(0.95, model)  # Small improvement (below min_delta)
        assert early_stopping(0.94, model)      # Another small improvement - should stop
    
    def test_restore_best_weights(self):
        """Test restoring best weights functionality."""
        config = EarlyStoppingConfig(patience=2, mode="min", restore_best_weights=True)
        early_stopping = EnhancedEarlyStopping(config)
        
        model = Mock()
        best_state = {"param": torch.tensor([1.0])}
        model.state_dict.return_value = best_state
        model.load_state_dict = Mock()
        
        # Train with improvement then degradation
        early_stopping(1.0, model)  # First score (saves as best)
        early_stopping(1.5, model)  # Worse
        should_stop = early_stopping(2.0, model)  # Worse - triggers stop
        
        assert should_stop
        # Should restore best weights
        model.load_state_dict.assert_called_once_with(best_state)


class TestTrainingMetrics:
    """Tests for TrainingMetrics dataclass."""
    
    def test_metrics_creation(self):
        """Test creating TrainingMetrics objects."""
        metrics = TrainingMetrics(
            epoch=10,
            train_loss=0.5,
            train_accuracy=0.8,
            val_loss=0.6,
            val_accuracy=0.75,
            cross_timeframe_consistency=0.9,
            timeframe_accuracies={"1h": 0.8, "4h": 0.7},
            learning_rate=0.001,
            gradient_norm=0.5,
            processing_time=1.2
        )
        
        assert metrics.epoch == 10
        assert metrics.train_loss == 0.5
        assert metrics.cross_timeframe_consistency == 0.9
        assert metrics.timeframe_accuracies["1h"] == 0.8
        assert metrics.processing_time == 1.2