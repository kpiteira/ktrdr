"""
Tests for multi-timeframe model storage system.
"""

import pytest
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock

from ktrdr.training.multi_timeframe_model_storage import (
    MultiTimeframeModelStorage,
    create_multi_timeframe_model_storage,
)
from ktrdr.training.multi_timeframe_label_generator import (
    MultiTimeframeLabelResult,
    MultiTimeframeLabelConfig,
    LabelValidationResult,
)
from ktrdr.neural.models.multi_timeframe_mlp import MultiTimeframeTrainingResult
from ktrdr.neural.feature_engineering import FeatureEngineeringResult


class SimpleTestModel(nn.Module):
    """Simple model for testing."""

    def __init__(self, input_size: int = 10, output_size: int = 3):
        super().__init__()
        self.input_size = input_size
        self.output_size = output_size
        self.layers = nn.Sequential(
            nn.Linear(input_size, 20), nn.ReLU(), nn.Linear(20, output_size)
        )

    def forward(self, x):
        return self.layers(x)


class TestMultiTimeframeModelStorage:
    """Tests for MultiTimeframeModelStorage."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def storage(self, temp_storage_dir):
        """Create storage instance with temporary directory."""
        return MultiTimeframeModelStorage(temp_storage_dir)

    @pytest.fixture
    def sample_model(self):
        """Create sample PyTorch model."""
        model = SimpleTestModel(input_size=15, output_size=3)
        # Initialize with some weights
        with torch.no_grad():
            for param in model.parameters():
                param.fill_(0.1)
        return model

    @pytest.fixture
    def sample_config(self):
        """Create sample model configuration."""
        return {
            "timeframe_configs": {
                "1h": {"expected_features": ["rsi", "macd"], "weight": 0.5},
                "4h": {"expected_features": ["rsi", "macd"], "weight": 0.3},
                "1d": {"expected_features": ["sma"], "weight": 0.2},
            },
            "architecture": {
                "hidden_layers": [20],
                "dropout": 0.2,
                "activation": "relu",
            },
            "training": {"epochs": 50, "learning_rate": 0.001, "batch_size": 32},
        }

    @pytest.fixture
    def sample_training_result(self):
        """Create sample training result."""
        return MultiTimeframeTrainingResult(
            training_history={
                "train_loss": [0.8, 0.6, 0.4, 0.3],
                "val_loss": [0.9, 0.7, 0.5, 0.4],
                "train_accuracy": [0.6, 0.7, 0.8, 0.85],
                "val_accuracy": [0.55, 0.65, 0.75, 0.8],
            },
            feature_importance={"feature_0": 0.3, "feature_1": 0.2, "feature_2": 0.5},
            timeframe_contributions={"1h": 0.5, "4h": 0.3, "1d": 0.2},
            model_performance={"train_accuracy": 0.85, "val_accuracy": 0.8},
            convergence_metrics={"converged": True, "final_epoch": 45},
        )

    @pytest.fixture
    def sample_feature_result(self):
        """Create sample feature engineering result."""
        return FeatureEngineeringResult(
            transformed_features=np.random.randn(100, 15),
            feature_names=[f"feature_{i}" for i in range(15)],
            selected_features_mask=np.ones(15, dtype=bool),
            scaler=None,  # Simplified for testing
            dimensionality_reducer=None,
            feature_importance={"feature_0": 0.3, "feature_1": 0.2},
            feature_stats=None,
            transformation_metadata={
                "original_feature_count": 20,
                "selected_feature_count": 15,
                "final_feature_count": 15,
                "scaling_method": "standard",
                "selection_method": "none",
            },
        )

    @pytest.fixture
    def sample_label_result(self):
        """Create sample label result."""
        # Create sample data
        dates = pd.date_range("2024-01-01", periods=50, freq="1h")
        labels = pd.Series(np.random.choice([0, 1, 2], size=50), index=dates)
        confidence = pd.Series(np.random.uniform(0.5, 1.0, size=50), index=dates)
        consistency = pd.Series(np.random.uniform(0.4, 1.0, size=50), index=dates)

        timeframe_labels = {
            "1h": pd.Series(np.random.choice([0, 1, 2], size=50), index=dates),
            "4h": pd.Series(
                np.random.choice([0, 1, 2], size=13), index=dates[::4][:13]
            ),
            "1d": pd.Series(np.random.choice([0, 1, 2], size=3), index=dates[::24][:3]),
        }

        validation_results = {
            i: LabelValidationResult(
                is_valid=True,
                consistency_score=0.8,
                timeframe_agreement={"1h": True, "4h": True},
                confidence_score=0.9,
                temporal_alignment_score=0.7,
                validation_details={"test": "data"},
            )
            for i in range(10)
        }

        return MultiTimeframeLabelResult(
            labels=labels,
            timeframe_labels=timeframe_labels,
            confidence_scores=confidence,
            consistency_scores=consistency,
            validation_results=validation_results,
            label_distribution={
                "consensus": {
                    "buy_count": 15,
                    "hold_count": 20,
                    "sell_count": 15,
                    "total": 50,
                },
                "timeframes": {
                    "1h": {
                        "buy_count": 18,
                        "hold_count": 16,
                        "sell_count": 16,
                        "total": 50,
                    }
                },
            },
            metadata={
                "timeframes": ["1h", "4h", "1d"],
                "generation_timestamp": "2024-01-01T00:00:00Z",
                "validation_statistics": {
                    "validation_rate": 0.8,
                    "average_consistency": 0.8,
                    "average_confidence": 0.9,
                },
            },
        )

    def test_storage_initialization(self, temp_storage_dir):
        """Test storage initialization."""
        storage = MultiTimeframeModelStorage(temp_storage_dir)

        assert storage.base_path == Path(temp_storage_dir)
        assert storage.base_path.exists()

    def test_save_multi_timeframe_model(
        self,
        storage,
        sample_model,
        sample_config,
        sample_training_result,
        sample_feature_result,
        sample_label_result,
    ):
        """Test saving a multi-timeframe model."""
        strategy_name = "test_strategy"
        symbol = "AAPL"
        timeframes = ["1h", "4h", "1d"]

        model_path = storage.save_multi_timeframe_model(
            model=sample_model,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframes=timeframes,
            config=sample_config,
            training_result=sample_training_result,
            feature_engineering_result=sample_feature_result,
            label_result=sample_label_result,
        )

        # Check that model was saved
        assert Path(model_path).exists()

        # Check that all required files exist
        model_dir = Path(model_path)
        required_files = [
            "model_state_dict.pt",
            "model_full.pt",
            "model_info.json",
            "config.json",
            "training_results.json",
            "feature_engineering.json",
            "labels.csv",
            "label_results.json",
            "multi_timeframe_metadata.json",
        ]

        for file_name in required_files:
            assert (model_dir / file_name).exists(), f"Missing file: {file_name}"

        # Check timeframe-specific label files
        for timeframe in timeframes:
            assert (model_dir / f"labels_{timeframe}.csv").exists()

    def test_load_multi_timeframe_model(
        self,
        storage,
        sample_model,
        sample_config,
        sample_training_result,
        sample_feature_result,
        sample_label_result,
    ):
        """Test loading a multi-timeframe model."""
        strategy_name = "test_strategy"
        symbol = "AAPL"
        timeframes = ["1h", "4h", "1d"]

        # Save model first
        model_path = storage.save_multi_timeframe_model(
            model=sample_model,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframes=timeframes,
            config=sample_config,
            training_result=sample_training_result,
            feature_engineering_result=sample_feature_result,
            label_result=sample_label_result,
        )

        # Load model
        loaded_data = storage.load_multi_timeframe_model(
            strategy_name=strategy_name, symbol=symbol, timeframes=timeframes
        )

        # Check loaded data structure
        assert "model" in loaded_data
        assert "config" in loaded_data
        assert "metadata" in loaded_data
        assert "training_result" in loaded_data
        assert "feature_engineering_result" in loaded_data
        assert "label_result" in loaded_data

        # Check model is correct type
        assert isinstance(loaded_data["model"], torch.nn.Module)

        # Check config matches
        assert (
            loaded_data["config"]["timeframe_configs"]
            == sample_config["timeframe_configs"]
        )

        # Check metadata
        metadata = loaded_data["metadata"]
        assert metadata["strategy_name"] == strategy_name
        assert metadata["symbol"] == symbol
        assert metadata["timeframes"] == timeframes

    def test_load_model_without_full_results(
        self,
        storage,
        sample_model,
        sample_config,
        sample_training_result,
        sample_feature_result,
        sample_label_result,
    ):
        """Test loading model without full results."""
        strategy_name = "test_strategy"
        symbol = "AAPL"
        timeframes = ["1h", "4h"]

        # Save model
        storage.save_multi_timeframe_model(
            model=sample_model,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframes=timeframes,
            config=sample_config,
            training_result=sample_training_result,
            feature_engineering_result=sample_feature_result,
            label_result=sample_label_result,
        )

        # Load without full results
        loaded_data = storage.load_multi_timeframe_model(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframes=timeframes,
            load_full_results=False,
        )

        # Should have basic data but not full results
        assert "model" in loaded_data
        assert "config" in loaded_data
        assert "metadata" in loaded_data
        assert "training_result" not in loaded_data
        assert "feature_engineering_result" not in loaded_data
        assert "label_result" not in loaded_data

    def test_list_multi_timeframe_models(
        self,
        storage,
        sample_model,
        sample_config,
        sample_training_result,
        sample_feature_result,
        sample_label_result,
    ):
        """Test listing multi-timeframe models."""
        # Save multiple models
        models_info = [
            ("strategy1", "AAPL", ["1h", "4h"]),
            ("strategy1", "GOOGL", ["1h", "4h", "1d"]),
            ("strategy2", "AAPL", ["4h", "1d"]),
        ]

        for strategy, symbol, timeframes in models_info:
            storage.save_multi_timeframe_model(
                model=sample_model,
                strategy_name=strategy,
                symbol=symbol,
                timeframes=timeframes,
                config=sample_config,
                training_result=sample_training_result,
                feature_engineering_result=sample_feature_result,
                label_result=sample_label_result,
            )

        # List all models
        all_models = storage.list_multi_timeframe_models()
        assert len(all_models) == 3

        # Filter by strategy
        strategy1_models = storage.list_multi_timeframe_models(
            strategy_name="strategy1"
        )
        assert len(strategy1_models) == 2

        # Filter by symbol
        aapl_models = storage.list_multi_timeframe_models(symbol="AAPL")
        assert len(aapl_models) == 2

        # Check model info structure
        model_info = all_models[0]
        assert "strategy_name" in model_info
        assert "symbol" in model_info
        assert "timeframes" in model_info
        assert "created_at" in model_info
        assert "performance" in model_info

    def test_load_nonexistent_model(self, storage):
        """Test loading a model that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            storage.load_multi_timeframe_model(
                strategy_name="nonexistent", symbol="AAPL", timeframes=["1h"]
            )

    def test_save_model_with_additional_metadata(
        self,
        storage,
        sample_model,
        sample_config,
        sample_training_result,
        sample_feature_result,
        sample_label_result,
    ):
        """Test saving model with additional metadata."""
        additional_metadata = {
            "experiment_id": "exp_001",
            "researcher": "test_user",
            "notes": "Test experiment with enhanced features",
        }

        model_path = storage.save_multi_timeframe_model(
            model=sample_model,
            strategy_name="test_strategy",
            symbol="AAPL",
            timeframes=["1h", "4h"],
            config=sample_config,
            training_result=sample_training_result,
            feature_engineering_result=sample_feature_result,
            label_result=sample_label_result,
            model_metadata=additional_metadata,
        )

        # Load and check metadata
        loaded_data = storage.load_multi_timeframe_model(
            strategy_name="test_strategy", symbol="AAPL", timeframes=["1h", "4h"]
        )

        metadata = loaded_data["metadata"]
        assert metadata["additional_metadata"] == additional_metadata

    def test_latest_symlink_creation(
        self,
        storage,
        sample_model,
        sample_config,
        sample_training_result,
        sample_feature_result,
        sample_label_result,
    ):
        """Test that latest symlinks are created correctly."""
        strategy_name = "test_strategy"
        symbol = "AAPL"
        timeframes = ["1h", "4h"]

        # Save first model
        model_path1 = storage.save_multi_timeframe_model(
            model=sample_model,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframes=timeframes,
            config=sample_config,
            training_result=sample_training_result,
            feature_engineering_result=sample_feature_result,
            label_result=sample_label_result,
        )

        # Save second model (should update latest)
        model_path2 = storage.save_multi_timeframe_model(
            model=sample_model,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframes=timeframes,
            config=sample_config,
            training_result=sample_training_result,
            feature_engineering_result=sample_feature_result,
            label_result=sample_label_result,
        )

        # Load latest (should be second model)
        loaded_data = storage.load_multi_timeframe_model(
            strategy_name=strategy_name, symbol=symbol, timeframes=timeframes
        )

        # Should load the second model
        assert loaded_data["model_path"] == model_path2

    def test_factory_function(self, temp_storage_dir):
        """Test factory function for creating storage."""
        storage = create_multi_timeframe_model_storage(temp_storage_dir)

        assert isinstance(storage, MultiTimeframeModelStorage)
        assert storage.base_path == Path(temp_storage_dir)

    def test_metadata_completeness(
        self,
        storage,
        sample_model,
        sample_config,
        sample_training_result,
        sample_feature_result,
        sample_label_result,
    ):
        """Test that metadata contains all expected fields."""
        model_path = storage.save_multi_timeframe_model(
            model=sample_model,
            strategy_name="test_strategy",
            symbol="AAPL",
            timeframes=["1h", "4h", "1d"],
            config=sample_config,
            training_result=sample_training_result,
            feature_engineering_result=sample_feature_result,
            label_result=sample_label_result,
        )

        # Load metadata
        loaded_data = storage.load_multi_timeframe_model(
            strategy_name="test_strategy", symbol="AAPL", timeframes=["1h", "4h", "1d"]
        )

        metadata = loaded_data["metadata"]

        # Check all required metadata fields
        required_fields = [
            "strategy_name",
            "symbol",
            "timeframes",
            "version",
            "created_at",
            "model_type",
            "performance_summary",
            "feature_summary",
            "label_quality",
            "pytorch_version",
        ]

        for field in required_fields:
            assert field in metadata, f"Missing metadata field: {field}"

        # Check performance summary
        perf = metadata["performance_summary"]
        assert "final_train_loss" in perf
        assert "final_val_loss" in perf
        assert "timeframe_contributions" in perf

        # Check feature summary
        features = metadata["feature_summary"]
        assert "original_feature_count" in features
        assert "final_feature_count" in features
        assert "feature_names" in features

        # Check label quality
        labels = metadata["label_quality"]
        assert "total_labels" in labels
        assert "average_confidence" in labels
        assert "validation_rate" in labels
