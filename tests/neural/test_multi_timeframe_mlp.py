"""
Unit tests for Multi-Timeframe MLP neural network.

This module contains comprehensive tests for the MultiTimeframeMLP
and related multi-timeframe neural network functionality.
"""

import pytest
import torch
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch

from ktrdr.neural.models.multi_timeframe_mlp import (
    MultiTimeframeMLP,
    TimeframeFeatureConfig,
    MultiTimeframeTrainingResult,
)
from ktrdr.training.multi_timeframe_feature_engineering import (
    MultiTimeframeFeatureEngineer,
    TimeframeFeatureSpec,
    MultiTimeframeFeatureResult,
)
from ktrdr.errors import ConfigurationError


class TestTimeframeFeatureConfig:
    """Test TimeframeFeatureConfig dataclass."""

    def test_timeframe_config_creation(self):
        """Test TimeframeFeatureConfig creation."""
        config = TimeframeFeatureConfig(
            timeframe="1h",
            expected_features=["rsi_low", "rsi_high", "macd_negative"],
            weight=1.5,
            enabled=True,
        )

        assert config.timeframe == "1h"
        assert config.expected_features == ["rsi_low", "rsi_high", "macd_negative"]
        assert config.weight == 1.5
        assert config.enabled is True


class TestMultiTimeframeMLP:
    """Test MultiTimeframeMLP neural network."""

    @pytest.fixture
    def basic_config(self):
        """Create basic multi-timeframe MLP configuration."""
        return {
            "timeframe_configs": {
                "1h": {
                    "expected_features": [
                        "rsi_low",
                        "rsi_high",
                        "macd_negative",
                        "macd_positive",
                    ],
                    "weight": 1.0,
                    "enabled": True,
                },
                "4h": {
                    "expected_features": [
                        "rsi_low",
                        "rsi_high",
                        "trend_up",
                        "trend_down",
                    ],
                    "weight": 1.2,
                    "enabled": True,
                },
                "1d": {
                    "expected_features": ["trend_direction"],
                    "weight": 1.5,
                    "enabled": True,
                },
            },
            "architecture": {
                "hidden_layers": [27, 18, 9],  # 3x input (9 features), then reduce
                "dropout": 0.3,
                "activation": "relu",
                "batch_norm": True,
                "output_activation": "softmax",
            },
            "training": {
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 100,
                "optimizer": "adam",
                "early_stopping_patience": 10,
            },
            "feature_processing": {"scale_features": True, "scaler_type": "standard"},
        }

    @pytest.fixture
    def minimal_config(self):
        """Create minimal configuration for testing."""
        return {
            "timeframe_configs": {
                "1h": {
                    "expected_features": ["rsi_low", "rsi_high"],
                    "weight": 1.0,
                    "enabled": True,
                }
            },
            "architecture": {"hidden_layers": [6, 3], "dropout": 0.2},
            "training": {"epochs": 10},
        }

    def test_initialization(self, basic_config):
        """Test MultiTimeframeMLP initialization."""
        model = MultiTimeframeMLP(basic_config)

        assert model.config == basic_config
        assert len(model.timeframe_configs) == 3
        assert "1h" in model.timeframe_configs
        assert "4h" in model.timeframe_configs
        assert "1d" in model.timeframe_configs

        # Check feature order establishment
        assert len(model.feature_order) == 9  # 4 + 4 + 1 features
        assert all(
            "_1h" in name or "_4h" in name or "_1d" in name
            for name in model.feature_order
        )

    def test_timeframe_ordering(self, basic_config):
        """Test consistent timeframe ordering."""
        model = MultiTimeframeMLP(basic_config)

        timeframe_order = model._get_timeframe_order()
        # Should be ordered from shortest to longest: 1h, 4h, 1d
        assert timeframe_order == ["1h", "4h", "1d"]

    def test_build_model(self, basic_config):
        """Test neural network model building."""
        # Disable batch norm for single sample testing
        basic_config["architecture"]["batch_norm"] = False
        model = MultiTimeframeMLP(basic_config)

        input_size = 9  # Total features across timeframes
        nn_model = model.build_model(input_size)

        assert model.input_size == input_size
        assert model.expected_input_size == input_size
        assert nn_model is not None

        # Test forward pass
        test_input = torch.randn(1, input_size)
        output = nn_model(test_input)
        assert output.shape == (1, 3)  # BUY/HOLD/SELL
        assert torch.allclose(output.sum(dim=1), torch.ones(1))  # Softmax sums to 1

    def test_build_model_with_different_architectures(self, minimal_config):
        """Test model building with different architectures."""
        # Test with batch norm disabled
        minimal_config["architecture"]["batch_norm"] = False
        model = MultiTimeframeMLP(minimal_config)
        nn_model = model.build_model(2)
        assert nn_model is not None

        # Test with different activation
        minimal_config["architecture"]["activation"] = "tanh"
        model = MultiTimeframeMLP(minimal_config)
        nn_model = model.build_model(2)
        assert nn_model is not None

    def test_prepare_features_success(self, basic_config):
        """Test successful multi-timeframe feature preparation."""
        model = MultiTimeframeMLP(basic_config)

        # Mock fuzzy data for multiple timeframes
        fuzzy_data = {
            "1h": pd.DataFrame(
                {
                    "rsi_low": [0.8],
                    "rsi_high": [0.1],
                    "macd_negative": [0.7],
                    "macd_positive": [0.2],
                }
            ),
            "4h": pd.DataFrame(
                {
                    "rsi_low": [0.3],
                    "rsi_high": [0.6],
                    "trend_up": [0.8],
                    "trend_down": [0.1],
                }
            ),
            "1d": pd.DataFrame({"trend_direction": [0.9]}),
        }

        features = model.prepare_features(fuzzy_data, {})

        assert features.shape == (1, 9)  # 1 sample, 9 features
        assert torch.all(features >= 0)  # All features should be non-negative
        assert torch.all(features <= 2)  # Should be reasonable after scaling

    def test_prepare_features_missing_timeframe(self, basic_config):
        """Test feature preparation with missing timeframe data."""
        model = MultiTimeframeMLP(basic_config)

        # Missing 4h data
        fuzzy_data = {
            "1h": pd.DataFrame(
                {
                    "rsi_low": [0.8],
                    "rsi_high": [0.1],
                    "macd_negative": [0.7],
                    "macd_positive": [0.2],
                }
            ),
            "1d": pd.DataFrame({"trend_direction": [0.9]}),
        }

        features = model.prepare_features(fuzzy_data, {})

        # Should still work, with zeros for missing timeframe
        assert features.shape == (1, 9)

    def test_prepare_features_missing_features(self, basic_config):
        """Test feature preparation with missing individual features."""
        model = MultiTimeframeMLP(basic_config)

        # Missing some features in 1h timeframe
        fuzzy_data = {
            "1h": pd.DataFrame(
                {
                    "rsi_low": [0.8],
                    "rsi_high": [0.1],
                    # Missing macd_negative and macd_positive
                }
            ),
            "4h": pd.DataFrame(
                {
                    "rsi_low": [0.3],
                    "rsi_high": [0.6],
                    "trend_up": [0.8],
                    "trend_down": [0.1],
                }
            ),
            "1d": pd.DataFrame({"trend_direction": [0.9]}),
        }

        features = model.prepare_features(fuzzy_data, {})

        # Should still work, with zeros for missing features
        assert features.shape == (1, 9)

    def test_disabled_timeframe_handling(self, basic_config):
        """Test handling of disabled timeframes."""
        # Disable 4h timeframe
        basic_config["timeframe_configs"]["4h"]["enabled"] = False

        model = MultiTimeframeMLP(basic_config)

        # Feature order should exclude 4h features
        assert len(model.feature_order) == 5  # 4 (1h) + 1 (1d) = 5 features
        assert not any("_4h" in name for name in model.feature_order)

    def test_train_basic(self, minimal_config):
        """Test basic training functionality."""
        # Disable batch norm for small batch testing
        minimal_config["architecture"]["batch_norm"] = False
        model = MultiTimeframeMLP(minimal_config)

        # Build model first
        input_size = 2
        model.model = model.build_model(input_size)

        # Create mock training data
        X = torch.randn(20, input_size)  # 20 samples, 2 features
        y = torch.randint(0, 3, (20,))  # Random BUY/HOLD/SELL labels

        # Train with minimal epochs
        result = model.train(X, y)

        assert isinstance(result, MultiTimeframeTrainingResult)
        assert model.is_trained is True
        assert "train_loss" in result.training_history
        assert "train_accuracy" in result.training_history
        assert len(result.training_history["train_loss"]) == 10  # 10 epochs

    def test_train_with_validation(self, minimal_config):
        """Test training with validation data."""
        # Disable batch norm for small batch testing
        minimal_config["architecture"]["batch_norm"] = False
        model = MultiTimeframeMLP(minimal_config)

        # Build model
        input_size = 2
        model.model = model.build_model(input_size)

        # Create training and validation data
        X_train = torch.randn(20, input_size)
        y_train = torch.randint(0, 3, (20,))
        X_val = torch.randn(10, input_size)
        y_val = torch.randint(0, 3, (10,))

        # Train with validation
        result = model.train(X_train, y_train, validation_data=(X_val, y_val))

        assert "val_loss" in result.training_history
        assert "val_accuracy" in result.training_history
        assert len(result.training_history["val_loss"]) == 10

    def test_predict_without_training(self, minimal_config):
        """Test prediction without training should raise error."""
        model = MultiTimeframeMLP(minimal_config)

        # Build but don't train model
        model.model = model.build_model(2)

        test_features = torch.randn(1, 2)

        with pytest.raises(ValueError, match="Model not trained"):
            model.predict(test_features)

    def test_predict_with_timeframe_breakdown(self, minimal_config):
        """Test prediction with timeframe contribution breakdown."""
        model = MultiTimeframeMLP(minimal_config)

        # Build and "train" model (mark as trained)
        model.model = model.build_model(2)
        model.is_trained = True

        test_features = torch.randn(1, 2)

        result = model.predict_with_timeframe_breakdown(test_features)

        assert "signal" in result
        assert "confidence" in result
        assert "timeframe_analysis" in result
        assert "contributions" in result["timeframe_analysis"]
        assert "feature_count_by_timeframe" in result["timeframe_analysis"]

    def test_model_summary(self, basic_config):
        """Test model summary generation."""
        model = MultiTimeframeMLP(basic_config)
        model.model = model.build_model(9)

        summary = model.get_model_summary()

        assert summary["model_type"] == "MultiTimeframeMLP"
        assert summary["total_parameters"] > 0
        assert summary["timeframes"] == ["1h", "4h", "1d"]
        assert summary["enabled_timeframes"] == ["1h", "4h", "1d"]
        assert summary["total_features"] == 9
        assert summary["expected_input_size"] == 9
        assert "architecture" in summary


