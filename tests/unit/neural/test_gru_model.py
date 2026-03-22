"""Tests for GRU trading model."""

import pytest
import torch

from ktrdr.neural.models.gru import GRUNetwork, GRUTradingModel


class TestGRUNetwork:
    """Test the raw PyTorch GRU network module."""

    def test_forward_classification(self):
        """GRU forward pass produces correct output shape for classification."""
        batch, seq_len, features, hidden, classes = 8, 20, 6, 64, 3
        net = GRUNetwork(
            features, hidden, num_layers=2, num_classes=classes, dropout=0.2
        )
        x = torch.randn(batch, seq_len, features)
        out = net(x)
        assert out.shape == (batch, classes)

    def test_forward_regression(self):
        """GRU forward pass produces correct output shape for regression."""
        batch, seq_len, features, hidden = 8, 20, 6, 64
        net = GRUNetwork(features, hidden, num_layers=2, num_classes=1, dropout=0.2)
        x = torch.randn(batch, seq_len, features)
        out = net(x)
        assert out.shape == (batch, 1)

    def test_single_sample_inference(self):
        """Batch size 1 works for inference."""
        net = GRUNetwork(6, 64, num_layers=2, num_classes=3, dropout=0.0)
        net.eval()
        x = torch.randn(1, 20, 6)
        with torch.no_grad():
            out = net(x)
        assert out.shape == (1, 3)


class TestGRUTradingModel:
    """Test the GRUTradingModel wrapper."""

    def _make_config(self, **overrides):
        config = {
            "type": "gru",
            "architecture": {
                "hidden_size": 32,
                "num_layers": 1,
                "dropout": 0.1,
                "sequence_length": 10,
            },
            "output_format": "classification",
            "num_classes": 3,
        }
        config.update(overrides)
        return config

    def test_build_model_returns_gru_network(self):
        """build_model creates a GRUNetwork."""
        model = GRUTradingModel(self._make_config())
        net = model.build_model(input_size=6)
        assert isinstance(net, GRUNetwork)

    def test_build_model_classification(self):
        """Classification model has correct output dimension."""
        model = GRUTradingModel(self._make_config(num_classes=3))
        net = model.build_model(input_size=6)
        x = torch.randn(2, 10, 6)
        out = net(x)
        assert out.shape == (2, 3)

    def test_missing_sequence_length_raises(self):
        """Missing sequence_length in architecture raises ValueError."""
        config = self._make_config()
        del config["architecture"]["sequence_length"]
        model = GRUTradingModel(config)
        with pytest.raises(ValueError, match="sequence_length"):
            model.build_model(input_size=6)
