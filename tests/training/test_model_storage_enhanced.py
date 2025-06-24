"""
Tests for enhanced ModelStorage with pure fuzzy support.
"""

import pytest
import torch
import torch.nn as nn
import tempfile
import shutil
from pathlib import Path
from sklearn.preprocessing import StandardScaler

from ktrdr.training.model_storage import ModelStorage


class TestEnhancedModelStorage:
    """Test cases for enhanced model storage supporting pure fuzzy models."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary model storage."""
        temp_dir = Path(tempfile.mkdtemp())
        storage = ModelStorage(str(temp_dir))
        yield storage
        shutil.rmtree(temp_dir)

    @pytest.fixture 
    def test_model(self):
        """Create simple test model."""
        return nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(), 
            nn.Linear(5, 3)
        )

    def test_save_pure_fuzzy_model(self, temp_storage, test_model):
        """Test saving pure fuzzy model (no scaler)."""
        config = {
            'model': {
                'features': {
                    'include_raw_indicators': False,
                    'include_price_context': False,
                    'include_volume_context': False,
                    'scale_features': False,
                    'lookback_periods': 2
                }
            }
        }
        
        feature_names = ['rsi_oversold', 'rsi_neutral', 'macd_positive']
        
        model_path = temp_storage.save_model(
            model=test_model,
            strategy_name='pure_fuzzy_test',
            symbol='AAPL',
            timeframe='1h',
            config=config,
            training_metrics={'final_train_accuracy': 0.85},
            feature_names=feature_names,
            scaler=None
        )
        
        assert model_path is not None
        
        # Check that scaler.pkl was not created
        scaler_path = Path(model_path) / "scaler.pkl"
        assert not scaler_path.exists()

    def test_save_mixed_features_model(self, temp_storage, test_model):
        """Test saving mixed features model (with scaler)."""
        config = {
            'model': {
                'features': {
                    'include_raw_indicators': False,
                    'include_price_context': True,
                    'include_volume_context': True,
                    'scale_features': True,
                    'lookback_periods': 1
                }
            }
        }
        
        feature_names = ['rsi_oversold', 'price_ratio', 'volume_ratio']
        scaler = StandardScaler()
        
        model_path = temp_storage.save_model(
            model=test_model,
            strategy_name='mixed_test',
            symbol='AAPL',
            timeframe='1h',
            config=config,
            training_metrics={'final_train_accuracy': 0.82},
            feature_names=feature_names,
            scaler=scaler
        )
        
        assert model_path is not None
        
        # Check that scaler.pkl was created
        scaler_path = Path(model_path) / "scaler.pkl"
        assert scaler_path.exists()

    def test_load_pure_fuzzy_model(self, temp_storage, test_model):
        """Test loading pure fuzzy model."""
        config = {
            'model': {
                'features': {
                    'lookback_periods': 2,
                    'scale_features': False
                }
            }
        }
        
        feature_names = ['rsi_oversold', 'macd_positive']
        
        # Save model
        temp_storage.save_model(
            model=test_model,
            strategy_name='fuzzy_load_test',
            symbol='MSFT',
            timeframe='4h', 
            config=config,
            training_metrics={'final_train_accuracy': 0.90},
            feature_names=feature_names,
            scaler=None
        )
        
        # Load model
        loaded = temp_storage.load_model('fuzzy_load_test', 'MSFT', '4h')
        
        assert loaded['model_version'] == 'pure_fuzzy_v1'
        assert loaded['architecture_type'] == 'pure_fuzzy'
        assert loaded['is_pure_fuzzy'] is True
        assert loaded['scaler'] is None
        assert loaded['features']['feature_type'] == 'pure_fuzzy'
        assert 'fuzzy_features' in loaded['features']
        assert loaded['features']['scaling_info']['requires_scaling'] is False

    def test_load_mixed_features_model(self, temp_storage, test_model):
        """Test loading mixed features model."""
        config = {
            'model': {
                'features': {
                    'lookback_periods': 1,
                    'scale_features': True
                }
            }
        }
        
        feature_names = ['rsi_oversold', 'price_feature']
        scaler = StandardScaler()
        
        # Save model
        temp_storage.save_model(
            model=test_model,
            strategy_name='mixed_load_test',
            symbol='GOOGL',
            timeframe='1d',
            config=config,
            training_metrics={'final_train_accuracy': 0.88},
            feature_names=feature_names,
            scaler=scaler
        )
        
        # Load model
        loaded = temp_storage.load_model('mixed_load_test', 'GOOGL', '1d')
        
        assert loaded['model_version'] == 'mixed_features_v1'
        assert loaded['architecture_type'] == 'mixed_features'
        assert loaded['is_pure_fuzzy'] is False
        assert loaded['scaler'] is not None
        assert isinstance(loaded['scaler'], StandardScaler)
        assert loaded['features']['feature_type'] == 'mixed_features'
        assert 'feature_names' in loaded['features']
        assert loaded['features']['scaling_info']['requires_scaling'] is True

    def test_feature_metadata_pure_fuzzy(self, temp_storage, test_model):
        """Test feature metadata for pure fuzzy models."""
        config = {
            'model': {
                'features': {
                    'lookback_periods': 3,
                    'scale_features': False
                }
            }
        }
        
        feature_names = ['rsi_oversold', 'rsi_neutral', 'macd_positive', 'sma_above']
        
        temp_storage.save_model(
            model=test_model,
            strategy_name='fuzzy_metadata_test',
            symbol='AAPL',
            timeframe='1h',
            config=config,
            training_metrics={'final_train_accuracy': 0.85},
            feature_names=feature_names,
            scaler=None
        )
        
        loaded = temp_storage.load_model('fuzzy_metadata_test', 'AAPL', '1h')
        features = loaded['features']
        
        assert features['model_version'] == 'pure_fuzzy_v1'
        assert features['feature_type'] == 'pure_fuzzy'
        assert features['fuzzy_features'] == feature_names
        assert features['feature_count'] == len(feature_names)
        assert features['temporal_config']['lookback_periods'] == 3
        assert features['temporal_config']['enabled'] is True
        assert features['scaling_info']['requires_scaling'] is False
        assert features['scaling_info']['reason'] == 'fuzzy_values_already_normalized'

    def test_feature_metadata_mixed(self, temp_storage, test_model):
        """Test feature metadata for mixed features models."""
        config = {
            'model': {
                'features': {
                    'lookback_periods': 1,
                    'scale_features': True
                }
            }
        }
        
        feature_names = ['rsi_oversold', 'price_ratio', 'volume_change']
        scaler = StandardScaler()
        
        temp_storage.save_model(
            model=test_model,
            strategy_name='mixed_metadata_test',
            symbol='MSFT',
            timeframe='4h',
            config=config,
            training_metrics={'final_train_accuracy': 0.83},
            feature_names=feature_names,
            scaler=scaler
        )
        
        loaded = temp_storage.load_model('mixed_metadata_test', 'MSFT', '4h')
        features = loaded['features']
        
        assert features['model_version'] == 'mixed_features_v1'
        assert features['feature_type'] == 'mixed_features'
        assert features['feature_names'] == feature_names
        assert features['feature_count'] == len(feature_names)
        assert features['scaling_info']['requires_scaling'] is True
        assert features['scaling_info']['scaler_type'] == 'StandardScaler'

    def test_metadata_enhancement(self, temp_storage, test_model):
        """Test enhanced metadata for model versioning."""
        config = {'model': {'features': {'scale_features': False}}}
        
        temp_storage.save_model(
            model=test_model,
            strategy_name='metadata_test',
            symbol='AAPL',
            timeframe='1h',
            config=config,
            training_metrics={'final_train_accuracy': 0.87, 'epochs_trained': 50},
            feature_names=['rsi_oversold'],
            scaler=None
        )
        
        loaded = temp_storage.load_model('metadata_test', 'AAPL', '1h')
        metadata = loaded['metadata']
        
        assert metadata['model_version'] == 'pure_fuzzy_v1'
        assert metadata['architecture_type'] == 'pure_fuzzy'
        assert metadata['feature_engineering']['removed'] is True
        assert metadata['feature_engineering']['scaler_required'] is False
        assert metadata['feature_engineering']['fuzzy_only'] is True

    def test_backward_compatibility(self, temp_storage, test_model):
        """Test that enhanced storage is backward compatible."""
        # Save a model with new format
        config = {'model': {'features': {'scale_features': True}}}
        scaler = StandardScaler()
        
        temp_storage.save_model(
            model=test_model,
            strategy_name='compat_test',
            symbol='AAPL',
            timeframe='1h',
            config=config,
            training_metrics={'final_train_accuracy': 0.80},
            feature_names=['feature1', 'feature2'],
            scaler=scaler
        )
        
        # Load and verify
        loaded = temp_storage.load_model('compat_test', 'AAPL', '1h')
        
        # Should have all legacy fields plus new ones
        assert 'model' in loaded
        assert 'config' in loaded
        assert 'features' in loaded
        assert 'metadata' in loaded
        assert 'scaler' in loaded
        assert 'model_path' in loaded
        
        # Plus new fields
        assert 'model_version' in loaded
        assert 'architecture_type' in loaded
        assert 'is_pure_fuzzy' in loaded

    def test_temporal_config_no_lookback(self, temp_storage, test_model):
        """Test temporal config when no lookback is used."""
        config = {
            'model': {
                'features': {
                    'lookback_periods': 0,
                    'scale_features': False
                }
            }
        }
        
        temp_storage.save_model(
            model=test_model,
            strategy_name='no_lookback_test',
            symbol='AAPL',
            timeframe='1h',
            config=config,
            training_metrics={'final_train_accuracy': 0.85},
            feature_names=['rsi_oversold'],
            scaler=None
        )
        
        loaded = temp_storage.load_model('no_lookback_test', 'AAPL', '1h')
        temporal_config = loaded['features']['temporal_config']
        
        assert temporal_config['lookback_periods'] == 0
        assert temporal_config['enabled'] is False