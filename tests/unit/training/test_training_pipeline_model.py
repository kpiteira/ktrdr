"""
Unit tests for TrainingPipeline model methods.

Tests the model creation, training, and evaluation methods extracted
from StrategyTrainer to eliminate code duplication.
"""

from unittest.mock import Mock

import pytest
import torch
import torch.nn as nn

from ktrdr.async_infrastructure.cancellation import CancellationToken
from ktrdr.training.training_pipeline import TrainingPipeline


class TestCreateModel:
    """Test TrainingPipeline.create_model() method."""

    def test_create_model_mlp_basic(self):
        """Test creating a basic MLP model."""
        model_config = {
            "type": "mlp",
            "architecture": {
                "hidden_layers": [64, 32],
                "dropout": 0.2,
            },
            "num_classes": 3,
        }
        input_dim = 20
        output_dim = 3

        model = TrainingPipeline.create_model(
            input_dim=input_dim,
            output_dim=output_dim,
            model_config=model_config,
        )

        # Verify model is a nn.Module
        assert isinstance(model, nn.Module)

        # Verify model can process inputs of correct shape
        test_input = torch.randn(10, input_dim)
        output = model(test_input)
        assert output.shape == (10, output_dim)

    def test_create_model_mlp_custom_hidden_layers(self):
        """Test creating MLP with custom hidden layer configuration."""
        model_config = {
            "type": "mlp",
            "architecture": {
                "hidden_layers": [128, 64, 32, 16],
                "dropout": 0.3,
            },
            "num_classes": 3,
        }
        input_dim = 50
        output_dim = 3

        model = TrainingPipeline.create_model(
            input_dim=input_dim,
            output_dim=output_dim,
            model_config=model_config,
        )

        # Verify model structure
        test_input = torch.randn(5, input_dim)
        output = model(test_input)
        assert output.shape == (5, output_dim)

    def test_create_model_invalid_type(self):
        """Test that invalid model type raises error."""
        model_config = {
            "type": "invalid_model_type",
        }

        with pytest.raises(ValueError, match="Unknown model type"):
            TrainingPipeline.create_model(
                input_dim=20,
                output_dim=3,
                model_config=model_config,
            )

    def test_create_model_default_mlp(self):
        """Test creating model with default MLP type."""
        model_config = {
            "architecture": {
                "hidden_layers": [64, 32],
            },
            "num_classes": 3,
        }  # No 'type' specified, should default to MLP

        model = TrainingPipeline.create_model(
            input_dim=20,
            output_dim=3,
            model_config=model_config,
        )

        assert isinstance(model, nn.Module)


class TestTrainModel:
    """Test TrainingPipeline.train_model() method."""

    def test_train_model_basic(self):
        """Test basic model training."""
        # Create simple model
        model = nn.Sequential(
            nn.Linear(10, 20),
            nn.ReLU(),
            nn.Linear(20, 3),
        )

        # Create dummy training data
        X_train = torch.randn(100, 10)
        y_train = torch.randint(0, 3, (100,))
        X_val = torch.randn(20, 10)
        y_val = torch.randint(0, 3, (20,))

        training_config = {
            "epochs": 2,
            "batch_size": 16,
            "learning_rate": 0.001,
        }

        result = TrainingPipeline.train_model(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            training_config=training_config,
        )

        # Verify result structure (matches ModelTrainer output)
        assert "final_train_loss" in result
        assert "final_val_loss" in result
        assert "final_train_accuracy" in result
        assert "final_val_accuracy" in result
        assert "epochs_trained" in result
        assert result["epochs_trained"] == 2

    def test_train_model_with_progress_callback(self):
        """Test training with progress callback."""
        model = nn.Sequential(nn.Linear(10, 3))
        X_train = torch.randn(50, 10)
        y_train = torch.randint(0, 3, (50,))
        X_val = torch.randn(10, 10)
        y_val = torch.randint(0, 3, (10,))

        training_config = {
            "epochs": 2,
            "batch_size": 16,
        }

        progress_calls = []

        def progress_callback(epoch, total_epochs, metrics=None):
            progress_calls.append({"epoch": epoch, "total_epochs": total_epochs})

        result = TrainingPipeline.train_model(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            training_config=training_config,
            progress_callback=progress_callback,
        )

        # Verify progress callback was called
        assert len(progress_calls) > 0
        assert result["epochs_trained"] == 2

    def test_train_model_with_cancellation(self):
        """Test that training respects cancellation token."""
        model = nn.Sequential(nn.Linear(10, 3))
        X_train = torch.randn(100, 10)
        y_train = torch.randint(0, 3, (100,))
        X_val = torch.randn(20, 10)
        y_val = torch.randint(0, 3, (20,))

        training_config = {
            "epochs": 10,  # Many epochs
            "batch_size": 16,
        }

        # Create a mock cancelled token
        from ktrdr.async_infrastructure.cancellation import CancellationError

        token = Mock(spec=CancellationToken)
        token.is_cancelled.return_value = True
        token.is_cancelled_requested.return_value = True

        with pytest.raises(CancellationError):
            TrainingPipeline.train_model(
                model=model,
                X_train=X_train,
                y_train=y_train,
                X_val=X_val,
                y_val=y_val,
                training_config=training_config,
                cancellation_token=token,
            )

    def test_train_model_multi_symbol(self):
        """
        Test training with multi-symbol data.

        SYMBOL-AGNOSTIC: Multi-symbol data is concatenated before training.
        The model treats features from multiple symbols the same as single-symbol data.
        No symbol_indices needed - model learns patterns in indicators, not symbol identity.
        """
        model = nn.Sequential(nn.Linear(10, 3))

        # Multi-symbol training data (concatenated from multiple symbols)
        X_train = torch.randn(100, 10)
        y_train = torch.randint(0, 3, (100,))

        X_val = torch.randn(20, 10)
        y_val = torch.randint(0, 3, (20,))

        training_config = {
            "epochs": 2,
            "batch_size": 16,
        }

        result = TrainingPipeline.train_model(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            training_config=training_config,
        )

        # Verify result
        assert "final_train_loss" in result
        assert "final_val_loss" in result
        assert result["epochs_trained"] == 2


