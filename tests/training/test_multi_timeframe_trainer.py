"""Tests for multi-timeframe neural network training pipeline."""

import pytest
import pandas as pd
import numpy as np
import torch
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

from ktrdr.training.multi_timeframe_trainer import (
    MultiTimeframeTrainer,
    MultiTimeframeTrainingConfig,
    TrainingDataSpec,
    TrainingResult
)
from ktrdr.training.data_preparation import DataPreparationConfig


class TestMultiTimeframeTrainer:
    """Test the multi-timeframe neural network trainer."""
    
    @pytest.fixture
    def sample_config(self):
        """Create sample training configuration."""
        data_spec = TrainingDataSpec(
            symbol="AAPL",
            start_date="2024-01-01",
            end_date="2024-03-01",
            timeframes=["1h", "4h"],
            lookback_periods={"1h": 100, "4h": 50}
        )
        
        config = MultiTimeframeTrainingConfig(
            data_spec=data_spec,
            indicator_config={
                "timeframes": [
                    {
                        "timeframe": "1h",
                        "indicators": [
                            {"type": "RSI", "params": {"period": 14}},
                            {"type": "SimpleMovingAverage", "params": {"period": 20}}
                        ]
                    },
                    {
                        "timeframe": "4h",
                        "indicators": [
                            {"type": "RSI", "params": {"period": 14}}
                        ]
                    }
                ]
            },
            fuzzy_config={
                "variables": {
                    "rsi": {
                        "membership_functions": {
                            "low": {"type": "trapezoidal", "points": [0, 0, 25, 35]},
                            "high": {"type": "trapezoidal", "points": [65, 75, 100, 100]}
                        }
                    }
                }
            },
            neural_config={
                "timeframe_configs": {
                    "1h": {"expected_features": ["rsi_membership"], "weight": 1.0, "enabled": True},
                    "4h": {"expected_features": ["rsi_membership"], "weight": 0.8, "enabled": True}
                },
                "architecture": {
                    "hidden_layers": [32, 16],
                    "dropout": 0.3,
                    "activation": "relu"
                },
                "training": {
                    "learning_rate": 0.001,
                    "batch_size": 16,
                    "epochs": 10,
                    "early_stopping_patience": 5
                }
            },
            feature_config={
                "timeframe_specs": {
                    "1h": {"fuzzy_features": ["rsi_membership"], "weight": 1.0, "enabled": True},
                    "4h": {"fuzzy_features": ["rsi_membership"], "weight": 0.8, "enabled": True}
                },
                "scaling": {"enabled": True, "type": "standard"}
            },
            training_config={
                "labeling": {"min_change_percent": 0.02, "min_bars": 5},
                "validation_split": 0.2,
                "test_split": 0.1,
                "random_seed": 42
            }
        )
        
        return config
    
    @pytest.fixture
    def sample_data(self):
        """Create sample training data."""
        np.random.seed(42)
        
        # Create 1h data
        dates_1h = pd.date_range('2024-01-01', periods=200, freq='1h')
        prices_1h = 100 + np.cumsum(np.random.normal(0, 1, 200))
        
        data_1h = pd.DataFrame({
            'timestamp': dates_1h,
            'open': prices_1h * 0.999,
            'high': prices_1h * 1.001,
            'low': prices_1h * 0.998,
            'close': prices_1h,
            'volume': np.random.randint(1000, 10000, 200)
        })
        
        # Create 4h data (every 4th hour)
        data_4h = data_1h.iloc[::4].reset_index(drop=True)
        
        return {
            "1h": data_1h,
            "4h": data_4h
        }
    
    @pytest.fixture
    def trainer(self, sample_config):
        """Create trainer instance."""
        return MultiTimeframeTrainer(sample_config)
    
    def test_trainer_initialization(self, trainer, sample_config):
        """Test trainer initialization."""
        assert trainer.config == sample_config
        assert trainer.data_manager is None
        assert trainer.indicator_engine is None
        assert trainer.fuzzy_engine is None
        assert trainer.feature_engineer is None
        assert trainer.model is None
    
    def test_prepare_training_pipeline(self, trainer):
        """Test training pipeline preparation."""
        trainer.prepare_training_pipeline()
        
        # Check that all components are initialized
        assert trainer.data_manager is not None
        assert trainer.indicator_engine is not None
        assert trainer.fuzzy_engine is not None
        assert trainer.feature_engineer is not None
        assert trainer.labeler is not None
    
    @patch('ktrdr.training.multi_timeframe_trainer.MultiTimeframeDataManager')
    @patch('ktrdr.training.multi_timeframe_trainer.MultiTimeframeIndicatorEngine')
    @patch('ktrdr.training.multi_timeframe_trainer.MultiTimeframeFuzzyEngine')
    def test_load_and_prepare_data(self, mock_fuzzy, mock_indicator, mock_data_manager, trainer, sample_data):
        """Test data loading and preparation."""
        # Setup mocks
        mock_data_manager.return_value.synchronize_timeframes.return_value = sample_data
        
        # Mock indicator data
        indicator_data = {}
        for tf, df in sample_data.items():
            indicator_df = df.copy()
            indicator_df['rsi_14'] = np.random.uniform(20, 80, len(df))
            indicator_data[tf] = indicator_df
        
        mock_indicator.return_value.apply_multi_timeframe.return_value = indicator_data
        
        # Mock fuzzy data
        fuzzy_data = {}
        for tf, df in sample_data.items():
            fuzzy_df = df.copy()
            fuzzy_df['rsi_membership'] = np.random.uniform(0, 1, len(df))
            fuzzy_data[tf] = fuzzy_df
        
        mock_fuzzy.return_value.compute_multi_timeframe_memberships.return_value = fuzzy_data
        
        # Prepare pipeline and load data
        trainer.prepare_training_pipeline()
        
        # Mock the _load_timeframe_data method to return our sample data
        def mock_load_timeframe_data(symbol, timeframe, start_date, end_date, lookback):
            return sample_data.get(timeframe)
        
        trainer._load_timeframe_data = mock_load_timeframe_data
        
        # Load and prepare data
        stats = trainer.load_and_prepare_data()
        
        # Verify data was loaded
        assert trainer.raw_data is not None
        assert len(trainer.raw_data) == 2  # 1h and 4h
        assert trainer.indicator_data is not None
        assert trainer.fuzzy_data is not None
        assert trainer.labels is not None
        assert isinstance(stats, dict)
    
    def test_prepare_training_features(self, trainer):
        """Test training feature preparation."""
        # Mock data
        trainer.fuzzy_data = {
            "1h": pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
                'rsi_membership': np.random.uniform(0, 1, 100)
            }),
            "4h": pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=25, freq='4h'),
                'rsi_membership': np.random.uniform(0, 1, 25)
            })
        }
        
        trainer.labels = pd.Series(
            np.random.choice([0, 1, 2], 100),
            index=pd.date_range('2024-01-01', periods=100, freq='1h')
        )
        
        trainer.indicator_data = {
            "1h": trainer.fuzzy_data["1h"].copy(),
            "4h": trainer.fuzzy_data["4h"].copy()
        }
        
        # Mock feature engineer
        trainer.feature_engineer = Mock()
        trainer.feature_engineer.prepare_batch_features.return_value = Mock(
            features_tensor=torch.randn(100, 10),
            feature_names=['feature_1', 'feature_2'],
            timeframe_feature_map={'1h': ['feature_1'], '4h': ['feature_2']}
        )
        
        # Prepare features
        X, y = trainer.prepare_training_features()
        
        # Verify features
        assert isinstance(X, torch.Tensor)
        assert isinstance(y, torch.Tensor)
        assert X.shape[0] == y.shape[0]  # Same number of samples
    
    @patch('ktrdr.training.multi_timeframe_trainer.MultiTimeframeMLP')
    def test_train_model(self, mock_mlp_class, trainer):
        """Test model training."""
        # Setup trainer with mock data
        trainer.fuzzy_data = {
            "1h": pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
                'rsi_membership': np.random.uniform(0, 1, 100)
            })
        }
        
        trainer.labels = pd.Series(
            np.random.choice([0, 1, 2], 100),
            index=pd.date_range('2024-01-01', periods=100, freq='1h')
        )
        
        # Mock feature preparation
        trainer.prepare_training_features = Mock(return_value=(
            torch.randn(100, 10),  # Features
            torch.randint(0, 3, (100,))  # Labels
        ))
        
        # Mock MLP model
        mock_model = Mock()
        mock_model.build_model.return_value = Mock()
        mock_model.train.return_value = Mock(
            training_history={'train_loss': [1.0, 0.8, 0.6]},
            feature_importance={'feature_1': 0.6, 'feature_2': 0.4},
            timeframe_contributions={'1h': 1.0},
            model_performance={'train_accuracy': 0.8, 'val_accuracy': 0.75}
        )
        mock_mlp_class.return_value = mock_model
        
        # Mock evaluation
        trainer._evaluate_model = Mock(return_value={
            'accuracy': 0.77,
            'classification_report': {'macro avg': {'f1-score': 0.76}},
            'confusion_matrix': [[20, 5, 5], [3, 25, 7], [2, 4, 29]]
        })
        
        # Train model
        result = trainer.train_model()
        
        # Verify training result
        assert isinstance(result, TrainingResult)
        assert result.model is not None
        assert 'train_accuracy' in result.performance_metrics
        assert 'test_accuracy' in result.performance_metrics
        assert result.feature_importance is not None
        assert result.timeframe_contributions is not None
    
    def test_model_saving_and_loading(self, trainer):
        """Test model saving and loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "test_model.pth"
            
            # Create mock model
            mock_model = Mock()
            mock_model.model = Mock()
            mock_model.model.state_dict.return_value = {'layer1.weight': torch.randn(10, 5)}
            mock_model.config = {'test': 'config'}
            mock_model.feature_scaler = None
            mock_model.feature_order = ['feature_1', 'feature_2']
            
            trainer.model = mock_model
            
            # Save model
            trainer.save_model(model_path)
            assert model_path.exists()
            
            # Load model
            with patch('ktrdr.training.multi_timeframe_trainer.MultiTimeframeMLP') as mock_mlp:
                mock_loaded_model = Mock()
                mock_loaded_model.build_model.return_value = Mock()
                mock_loaded_model.model = Mock()
                mock_loaded_model.model.load_state_dict.return_value = None
                mock_mlp.return_value = mock_loaded_model
                
                loaded_model = trainer.load_model(model_path)
                
                assert loaded_model is not None
                mock_loaded_model.build_model.assert_called_once()
                mock_loaded_model.model.load_state_dict.assert_called_once()
    
    def test_create_training_report(self, trainer):
        """Test training report creation."""
        # Setup mock training result
        mock_result = TrainingResult(
            model=Mock(),
            training_history={'train_loss': [1.0, 0.8], 'val_accuracy': [0.7, 0.75]},
            performance_metrics={'train_accuracy': 0.8, 'val_accuracy': 0.75, 'test_accuracy': 0.77},
            feature_importance={'feature_1': 0.6, 'feature_2': 0.4},
            timeframe_contributions={'1h': 0.7, '4h': 0.3},
            data_stats={'timeframes': ['1h', '4h']}
        )
        
        trainer.model = Mock()
        trainer.model.get_model_summary.return_value = {'total_parameters': 1000}
        
        # Create report
        report = trainer.create_training_report(mock_result)
        
        # Verify report structure
        assert 'training_config' in report
        assert 'model_architecture' in report
        assert 'performance' in report
        assert 'training_history' in report
        assert 'feature_analysis' in report
        assert 'data_statistics' in report
        assert 'timestamp' in report
        
        # Verify content
        assert report['training_config']['symbol'] == "AAPL"
        assert report['performance']['test_accuracy'] == 0.77
        assert report['feature_analysis']['timeframe_contributions']['1h'] == 0.7


class TestDataPreparationIntegration:
    """Test integration with data preparation module."""
    
    @pytest.fixture
    def sample_multi_timeframe_data(self):
        """Create sample multi-timeframe data."""
        np.random.seed(42)
        
        # Create base hourly data
        dates = pd.date_range('2024-01-01', periods=500, freq='1h')
        prices = 100 + np.cumsum(np.random.normal(0, 1, 500))
        
        indicator_data = {}
        fuzzy_data = {}
        price_data = {}
        
        for tf_mult, tf_name in [(1, '1h'), (4, '4h'), (24, '1d')]:
            # Subsample data for different timeframes
            tf_dates = dates[::tf_mult]
            tf_prices = prices[::tf_mult]
            
            # Price data
            price_df = pd.DataFrame({
                'timestamp': tf_dates,
                'open': tf_prices * 0.999,
                'high': tf_prices * 1.001,
                'low': tf_prices * 0.998,
                'close': tf_prices,
                'volume': np.random.randint(1000, 10000, len(tf_prices))
            })
            price_data[tf_name] = price_df
            
            # Indicator data
            indicator_df = price_df.copy()
            indicator_df['rsi_14'] = np.random.uniform(20, 80, len(tf_prices))
            indicator_df['sma_20'] = tf_prices + np.random.normal(0, 1, len(tf_prices))
            indicator_data[tf_name] = indicator_df
            
            # Fuzzy data
            fuzzy_df = price_df.copy()
            fuzzy_df['rsi_membership'] = np.random.uniform(0, 1, len(tf_prices))
            fuzzy_df['trend_membership'] = np.random.uniform(0, 1, len(tf_prices))
            fuzzy_data[tf_name] = fuzzy_df
        
        return indicator_data, fuzzy_data, price_data
    
    def test_data_preparation_integration(self, sample_multi_timeframe_data):
        """Test integration with data preparation module."""
        from ktrdr.training.data_preparation import MultiTimeframeDataPreparator, DataPreparationConfig
        
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        # Create data preparator
        config = DataPreparationConfig(
            sequence_length=20,
            prediction_horizon=3,
            overlap_ratio=0.5,
            min_data_quality=0.7
        )
        
        preparator = MultiTimeframeDataPreparator(config)
        
        # Prepare training data
        train_seq, val_seq, quality_report = preparator.prepare_training_data(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify sequences
        assert train_seq.features.shape[0] > 0  # Has training samples
        assert val_seq.features.shape[0] > 0    # Has validation samples
        assert train_seq.features.shape[1] == val_seq.features.shape[1]  # Same feature count
        
        # Verify quality report
        assert quality_report.overall_quality_score >= 0.0
        assert len(quality_report.timeframe_completeness) == 3  # 1h, 4h, 1d
        
        # Verify metadata
        assert train_seq.metadata['dataset_type'] == 'training'
        assert val_seq.metadata['dataset_type'] == 'validation'


class TestCrossTimeframeFeatures:
    """Test cross-timeframe feature engineering integration."""
    
    def test_cross_timeframe_feature_extraction(self):
        """Test cross-timeframe feature extraction."""
        from ktrdr.training.cross_timeframe_features import CrossTimeframeFeatureEngineer
        
        # Create sample data
        np.random.seed(42)
        
        indicator_data = {}
        fuzzy_data = {}
        price_data = {}
        
        for tf in ['1h', '4h']:
            dates = pd.date_range('2024-01-01', periods=100, freq='1h' if tf == '1h' else '4h')
            prices = 100 + np.cumsum(np.random.normal(0, 1, 100))
            
            price_data[tf] = pd.DataFrame({
                'timestamp': dates,
                'close': prices
            })
            
            indicator_data[tf] = pd.DataFrame({
                'timestamp': dates,
                'rsi_14': np.random.uniform(20, 80, 100)
            })
            
            fuzzy_data[tf] = pd.DataFrame({
                'timestamp': dates,
                'rsi_membership': np.random.uniform(0, 1, 100)
            })
        
        # Create feature engineer
        config = {
            'enabled_features': ['correlation', 'momentum_cascade', 'trend_alignment'],
            'normalize_features': True
        }
        
        engineer = CrossTimeframeFeatureEngineer(config)
        
        # Extract features
        result = engineer.extract_cross_timeframe_features(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify results
        assert result.features.shape[1] > 0  # Has features
        assert len(result.feature_names) == result.features.shape[1]
        assert 'correlation' in result.feature_metadata
        assert 'momentum_cascade' in result.extraction_stats


class TestTrainingPresets:
    """Test training configuration presets."""
    
    def test_preset_loading(self):
        """Test loading of training presets."""
        from config.training_presets import MultiTimeframeTrainingPresets
        
        # Test all presets load successfully
        all_presets = MultiTimeframeTrainingPresets.get_all_presets()
        
        assert len(all_presets) > 0
        assert 'quick_test' in all_presets
        assert 'production' in all_presets
        
        # Test individual preset
        quick_test = MultiTimeframeTrainingPresets.get_quick_test_preset()
        
        assert quick_test.name == 'quick_test'
        assert 'data_spec' in quick_test.config
        assert 'neural_config' in quick_test.config
        assert len(quick_test.recommended_use_cases) > 0
    
    def test_preset_configuration_validity(self):
        """Test that preset configurations are valid."""
        from config.training_presets import MultiTimeframeTrainingPresets
        
        presets = MultiTimeframeTrainingPresets.get_all_presets()
        
        for preset_name, preset in presets.items():
            config = preset.config
            
            # Check required sections exist
            if 'data_spec' in config:
                assert 'timeframes' in config['data_spec']
            
            if 'neural_config' in config:
                if 'architecture' in config['neural_config']:
                    arch = config['neural_config']['architecture']
                    assert 'hidden_layers' in arch
                    assert isinstance(arch['hidden_layers'], list)
                
                if 'training' in config['neural_config']:
                    training = config['neural_config']['training']
                    assert 'learning_rate' in training
                    assert 'epochs' in training
            
            # Verify numeric values are reasonable
            if 'data_preparation' in config:
                prep = config['data_preparation']
                if 'sequence_length' in prep:
                    assert prep['sequence_length'] > 0
                if 'prediction_horizon' in prep:
                    assert prep['prediction_horizon'] > 0


if __name__ == "__main__":
    pytest.main([__file__])