class TestMultiTimeframeFeatureEngineer:
    """Test MultiTimeframeFeatureEngineer."""

    @pytest.fixture
    def feature_config(self):
        """Create feature engineering configuration."""
        return {
            "timeframe_specs": {
                "1h": {
                    "fuzzy_features": ["rsi_low", "rsi_high", "macd_negative"],
                    "indicator_features": ["rsi", "macd"],
                    "weight": 1.0,
                    "enabled": True,
                },
                "4h": {
                    "fuzzy_features": ["rsi_low", "trend_up"],
                    "weight": 1.2,
                    "enabled": True,
                },
            },
            "scaling": {"enabled": True, "type": "standard"},
        }

    def test_initialization(self, feature_config):
        """Test MultiTimeframeFeatureEngineer initialization."""
        engineer = MultiTimeframeFeatureEngineer(feature_config)

        assert len(engineer.timeframe_specs) == 2
        assert "1h" in engineer.timeframe_specs
        assert "4h" in engineer.timeframe_specs

        # Check timeframe spec details
        spec_1h = engineer.timeframe_specs["1h"]
        assert spec_1h.timeframe == "1h"
        assert spec_1h.fuzzy_features == ["rsi_low", "rsi_high", "macd_negative"]
        assert spec_1h.weight == 1.0

    def test_prepare_multi_timeframe_features(self, feature_config):
        """Test multi-timeframe feature preparation."""
        engineer = MultiTimeframeFeatureEngineer(feature_config)

        # Create mock data
        fuzzy_data = {
            "1h": pd.DataFrame(
                {
                    "rsi_low": [0.8, 0.7],
                    "rsi_high": [0.1, 0.2],
                    "macd_negative": [0.6, 0.5],
                }
            ),
            "4h": pd.DataFrame({"rsi_low": [0.4, 0.3], "trend_up": [0.9, 0.8]}),
        }

        indicators = {
            "1h": pd.DataFrame({"rsi": [35.0, 40.0], "macd": [-0.1, -0.05]}),
            "4h": pd.DataFrame({"rsi": [45.0, 42.0]}),
        }

        result = engineer.prepare_multi_timeframe_features(
            fuzzy_data=fuzzy_data, indicators=indicators
        )

        assert isinstance(result, MultiTimeframeFeatureResult)
        assert (
            result.features_tensor.shape[1] == 7
        )  # 3 + 2 + 2 fuzzy + indicator features
        assert len(result.feature_names) == 7
        assert "1h" in result.timeframe_feature_map
        assert "4h" in result.timeframe_feature_map

    def test_feature_validation(self, feature_config):
        """Test input data validation."""
        engineer = MultiTimeframeFeatureEngineer(feature_config)

        # Valid data
        fuzzy_data = {
            "1h": pd.DataFrame(
                {"rsi_low": [0.8], "rsi_high": [0.1], "macd_negative": [0.6]}
            ),
            "4h": pd.DataFrame({"rsi_low": [0.4], "trend_up": [0.9]}),
        }

        validation_report = engineer.validate_input_data(fuzzy_data)
        assert validation_report["valid"] is True
        assert len(validation_report["errors"]) == 0

        # Invalid data - missing timeframe
        invalid_fuzzy_data = {
            "1h": pd.DataFrame(
                {"rsi_low": [0.8], "rsi_high": [0.1], "macd_negative": [0.6]}
            )
            # Missing 4h data
        }

        validation_report = engineer.validate_input_data(invalid_fuzzy_data)
        assert validation_report["valid"] is False
        assert len(validation_report["errors"]) > 0

    def test_batch_feature_preparation(self, feature_config):
        """Test batch feature preparation."""
        engineer = MultiTimeframeFeatureEngineer(feature_config)

        # Create batch of fuzzy data (2 samples)
        batch_fuzzy_data = [
            {
                "1h": pd.DataFrame(
                    {"rsi_low": [0.8], "rsi_high": [0.1], "macd_negative": [0.6]}
                ),
                "4h": pd.DataFrame({"rsi_low": [0.4], "trend_up": [0.9]}),
            },
            {
                "1h": pd.DataFrame(
                    {"rsi_low": [0.7], "rsi_high": [0.2], "macd_negative": [0.5]}
                ),
                "4h": pd.DataFrame({"rsi_low": [0.3], "trend_up": [0.8]}),
            },
        ]

        result = engineer.prepare_batch_features(batch_fuzzy_data)

        assert result.features_tensor.shape == (2, 5)  # 2 samples, 5 features
        assert result.feature_stats["batch_size"] == 2

    def test_feature_template(self, feature_config):
        """Test feature template generation."""
        engineer = MultiTimeframeFeatureEngineer(feature_config)

        template = engineer.get_feature_template()

        assert "timeframes" in template
        assert "total_expected_features" in template
        assert template["total_expected_features"] == 7  # 3 + 2 + 2
        assert "1h" in template["timeframes"]
        assert "4h" in template["timeframes"]