class TestEvaluateModel:
    """Test TrainingPipeline.evaluate_model() method."""

    def test_evaluate_model_basic(self):
        """Test basic model evaluation."""
        # Create and train simple model
        model = nn.Sequential(
            nn.Linear(10, 20),
            nn.ReLU(),
            nn.Linear(20, 3),
        )

        # Create dummy test data
        X_test = torch.randn(30, 10)
        y_test = torch.randint(0, 3, (30,))

        result = TrainingPipeline.evaluate_model(
            model=model,
            X_test=X_test,
            y_test=y_test,
        )

        # Verify result structure
        assert "test_accuracy" in result
        assert "test_loss" in result
        assert "precision" in result
        assert "recall" in result
        assert "f1_score" in result

        # Verify metrics are floats
        assert isinstance(result["test_accuracy"], float)
        assert isinstance(result["test_loss"], float)
        assert isinstance(result["precision"], float)
        assert isinstance(result["recall"], float)
        assert isinstance(result["f1_score"], float)

    def test_evaluate_model_none_test_data_raises_exception(self):
        """Test evaluation with no test data raises TrainingDataError.

        This is a fail-loudly behavior: if the data pipeline fails to produce
        test data, we should raise an exception rather than silently returning
        zeros that mask the infrastructure error.
        """
        import pytest

        from ktrdr.training.exceptions import TrainingDataError

        model = nn.Sequential(nn.Linear(10, 3))

        with pytest.raises(TrainingDataError) as exc_info:
            TrainingPipeline.evaluate_model(
                model=model,
                X_test=None,
                y_test=None,
            )

        # Exception message should explain the issue
        assert "test data" in str(exc_info.value).lower()

    def test_evaluate_model_partial_none_raises_exception(self):
        """Test that partial None (X_test or y_test) also raises."""
        import pytest

        from ktrdr.training.exceptions import TrainingDataError

        model = nn.Sequential(nn.Linear(10, 3))

        # X_test is None, y_test is not
        with pytest.raises(TrainingDataError):
            TrainingPipeline.evaluate_model(
                model=model,
                X_test=None,
                y_test=torch.randint(0, 3, (30,)),
            )

        # X_test is not None, y_test is None
        with pytest.raises(TrainingDataError):
            TrainingPipeline.evaluate_model(
                model=model,
                X_test=torch.randn(30, 10),
                y_test=None,
            )

    def test_evaluate_model_multi_symbol(self):
        """
        Test evaluation with multi-symbol data.

        SYMBOL-AGNOSTIC: Multi-symbol test data is concatenated before evaluation.
        The model evaluates features from multiple symbols the same as single-symbol data.
        No symbol_indices needed - model evaluates patterns in indicators, not symbol identity.
        """
        model = nn.Sequential(nn.Linear(10, 3))

        # Multi-symbol test data (concatenated from multiple symbols)
        X_test = torch.randn(30, 10)
        y_test = torch.randint(0, 3, (30,))

        result = TrainingPipeline.evaluate_model(
            model=model,
            X_test=X_test,
            y_test=y_test,
        )

        # Verify result structure
        assert "test_accuracy" in result
        assert "test_loss" in result
        assert "precision" in result
        assert "recall" in result
        assert "f1_score" in result

    def test_evaluate_model_perfect_predictions(self):
        """Test evaluation with perfect predictions."""
        # Create a simple model
        model = nn.Sequential(
            nn.Linear(5, 10),
            nn.ReLU(),
            nn.Linear(10, 3),
        )

        # Generate test data
        X_test = torch.randn(30, 5)
        # Create labels that repeat pattern (to ensure all classes represented)
        y_test = torch.tensor([0, 1, 2] * 10)

        # Train model briefly to get reasonable predictions
        # (We're not testing perfect accuracy, just that evaluation works)
        result = TrainingPipeline.evaluate_model(
            model=model,
            X_test=X_test,
            y_test=y_test,
        )

        # Verify all metrics are present and valid
        assert "test_accuracy" in result
        assert "test_loss" in result
        assert "precision" in result
        assert "recall" in result
        assert "f1_score" in result

        # Metrics should be valid floats between 0 and 1 (except loss)
        assert 0.0 <= result["test_accuracy"] <= 1.0
        assert 0.0 <= result["precision"] <= 1.0
        assert 0.0 <= result["recall"] <= 1.0
        assert 0.0 <= result["f1_score"] <= 1.0
        assert result["test_loss"] >= 0.0