class TestMultiTimeframeIntegration:
    """Test integration between MLP and FeatureEngineer."""

    @pytest.fixture
    def integration_config(self):
        """Create configuration for integration testing."""
        return {
            "model_config": {
                "timeframe_configs": {
                    "1h": {
                        "expected_features": ["rsi_low_1h", "rsi_high_1h"],
                        "weight": 1.0,
                        "enabled": True,
                    },
                    "4h": {
                        "expected_features": ["trend_up_4h", "trend_down_4h"],
                        "weight": 1.0,
                        "enabled": True,
                    },
                },
                "architecture": {"hidden_layers": [8, 4], "batch_norm": False},
                "training": {"epochs": 5},
            },
            "feature_config": {
                "timeframe_specs": {
                    "1h": {
                        "fuzzy_features": ["rsi_low", "rsi_high"],
                        "weight": 1.0,
                        "enabled": True,
                    },
                    "4h": {
                        "fuzzy_features": ["trend_up", "trend_down"],
                        "weight": 1.0,
                        "enabled": True,
                    },
                },
                "scaling": {"enabled": True, "type": "standard"},
            },
        }

    def test_end_to_end_workflow(self, integration_config):
        """Test complete end-to-end workflow."""
        # Initialize components
        model = MultiTimeframeMLP(integration_config["model_config"])
        engineer = MultiTimeframeFeatureEngineer(integration_config["feature_config"])

        # Prepare training data
        fuzzy_data = {
            "1h": pd.DataFrame(
                {"rsi_low": [0.8, 0.6, 0.9], "rsi_high": [0.1, 0.3, 0.05]}
            ),
            "4h": pd.DataFrame(
                {"trend_up": [0.7, 0.8, 0.6], "trend_down": [0.2, 0.1, 0.3]}
            ),
        }

        # Create batch data for training
        batch_fuzzy_data = [fuzzy_data] * 10  # 10 samples

        # Prepare features
        feature_result = engineer.prepare_batch_features(batch_fuzzy_data)
        X = feature_result.features_tensor
        y = torch.randint(0, 3, (10,))  # Random labels

        # Build and train model
        model.model = model.build_model(X.shape[1])
        training_result = model.train(X, y)

        # Test prediction
        test_features = engineer.prepare_multi_timeframe_features(fuzzy_data)
        prediction = model.predict(test_features.features_tensor)

        assert prediction["signal"] in ["BUY", "HOLD", "SELL"]
        assert 0.0 <= prediction["confidence"] <= 1.0
        assert training_result.convergence_metrics["final_epoch"] <= 5
